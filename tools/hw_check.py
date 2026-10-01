"""Hardware-in-the-loop CLI checks: flash, serial safety, camera, ports.

Lets an operator (or an agent) code and test the REAL rover over USB/Wi-Fi:

  py -3.12 tools/hw_check.py ports                  # find the Arduino/ESP32
  py -3.12 tools/hw_check.py flash --target uno     # compile + upload UNO
  py -3.12 tools/hw_check.py flash --target esp32   # compile + upload camera
  py -3.12 tools/hw_check.py serial                 # safe protocol tests
  py -3.12 tools/hw_check.py serial --motion --space   # + motor drive test
  py -3.12 tools/hw_check.py serial --obstacle      # + 15cm emergency gate
  py -3.12 tools/hw_check.py esp32                  # Wi-Fi camera checks
  py -3.12 tools/hw_check.py mon                    # raw telemetry view
  py -3.12 tools/hw_check.py all                    # ports + safe serial + esp32

Exit codes: 0 = all executed checks passed, 1 = at least one FAIL,
2 = nothing executed (everything skipped / no hardware found).
"""

import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config", "config.yaml")
LOG_DIR = os.path.join(ROOT, "logs")

BAUD = 9600
COMM_TIMEOUT_MS = 3000
TELEMETRY_MS = 200
EMERGENCY_CM = 15.0
DEFAULT_STREAM = "http://192.168.1.100:81/stream"

CLI_CANDIDATES = (
    "arduino-cli",
    r"C:\Program Files\Arduino CLI\arduino-cli.exe",
    os.path.join(os.path.expanduser("~"), "tools", "bin", "arduino-cli.exe"),
)
UNO_FQBN = "arduino:avr:uno"
ESP32_FQBN = "esp32:esp32:esp32cam"
SKETCHES = {
    "uno": (os.path.join("arduino", "rover_controller"), UNO_FQBN),
    "esp32": (os.path.join("esp32", "camera_stream"), ESP32_FQBN),
}

# Port descriptions that are definitely NOT a rover board.
PORT_DENY = re.compile(
    r"intel\(r\) .*sol|bluetooth|communications port \(com\d+\)", re.I
)
# Port descriptions that look like a serial board (CH340/CP210x/FTDI/Arduino).
PORT_LIKE = re.compile(
    r"arduino|ch340|ch341|cp210|wch|usb-serial|usb serial|ftdi|esp32|heltec",
    re.I,
)

LINE_RE = re.compile(r"^(DIST|STATUS|TICKS):(.+)$")


class Report:
    def __init__(self):
        self.rows = []

    def add(self, status, cid, detail=""):
        self.rows.append((status, cid, detail))
        print("%-4s %s%s" % (status, cid, " - " + detail if detail else ""))

    def summary(self):
        fails = [r for r in self.rows if r[0] == "FAIL"]
        runs = [r for r in self.rows if r[0] in ("PASS", "FAIL")]
        print("-" * 60)
        print(
            "SUMMARY: %d passed, %d failed, %d skipped"
            % (
                len([r for r in runs if r[0] == "PASS"]),
                len(fails),
                len([r for r in self.rows if r[0] == "SKIP"]),
            )
        )
        return 1 if fails else (0 if runs else 2)


def _config_value(key):
    """Best-effort read of a scalar from config/config.yaml."""
    try:
        import yaml

        with open(CONFIG, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        def dig(obj, path):
            for part in path.split("."):
                obj = obj.get(part) if isinstance(obj, dict) else None
                if obj is None:
                    return None
            return obj

        return dig(data, key)
    except Exception:
        return None


def find_cli():
    for name in CLI_CANDIDATES:
        found = shutil.which(name) if os.sep not in name and "/" not in name else name
        if found and os.path.exists(found):
            return found
    return None


def list_ports():
    import serial.tools.list_ports as lp

    return sorted(lp.comports(), key=lambda p: p.device)


def pick_port(explicit=None):
    """Return (port, candidates) - auto-detect a rover board, never guess."""
    ports = list_ports()
    if explicit:
        return explicit, [p.device for p in ports]
    good = [p for p in ports if PORT_LIKE.search(p.description or "")]
    good = [p for p in good if not PORT_DENY.search(p.description or "")]
    if len(good) == 1:
        return good[0].device, [p.device for p in ports]
    return None, [p.device for p in ports]


def cmd_ports(_args):
    rep = Report()
    ports = list_ports()
    if not ports:
        rep.add("SKIP", "ports", "no serial ports found - plug the board in USB")
        return rep.summary()
    for p in ports:
        note = ""
        if PORT_DENY.search(p.description or ""):
            note = "  <- NOT a board (system port)"
        elif PORT_LIKE.search(p.description or ""):
            note = "  <- likely rover board"
        print(
            "  %-6s %-55s hwid=%s%s"
            % (p.device, (p.description or "")[:55], p.hwid, note)
        )
    chosen, _ = pick_port()
    if chosen:
        rep.add("PASS", "ports.autodetect", "rover board candidate: %s" % chosen)
    else:
        cfg = _config_value("serial.port")
        rep.add(
            "SKIP",
            "ports.autodetect",
            "no unique board match (config serial.port=%s); pass --port" % cfg,
        )
    return rep.summary()


def _run(cmd, timeout=600):
    print("running:", " ".join(str(c) for c in cmd))
    try:
        proc = subprocess.run(
            [str(c) for c in cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        print("error: %s" % exc)
        return 127
    except subprocess.TimeoutExpired:
        print("error: command timed out after %ds" % timeout)
        return 124
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = "\n".join(out.strip().splitlines()[-12:])
    if tail:
        print(tail)
    return proc.returncode


def cmd_flash(args):
    rep = Report()
    cli = find_cli()
    if cli is None:
        rep.add("FAIL", "flash.cli", "arduino-cli not found on PATH")
        return rep.summary()
    sketch, fqbn = SKETCHES[args.target]
    sketch_path = os.path.join(ROOT, sketch)
    rc = _run([cli, "compile", "--fqbn", fqbn, sketch_path])
    if rc != 0:
        rep.add("FAIL", "flash.compile", "%s %s" % (args.target, fqbn))
        return rep.summary()
    rep.add("PASS", "flash.compile", "%s %s" % (args.target, fqbn))
    if args.compile_only:
        return rep.summary()

    port, candidates = pick_port(args.port)
    if port is None:
        rep.add(
            "FAIL",
            "flash.port",
            "no board port found (seen: %s); plug USB in / pass --port"
            % (", ".join(candidates) or "none"),
        )
        return rep.summary()
    rep.add("PASS", "flash.port", port)
    up = _run([cli, "upload", "--fqbn", fqbn, "-p", port, sketch_path])
    if up == 0:
        hint = " (hold BOOT if handshake fails)" if args.target == "esp32" else ""
        rep.add("PASS", "flash.upload", port + hint)
    else:
        rep.add(
            "FAIL",
            "flash.upload",
            "%s%s"
            % (
                port,
                " (try holding BOOT while retrying)" if args.target == "esp32" else "",
            ),
        )
    return rep.summary()


class Telemetry:
    """Reads and decodes rover TX lines from an open serial port."""

    def __init__(self, ser):
        self.ser = ser
        self.dist = None  # last float cm (None = never seen)
        self.status = None  # last STATUS string
        self.status_seq = []  # (t, status) in read order
        self.dist_seq = []  # (t, cm)
        self.ticks_seen = False
        self.errors = 0  # STATUS:ERROR count since mark
        self.t0 = time.time()
        self.last_line = ""

    def pump(self, seconds):
        deadline = time.time() + seconds
        buf = b""
        while time.time() < deadline:
            chunk = self.ser.read(256)
            if chunk:
                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    self._line(raw.decode("ascii", "replace").strip())
            else:
                time.sleep(0.01)

    def _line(self, text):
        if not text:
            return
        self.last_line = text
        m = LINE_RE.match(text)
        if not m:
            return
        kind, val = m.group(1), m.group(2)
        now = time.time() - self.t0
        if kind == "DIST":
            try:
                v = float(val)
            except ValueError:
                return
            self.dist = v
            self.dist_seq.append((now, v))
        elif kind == "STATUS":
            self.status = val
            self.status_seq.append((now, val))
            if val == "ERROR":
                self.errors += 1
        elif kind == "TICKS":
            if re.fullmatch(r"\d+,\d+", val):
                self.ticks_seen = True

    def statuses_since(self, t):
        return [s for (tt, s) in self.status_seq if tt >= t]


def _open(port, baud=BAUD):
    import serial

    ser = serial.Serial(port, baud, timeout=0.05)
    return ser


def cmd_serial(args):
    rep = Report()
    port, candidates = pick_port(getattr(args, "port", None))
    if port is None:
        rep.add(
            "SKIP",
            "serial.port",
            "no board found (seen: %s); plug USB or pass --port"
            % (", ".join(candidates) or "none"),
        )
        return rep.summary()

    try:
        ser = _open(port)
    except Exception as exc:
        rep.add("FAIL", "serial.open", "%s: %s" % (port, exc))
        return rep.summary()
    rep.add("PASS", "serial.open", "%s @ %d baud" % (port, BAUD))

    tel = None
    try:
        time.sleep(2.5)  # UNO auto-reset on open (DTR) -> reboot
        tel = Telemetry(ser)
        tel.pump(4.0)

        # 1. telemetry heartbeat
        if not tel.dist_seq:
            rep.add(
                "FAIL",
                "serial.telemetry",
                "no DIST lines; last=%r (firmware missing/baud wrong?)" % tel.last_line,
            )
            return rep.summary()
        rep.add(
            "PASS",
            "serial.telemetry",
            "%d DIST, %d STATUS lines" % (len(tel.dist_seq), len(tel.status_seq)),
        )

        # 2. ultrasonic sensor health (DIST:-1 = no echo = wiring fault)
        last_dist = tel.dist if tel.dist is not None else -1.0
        if last_dist < 0:
            rep.add(
                "FAIL",
                "serial.ultrasonic",
                "DIST:-1 (no echo) - check HC-SR04 VCC/GND, TRIG=D11, ECHO=D12",
            )
        elif 2.0 <= last_dist <= 400.0:
            rep.add("PASS", "serial.ultrasonic", "last DIST=%.1f cm" % last_dist)
        else:
            rep.add("FAIL", "serial.ultrasonic", "out-of-range DIST=%.1f" % last_dist)

        # 3. STATUS vocabulary + TICKS format
        if tel.status_seq:
            rep.add("PASS", "serial.status", "last STATUS:%s" % tel.status)
        else:
            rep.add("FAIL", "serial.status", "no STATUS lines")
        rep.add(
            "PASS" if tel.ticks_seen else "FAIL",
            "serial.ticks",
            "TICKS:<l>,<r> decoded" if tel.ticks_seen else "no valid TICKS line",
        )

        # 4. malformed chunk -> STATUS:ERROR (motors stay off by design)
        before = len([1 for (_, s) in tel.status_seq if s == "ERROR"])
        ser.write(b"X9Z\n")
        ser.flush()
        tel.pump(1.0)
        err_after = len([1 for (_, s) in tel.status_seq if s == "ERROR"]) - before
        if err_after > 0:
            rep.add(
                "PASS", "serial.invalid", "%d STATUS:ERROR replies to junk" % err_after
            )
        else:
            rep.add(
                "FAIL", "serial.invalid", "junk input accepted without STATUS:ERROR"
            )

        # 5. speed-suffix parse (S180 = stop + PWM suffix, must not error)
        base = len([1 for (_, s) in tel.status_seq if s == "ERROR"])
        ser.write(b"S180\n")
        ser.flush()
        tel.pump(0.8)
        delta = len([1 for (_, s) in tel.status_seq if s == "ERROR"]) - base
        rep.add(
            "PASS" if delta == 0 else "FAIL",
            "serial.speed_suffix",
            "S180 parsed cleanly" if delta == 0 else "S180 wrongly rejected",
        )

        # 6. comm watchdog: silence > 3000ms -> STATUS:STOP, then recover
        ser.write(b"S\n")
        ser.flush()
        tel.pump(0.4)
        mark = time.time() - tel.t0
        tel.pump(4.2)
        stopped = [s for (t, s) in tel.status_seq if t >= mark + 3.0 and s == "STOP"]
        if stopped:
            rep.add(
                "PASS",
                "serial.watchdog_stop",
                "STATUS:STOP after %.1fs silence" % (COMM_TIMEOUT_MS / 1000.0),
            )
        else:
            rep.add(
                "FAIL", "serial.watchdog_stop", "no STATUS:STOP during 4.2s silence"
            )
        ser.write(b"S\n")
        ser.flush()
        tel.pump(1.5)
        if last_dist >= 0:
            ok = [s for (t, s) in tel.status_seq if t >= mark + 4.4 and s == "OK"]
            rep.add(
                "PASS" if ok else "FAIL",
                "serial.watchdog_recover",
                "STATUS:OK resumed after valid packet"
                if ok
                else "no STATUS:OK after S",
            )
        else:
            rep.add(
                "SKIP",
                "serial.watchdog_recover",
                "sensor fault makes STATUS stay STOP (fix ultrasonic first)",
            )

        # 7. obstacle gate (telemetry-level): F must be blocked under 15cm
        if getattr(args, "obstacle", False):
            rep.add(*_obstacle_check(ser, tel, getattr(args, "window", 10.0)))

        # 8. motion test (needs --space acknowledgement)
        if getattr(args, "motion", False):
            rep.add(*_motion_check(ser, tel, args))

    finally:
        try:
            ser.write(b"S\n")
            ser.flush()
        except Exception:
            pass
        try:
            ser.close()
        except Exception:
            pass
        print("serial port closed (rover left in STOP)")
    return rep.summary()


def _obstacle_check(ser, tel, window):
    print(
        "OBSTACLE GATE: place an object/hand <15cm in FRONT of the HC-SR04 "
        "NOW (%.0fs window)..." % window
    )
    start = time.time()
    mark = len(tel.status_seq)
    while time.time() - start < window:
        ser.write(b"F120\n")
        ser.flush()
        tel.pump(0.3)
    ser.write(b"S\n")
    ser.flush()
    tel.pump(0.5)
    dists = [d for (t, d) in tel.dist_seq if t >= start and 0 < d < EMERGENCY_CM]
    stops = [s for (t, s) in tel.status_seq[mark:] if s == "STOP"]
    if dists and stops:
        return (
            "PASS",
            "serial.obstacle_gate",
            "DIST=%.1f <15cm while F -> STATUS:STOP" % dists[-1],
        )
    if not dists:
        return (
            "SKIP",
            "serial.obstacle_gate",
            "no reading <15cm seen in window (object not close enough?)",
        )
    return "FAIL", "serial.obstacle_gate", "close DIST seen but no STATUS:STOP"


def _motion_check(ser, tel, args):
    if not getattr(args, "space", False):
        return (
            "SKIP",
            "serial.motion",
            "re-run with --space after clearing the area in front of the rover",
        )
    tel.pump(0.4)
    if tel.dist is None or (0 <= tel.dist < EMERGENCY_CM):
        return (
            "FAIL",
            "serial.motion",
            "blocked: DIST=%s (need clear path >=15cm)" % tel.dist,
        )
    mark = time.time() - tel.t0
    end = time.time() + 2.0
    while time.time() < end:
        ser.write(b"F150\n")
        ser.flush()
        tel.pump(0.4)
    ser.write(b"S\n")
    ser.flush()
    tel.pump(0.6)
    ok = [s for (t, s) in tel.status_seq if mark <= t and s == "OK"]
    if ok:
        return (
            "PASS",
            "serial.motion",
            "drove F150 for 2s with STATUS:OK (wheels must have spun)",
        )
    return "FAIL", "serial.motion", "F150 issued but STATUS never OK"


def cmd_mon(args):
    rep = Report()
    port, _ = pick_port(args.port)
    if port is None:
        rep.add("SKIP", "mon.port", "no board port found")
        return rep.summary()
    ser = _open(port)
    try:
        tel = Telemetry(ser)
        end = time.time() + args.seconds
        print("monitoring %s for %.0fs (Ctrl+C to stop)..." % (port, args.seconds))
        while time.time() < end:
            tel.pump(0.2)
            print(
                "  t=%5.1fs DIST=%s STATUS=%s"
                % (time.time() - tel.t0, tel.dist, tel.status)
            )
        rep.add("PASS", "mon", "%d DIST lines" % len(tel.dist_seq))
    except KeyboardInterrupt:
        rep.add("PASS", "mon", "stopped by user")
    finally:
        try:
            ser.write(b"S\n")
            ser.close()
        except Exception:
            pass
    return rep.summary()


def _tcp_up(host, port, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def cmd_esp32(args):
    import requests

    rep = Report()
    url = str(
        getattr(args, "url", None)
        or _config_value("camera.esp32_url")
        or DEFAULT_STREAM
    )
    m = re.match(r"(http://[^:/]+)(?::(\d+))?", url)
    if not m:
        rep.add("FAIL", "esp32.url", "cannot parse %r" % url)
        return rep.summary()
    host = m.group(1).split("//")[1]
    port = int(m.group(2) or 80)
    base = m.group(1) + (":" + m.group(2) if m.group(2) else "")

    if not _tcp_up(host, port):
        rep.add(
            "FAIL",
            "esp32.reach",
            "%s:%d unreachable - power ESP32, same Wi-Fi, check IP" % (host, port),
        )
        return rep.summary()
    rep.add("PASS", "esp32.reach", "%s:%d" % (host, port))

    try:
        r = requests.get(base + "/", timeout=5)
        rep.add(
            "PASS" if r.status_code == 200 else "FAIL",
            "esp32.root",
            "GET / -> %d" % r.status_code,
        )
    except Exception as exc:
        rep.add("FAIL", "esp32.root", str(exc))
        return rep.summary()

    try:
        with requests.get(url, stream=True, timeout=8) as s:
            ctype = s.headers.get("Content-Type", "")
            if s.status_code != 200 or "multipart/x-mixed-replace" not in ctype:
                rep.add(
                    "FAIL",
                    "esp32.stream",
                    "status=%d content-type=%r" % (s.status_code, ctype),
                )
                return rep.summary()
            rep.add("PASS", "esp32.stream", "multipart stream negotiated")
            raw = b""
            for chunk in s.iter_content(4096):
                raw += chunk
                soi = raw.find(b"\xff\xd8")
                eoi = raw.find(b"\xff\xd9", soi + 2) if soi >= 0 else -1
                if soi >= 0 and eoi >= 0:
                    break
                if len(raw) > 2_000_000:
                    break
            soi = raw.find(b"\xff\xd8")
            eoi = raw.find(b"\xff\xd9", soi + 2) if soi >= 0 else -1
            if soi < 0 or eoi < 0:
                rep.add("FAIL", "esp32.frame", "no complete JPEG in stream")
                return rep.summary()
            jpeg = raw[soi : eoi + 2]
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(jpeg))
            img.load()
            os.makedirs(LOG_DIR, exist_ok=True)
            out = os.path.join(LOG_DIR, "esp32_last_frame.jpg")
            img.save(out)
            rep.add(
                "PASS",
                "esp32.frame",
                "%dx%d JPEG saved -> %s" % (img.width, img.height, out),
            )
    except Exception as exc:
        rep.add("FAIL", "esp32.frame", str(exc))
    return rep.summary()


def cmd_all(args):
    print("== ports ==")
    rc_ports = cmd_ports(args)
    print("\n== serial (safe subset) ==")
    rc_serial = cmd_serial(args)
    print("\n== esp32 ==")
    rc_esp = cmd_esp32(args)
    worst = max(rc_ports, rc_serial, rc_esp)
    print("-" * 60)
    print(
        "ALL: ports=%d serial=%d esp32=%d -> exit %d"
        % (rc_ports, rc_serial, rc_esp, worst)
    )
    return worst


def main(argv=None):
    p = argparse.ArgumentParser(description="Rover hardware-in-the-loop checks")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ports", help="list serial ports and detect the board")

    f = sub.add_parser("flash", help="compile and upload firmware")
    f.add_argument("--target", choices=("uno", "esp32"), default="uno")
    f.add_argument("--port", default=None)
    f.add_argument("--compile-only", action="store_true")

    s = sub.add_parser("serial", help="protocol + safety tests over USB")
    s.add_argument("--port", default=None)
    s.add_argument("--motion", action="store_true", help="also drive the motors")
    s.add_argument("--space", action="store_true", help="area in front is clear")
    s.add_argument("--obstacle", action="store_true", help="run the 15cm gate test")
    s.add_argument("--window", type=float, default=10.0, help="obstacle test seconds")

    m = sub.add_parser("mon", help="live telemetry monitor")
    m.add_argument("--port", default=None)
    m.add_argument("--seconds", type=float, default=10.0)

    e = sub.add_parser("esp32", help="Wi-Fi camera checks")
    e.add_argument("--url", default=None, help="stream URL (default: config.yaml)")

    sub.add_parser("all", help="ports + safe serial + esp32")

    args = p.parse_args(argv)
    handlers = {
        "ports": cmd_ports,
        "flash": cmd_flash,
        "serial": cmd_serial,
        "mon": cmd_mon,
        "esp32": cmd_esp32,
        "all": cmd_all,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
