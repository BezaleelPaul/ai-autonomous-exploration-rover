"""Perception node orchestration: capture -> detect -> decide -> send -> HUD.

The loop is deliberately fail-safe: any missing input (no frame, no detection,
dead serial) resolves to ``'S'``, and ``shutdown`` always tries to leave the
rover stopped.
"""

from __future__ import annotations

import contextlib
import logging
import time
from dataclasses import dataclass

from software.ai.detection import Detection
from software.ai.detector import BaseDetector, MockDetector, YoloDetector
from software.camera.esp32_stream import ESP32Stream
from software.camera.frame_manager import FrameManager
from software.control.command_emitter import CommandEmitter
from software.perception_node.http_link import HttpLink
from software.perception_node.hud import draw_hud
from software.perception_node.serial_link import SerialLink
from software.perception_node.stream import open_ip_webcam
from software.perception_node.zones import (
    STOP,
    SteeringDecision,
    SteeringPolicy,
    best_target,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NodeState:
    """Immutable snapshot of one perception cycle (tests assert on this)."""

    decision: SteeringDecision
    sent: bool
    stream_ok: bool
    serial_ok: bool
    target_count: int
    fps: float
    cycle: int


def policy_from_config(cfg: dict) -> SteeringPolicy:
    """Build the steering policy from ``perception:`` (falling back to ``navigation:``)."""
    perception = cfg.get("perception", {})
    navigation = cfg.get("navigation", {})
    return SteeringPolicy(
        left_boundary=float(
            perception.get("left_boundary", navigation.get("left_boundary", 0.33))
        ),
        center_boundary=float(
            perception.get("center_boundary", navigation.get("center_boundary", 0.66))
        ),
        stop_area_ratio=float(perception.get("stop_area_ratio", 0.35)),
    )


def build_detector(perception: dict, target: str, mock: bool = False) -> BaseDetector:
    """YOLOv8 Nano (ultralytics) locked onto a single target class."""
    if mock:
        return MockDetector(
            target=target,
            confidence=float(perception.get("confidence_threshold", 0.4)),
        )
    return YoloDetector(
        model=str(perception.get("model", "yolov8n.pt")),
        confidence_threshold=float(perception.get("confidence_threshold", 0.4)),
        allowed_classes=[target],
        imgsz=int(perception.get("imgsz", 320)),
        track=True,
    )


class PerceptionNode:
    """Tier-1 node: IP Webcam in, single-character motion commands out."""

    def __init__(
        self,
        cfg: dict,
        *,
        detector: BaseDetector | None = None,
        stream: ESP32Stream | None = None,
        serial: SerialLink | None = None,
        mock: bool = False,
        mock_camera: bool | None = None,
        mock_serial: bool | None = None,
        target: str | None = None,
        hud_enabled: bool | None = None,
    ) -> None:
        self.cfg = cfg
        perception = cfg.get("perception", {})
        camera = cfg.get("camera", {})
        mock_cam = mock if mock_camera is None else bool(mock_camera)
        mock_ser = mock if mock_serial is None else bool(mock_serial)
        self.target = target or str(perception.get("target_class", "person"))
        self.policy = policy_from_config(cfg)
        self.detector = detector or build_detector(
            perception, self.target, mock=mock_cam
        )
        self.stream = stream or open_ip_webcam(
            str(perception.get("stream_url", "")),
            mock=mock_cam,
            reconnect_timeout_s=float(camera.get("reconnect_timeout_s", 5.0)),
            frozen_timeout_s=float(camera.get("frozen_frame_timeout_s", 3.0)),
            jpeg_timeout_s=camera.get("jpeg_timeout_s"),
            fps_target=camera.get("fps_target"),
        )
        mode = str(perception.get("serial_mode", "auto"))
        if mode == "http":
            self.serial = serial or HttpLink(
                str(perception.get("rover_url", "http://192.168.4.1")),
                timeout_s=float(cfg.get("serial", {}).get("command_timeout_s", 1.0)),
                mock=mock_ser,
            )
        else:
            self.serial = serial or SerialLink(
                port=str(perception.get("serial_port", "")) or None,
                baud_rate=int(perception.get("baud_rate", 9600)),
                mode=mode,
                timeout_s=float(cfg.get("serial", {}).get("command_timeout_s", 1.0)),
                reconnect_attempts=int(
                    cfg.get("serial", {}).get("reconnect_attempts", 5)
                ),
                mock=mock_ser,
            )
        self.frames = FrameManager(
            inference_interval=int(perception.get("inference_interval", 2)),
            max_frame_age_s=float(camera.get("frozen_frame_timeout_s", 3.0)),
        )
        enabled = perception.get("hud_enabled", True)
        self.hud_enabled = bool(enabled) if hud_enabled is None else bool(hud_enabled)
        self.window_name = str(
            perception.get("window_name", "AI Rover - Perception Node")
        )
        self.heartbeat_interval_s = float(perception.get("heartbeat_interval_s", 1.0))
        self.command_cooldown_s = float(perception.get("command_cooldown_s", 0.2))
        self.left_boundary = self.policy.left_boundary
        self.center_boundary = self.policy.center_boundary
        self.stop_area_ratio = self.policy.stop_area_ratio

        self._frame = None
        self._detections: list[Detection] = []
        self._decision = SteeringDecision(STOP, None, 0.0, False, "not started")
        self._emitter = CommandEmitter(
            self.serial.send,
            cooldown_s=self.command_cooldown_s,
            heartbeat_s=self.heartbeat_interval_s,
        )
        self._cycle = 0
        self._running = False
        self._paused = False
        self._detector_ready = False
        self._fps = 0.0
        self._fps_frames = 0
        self._fps_window_start = time.time()

    # ------------------------------------------------------------ lifecycle
    def startup(self) -> bool:
        """Load the model and open what can be opened. False = do not run."""
        load = getattr(self.detector, "load", None)
        self._detector_ready = (
            bool(load()) if callable(load) else self.detector.is_ready()
        )
        if not self._detector_ready:
            logger.error(
                "detector failed to load (%s) - check weights/network",
                getattr(self.detector, "model_name", type(self.detector).__name__),
            )
            return False
        if not self.stream.open() and not self.stream.mock:
            logger.warning(
                "stream not open yet (%s); emitting STOP until it appears",
                self.stream.url,
            )
        if not self.serial.connect():
            logger.warning("serial link down; commands are dropped until it reconnects")
        return True

    def shutdown(self) -> None:
        """Leave the rover stopped and release every resource."""
        self._running = False
        with contextlib.suppress(Exception):
            self.serial.send(STOP)
        with contextlib.suppress(Exception):
            self.serial.close()
        with contextlib.suppress(Exception):
            self.stream.close()
        if self.hud_enabled:
            with contextlib.suppress(Exception):
                import cv2

                cv2.destroyAllWindows()
        logger.info("perception node stopped after %s cycles", self._cycle)

    # ------------------------------------------------------------- control
    def step(self, now: float | None = None) -> NodeState:
        """Run exactly one perception cycle (idempotent for a frozen input)."""
        now = time.time() if now is None else now
        self._cycle += 1
        frame = self.stream.read()
        self._frame = frame
        stream_ok = frame is not None

        if frame is None:
            self._detections = []
            decision = self.policy.decide(None, 640.0, 480.0)
        else:
            self.frames.observe(frame, capture_time=now)
            if self.frames.should_infer():
                pending = self.frames.consume()
                if pending is not None:
                    self._detections = self.detector.detect(pending)
            target = best_target(self._matching_detections())
            decision = self.policy.decide(
                target, float(frame.shape[1]), float(frame.shape[0])
            )
            self._count_fps(now)

        self._decision = decision
        sent = self.emit(decision, now)
        return NodeState(
            decision=decision,
            sent=sent,
            stream_ok=stream_ok,
            serial_ok=self.serial_ok,
            target_count=len(self._matching_detections()),
            fps=self._fps,
            cycle=self._cycle,
        )

    @property
    def serial_ok(self) -> bool:
        return bool(getattr(self.serial, "connected", False))

    def emit(self, decision: SteeringDecision, now: float) -> bool:
        """Throttled send: STOP goes out immediately, motion respects cooldowns.

        A heartbeat re-sends the active command so the Arduino's communication
        watchdog never trips while the target stays put.
        """
        return self._emitter.emit(decision.command, now) is not None

    def _matching_detections(self) -> list[Detection]:
        name = self.target.lower()
        return [d for d in self._detections if d.class_name.lower() == name]

    def _count_fps(self, now: float) -> None:
        self._fps_frames += 1
        span = now - self._fps_window_start
        if span >= 1.0:
            self._fps = self._fps_frames / span
            self._fps_frames = 0
            self._fps_window_start = now

    # ----------------------------------------------------------------- HUD
    def render(self, state: NodeState | None = None):
        """Annotate the newest frame; None when no frame is available."""
        if self._frame is None:
            return None
        state = state or NodeState(
            decision=self._decision,
            sent=False,
            stream_ok=False,
            serial_ok=self.serial_ok,
            target_count=len(self._matching_detections()),
            fps=self._fps,
            cycle=self._cycle,
        )
        return draw_hud(
            self._frame,
            state.decision,
            self._matching_detections(),
            fps=state.fps,
            serial_ok=state.serial_ok,
            stream_ok=state.stream_ok,
            left_boundary=self.left_boundary,
            center_boundary=self.center_boundary,
            stop_area_ratio=self.stop_area_ratio,
            target=self.target,
        )

    def _show(self, state: NodeState) -> bool:
        """Blit the HUD; False when this host has no usable OpenCV window."""
        image = self.render(state)
        if image is None:
            return True
        try:
            import cv2

            cv2.imshow(self.window_name, image)
            return True
        except Exception as exc:
            logger.warning("no display available (%s); falling back to headless", exc)
            self.hud_enabled = False
            return False

    # ------------------------------------------------------------- running
    def run(self, loop_period_s: float = 0.03, max_cycles: int | None = None) -> None:
        """Loop until 'q'/ESC (with HUD) or CTRL+C. Always shuts down cleanly."""
        if not self.startup():
            return
        self._running = True
        try:
            while self._running:
                if max_cycles is not None and self._cycle >= max_cycles:
                    break
                if self._paused:
                    self.serial.send(STOP)
                    self._emitter.reset(STOP, time.time())
                    if not self.hud_enabled:
                        time.sleep(loop_period_s)
                    key = self._wait_key()
                    if key in _QUIT_KEYS:
                        break
                    if key == ord("p"):
                        self._paused = False
                    continue

                state = self.step()
                if self.hud_enabled:
                    self._show(state)
                    key = self._wait_key()
                    if key in _QUIT_KEYS:
                        break
                    if key == ord("h"):
                        self.hud_enabled = False
                        with contextlib.suppress(Exception):
                            import cv2

                            cv2.destroyWindow(self.window_name)
                    if key == ord("p"):
                        self._paused = True
                else:
                    time.sleep(loop_period_s)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def _wait_key(self) -> int:
        try:
            import cv2

            return int(cv2.waitKey(1)) & 0xFF
        except Exception:
            return -1


_QUIT_KEYS = {ord("q"), 27}
