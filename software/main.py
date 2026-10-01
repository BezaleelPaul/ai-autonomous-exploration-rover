"""Main orchestrator: STARTUP -> LOOP (PERCEIVE/DECIDE/SAFETY/CONTROL) -> SHUTDOWN.
Modes: manual | observe | search | scan360
CTRL+C always sends STOP.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import contextlib

from software.ai.detector import create_detector
from software.camera.enhance import enhance_for_inference
from software.camera.esp32_stream import ESP32Stream
from software.camera.frame_manager import FrameManager
from software.control.odometry import odometry_from_config
from software.control.pid import pid_from_config
from software.hardware.arduino_serial import ArduinoSerial
from software.navigation.decision_engine import DecisionEngine
from software.navigation.obstacle_avoidance import ObstacleAvoidance
from software.navigation.target_search import TargetSearch
from software.perception.object_tracker import ObjectTracker
from software.perception.scene_analyzer import SceneAnalyzer
from software.safety.failsafe import safe_stop
from software.safety.manual_guard import ManualMotionGuard
from software.safety.safety_manager import SafetyManager
from software.fusion.sensor_fusion import SensorFusion
from software.telemetry.event_logger import EventLogger
from software.telemetry.mission_logger import MissionLogger
from software.utils.config_loader import load_config


class RoverApp:
    def __init__(
        self,
        cfg: dict,
        mode: str = "observe",
        target: str = "bottle",
        mock_hw: bool = False,
    ):
        self.cfg = cfg
        self.mode = mode
        self.target_name = target
        self.mock_hw = mock_hw
        cam, ai, rov, ser, nav, saf = (
            cfg["camera"],
            cfg["ai"],
            cfg["rover"],
            cfg["serial"],
            cfg["navigation"],
            cfg["safety"],
        )
        self.serial = ArduinoSerial(
            ser["port"],
            ser["baud_rate"],
            ser["command_timeout_s"],
            mock=mock_hw,
            reconnect_attempts=ser.get("reconnect_attempts", 5),
        )
        self.camera = ESP32Stream(
            cam["esp32_url"],
            cam["reconnect_timeout_s"],
            cam.get("frozen_frame_timeout_s", 3.0),
            mock=mock_hw,
            fps_target=cam.get("fps_target"),
            jpeg_timeout_s=cam.get("jpeg_timeout_s"),
        )
        self.frames = FrameManager(ai.get("inference_interval", 2))
        # --mock simulates the whole perception stack too: never loads weights
        # or touches the network, regardless of ai.backend (test/demo isolation)
        det_cfg = {**cfg, "ai": {**cfg["ai"], "backend": "mock"}} if mock_hw else cfg
        self.detector = create_detector(det_cfg)
        # Detection recall and driving caution are separate dials: the detector
        # reports everything above ai.confidence_threshold, but we only steer
        # toward — and drive forward on — targets at ai.target_confidence, so
        # lowering the detection bar cannot relax the forward-motion gate.
        self.target_confidence = float(
            ai.get("target_confidence", ai["confidence_threshold"])
        )
        self.tracker = ObjectTracker(
            target, self.target_confidence, nav["target_lock_duration_s"]
        )
        self.scene = SceneAnalyzer(
            nav["left_boundary"],
            nav["center_boundary"],
            rov.get("approach_stop_width_ratio", 0.45),
        )
        # control: steering_kp/steering_min_pwm -> P-steering turn PWM on L/R
        ctl = cfg.get("control", {})
        self.engine = DecisionEngine(
            nav.get("center_tolerance", 0.06),
            nav["min_command_duration_s"],
            nav["decision_cooldown_s"],
            steering_kp=float(ctl.get("steering_kp", 0.0)),
            steering_min_pwm=int(ctl.get("steering_min_pwm", 120)),
        )
        self.search = TargetSearch(
            nav["search_timeout_s"],
            nav["max_search_rotations"],
            rov["search_rotation_duration_s"],
        )
        self.avoid = ObstacleAvoidance(
            rov["emergency_stop_distance_cm"], rov["slow_down_distance_cm"]
        )
        # config/thresholds.yaml is the tuning surface: safety cutoffs are
        # consumed from it at runtime (config.yaml copies are validated equal)
        ultra = cfg["thresholds"].get("ultrasonic", {})
        self.safety = SafetyManager(
            float(ultra.get("emergency_stop_cm", rov["emergency_stop_distance_cm"])),
            float(ultra.get("slow_cm", rov["slow_down_distance_cm"])),
            saf.get("comm_timeout_s", 3.0),
            sensor_invalid_limit=int(saf.get("sensor_invalid_limit", 5)),
        )
        # Phase 9+ foundations (docs/future-work/30): PID gains + odometry
        # geometry from config `control:`; applied once encoder hardware exists.
        self.drive_pid = pid_from_config(cfg)
        self.odometry = odometry_from_config(cfg)
        self.sensor_fusion = SensorFusion(
            emergency_obstacle_dist_m=float(rov.get("emergency_stop_distance_cm", 15.0)) / 100.0,
            min_target_confidence=self.target_confidence,
            wheel_odometry=self.odometry,
        )
        self.logger = EventLogger(cfg["logging"]["dir"], cfg["logging"]["level"])
        self.mission_logger = MissionLogger(cfg["logging"]["dir"])
        self.running = False
        self.state: dict = {"mode": mode, "command": "S", "safety": "-"}
        if mode == "search":
            self.search.start()

    # ----- lifecycle -----
    def startup(self) -> bool:
        self.logger.log_text(
            f"Starting mode={self.mode} target={self.target_name} mock={self.mock_hw}"
        )
        if not self.serial.connect():
            self.logger.log_text("Serial connect FAILED")
            if (
                self.cfg["safety"].get("require_serial_for_auto", True)
                and self.mode != "manual"
            ):
                return False
        self.camera.open()
        self.serial.send("S")
        # Preload weights before the first frame (HF ~20 s, YOLO ~1 s); non-fatal
        try:
            load = getattr(self.detector, "load", None)
            if callable(load):
                ok = load()
                self.logger.log_text(f"AI model ready={ok}")
        except Exception as e:
            self.logger.log_text(f"AI load error: {e}")
        self.running = True
        return True

    def shutdown(self) -> None:
        self.running = False
        with contextlib.suppress(Exception):
            safe_stop(self.serial.send)
        with contextlib.suppress(Exception):
            self.serial.disconnect()
        with contextlib.suppress(Exception):
            self.camera.close()
        self.logger.log_text("Shutdown complete (motors STOP).")

    def get_state(self) -> dict:
        return dict(self.state)

    # ----- one step -----
    def step(self) -> dict:
        frame = self.camera.read()
        if frame is not None:
            # Latest-frame buffer: records capture time so frame age / dropped
            # frames are measurable (software/camera/frame_manager.py).
            # Camera stubs in tests expose no stats, so read defensively.
            stats = getattr(self.camera, "stats", None)
            capture_time = getattr(stats, "last_frame_time", 0.0)
            try:
                capture_time = float(capture_time)
            except (TypeError, ValueError):
                capture_time = 0.0
            self.frames.observe(frame, capture_time=capture_time)
            latest = self.frames.consume()
            if latest is not None:
                frame = latest
        cam_ok = self.camera.is_healthy()
        ser_ok = self.serial.is_healthy(self.cfg["safety"].get("comm_timeout_s", 3.0))
        dist = self.serial.telemetry.distance_cm

        if (
            frame is None
            and self.cfg["safety"].get("require_camera_for_auto", True)
            and self.mode in ("observe", "search", "scan360")
        ):
            safe_stop(self.serial.send)
            self.state.update(command="S", safety="CAMERA_FAIL", distance=dist)
            return self.state

        dets = []
        infer_ms = 0.0
        if frame is not None and self.frames.should_infer():
            cam_cfg = self.cfg["camera"]
            if (
                cam_cfg.get("enhance_clahe")
                or cam_cfg.get("enhance_sharpen")
                or cam_cfg.get("enhance_denoise")
            ):
                frame = enhance_for_inference(
                    frame,
                    clahe=bool(cam_cfg.get("enhance_clahe", False)),
                    sharpen=bool(cam_cfg.get("enhance_sharpen", False)),
                    denoise=bool(cam_cfg.get("enhance_denoise", False)),
                )
            t0 = time.time()
            try:
                dets = self.detector.detect(frame) or []
            except Exception:
                dets = []
            infer_ms = (time.time() - t0) * 1000.0

        target = self.tracker.update(dets, frame=frame)
        fw = float(frame.shape[1]) if frame is not None else 640.0
        scene = self.scene.analyze(target, dets, fw)

        # desired command per mode (decision carries the P-steering speed)
        decision = None
        if self.mode == "search":
            cmd, done, _msg = self.search.update(target is not None)
            if scene.target:
                decision = self.engine.decide(
                    scene.position,
                    scene.very_close,
                    True,
                    center_error=scene.center_error,
                )
                cmd = decision.command
            else:
                self.engine.to_search()
                if done and not self.search.s.active:
                    cmd = "S"
        elif self.mode == "scan360":
            # scan whenever the target is absent; approach when it is visible
            if not self.search.s.active:
                self.search.start()
            cmd, done, _msg = self.search.update(target is not None)
            if scene.target:
                decision = self.engine.decide(
                    scene.position,
                    scene.very_close,
                    True,
                    center_error=scene.center_error,
                )
                cmd = decision.command
        elif self.mode == "observe":
            if target is None:
                cmd = "S"
            else:
                decision = self.engine.decide(
                    scene.position,
                    scene.very_close,
                    True,
                    center_error=scene.center_error,
                )
                cmd = decision.command
        else:
            cmd = "S"

        # safety gate first, obstacle layer second: SafetyManager must see the
        # raw command so the R4 emergency latch actually engages (M1)
        conf = target.confidence if target else 0.0
        verdict = self.safety.check(
            cmd, dist, ser_ok, cam_ok, conf, self.target_confidence
        )
        final = self.avoid.override(verdict.command, dist)
        # reflect the safety outcome in the engine state machine (docs/19)
        if verdict.reason.startswith("EMERGENCY"):
            self.engine.emergency()
        elif verdict.reason.startswith("CAUTION"):
            self.engine.state = "AVOIDING"
        # Protocol v2: attach the proportional turn speed only while the
        # final command still matches the steering decision (L/R); safety or
        # obstacle overrides downgrade to a bare command.
        turn_speed = (
            decision.speed
            if decision is not None and final == decision.command
            else None
        )
        self.serial.send(final, speed=turn_speed)
        robot_state = self.sensor_fusion.update(scene, self.serial.telemetry)
        self.state.update(
            mode=self.mode,
            command=final,
            safety=verdict.reason,
            distance=dist,
            target=self.target_name if target else "-",
            confidence=round(conf, 3),
            position=scene.position,
            fps=round(self.camera.stats.fps, 1),
            infer_ms=round(infer_ms, 1),
            velocity=robot_state.velocity_m_s,
            heading=robot_state.heading_deg,
            tilt=robot_state.tilt_deg,
            battery=robot_state.battery_pct,
        )
        self.mission_logger.log_mission_step(robot_state, target, final)
        self.logger.log_event(
            self.mode,
            self.state["target"],
            conf,
            scene.position,
            dist,
            final,
            verdict.reason,
            infer_ms,
            self.camera.stats.fps,
        )
        if self.cfg["logging"].get("log_frames"):
            age = self.frames.frame_age()
            age_txt = "n/a" if age is None else f"{age:.3f}s"
            self.logger.log_text(
                f"FRAME fps={self.camera.stats.fps:.1f} infer_ms={infer_ms:.1f} "
                f"frame_age={age_txt} dropped={self.frames.stats()['dropped']} "
                f"cmd={final} dist={dist}"
            )
        return self.state

    def run_forever(self) -> None:
        try:
            while self.running:
                self.step()
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()


def manual_loop(app: RoverApp) -> None:
    print("MANUAL: W/A/S/D move, SPACE stop, Q quit. Safety still enforced.")
    print("Motion auto-stops after movement_timeout_s of no input (R5).")
    keys = {"w": "F", "s": "B", "a": "L", "d": "R", " ": "S"}
    guard = ManualMotionGuard(
        app.serial.send, app.cfg["rover"].get("movement_timeout_s", 1.0)
    )
    try:
        while True:
            try:
                ch = input("cmd [w/a/s/d/space/q]: ").strip().lower()
            except EOFError:
                break
            if ch in ("q", "quit"):
                break
            if ch == "":
                ch = " "
            cmd = keys.get(ch, "S")
            dist = app.serial.telemetry.distance_cm
            v = app.safety.check(
                cmd,
                dist,
                app.serial.is_healthy(),
                True,
                1.0,
                0.0,
                allow_without_camera=True,
            )
            guard.send(v.command)
            print(f" -> {v.command} ({v.reason}) dist={dist}")
    finally:
        guard.close()
        app.shutdown()


def main() -> None:
    p = argparse.ArgumentParser(description="AI Visual Smart Rover")
    p.add_argument(
        "--mode", default="observe", choices=["manual", "observe", "search", "scan360"]
    )
    p.add_argument(
        "--target",
        default=None,
        help="target class name (default: config ai.target_class, e.g. bottle)",
    )
    p.add_argument("--config", default="config/config.yaml")
    p.add_argument(
        "--mock", action="store_true", help="no hardware: simulated camera+serial"
    )
    p.add_argument("--dashboard", action="store_true")
    args = p.parse_args()

    cfg = load_config(args.config)
    target_name = args.target or cfg.get("ai", {}).get("target_class", "bottle")
    app = RoverApp(cfg, args.mode, target_name, mock_hw=args.mock)
    if not app.startup():
        print("Startup failed (see logs). Motors STOPPED.")
        app.shutdown()
        sys.exit(1)

    if args.dashboard or cfg.get("dashboard", {}).get("enabled"):
        try:
            from software.dashboard.app import run_dashboard

            t = threading.Thread(
                target=run_dashboard,
                kwargs={
                    "get_state_fn": app.get_state,
                    "host": cfg["dashboard"]["host"],
                    "port": cfg["dashboard"]["port"],
                },
                daemon=True,
            )
            t.start()
            print(
                f"Dashboard on http://{cfg['dashboard']['host']}:{cfg['dashboard']['port']}"
            )
        except Exception as e:
            print(f"Dashboard unavailable: {e}")

    if args.mode == "manual":
        manual_loop(app)
    else:
        app.run_forever()


if __name__ == "__main__":
    main()
