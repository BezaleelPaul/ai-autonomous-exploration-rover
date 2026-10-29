"""Bench sender: drive the Arduino safety executive over any COM port.

Bring-up helper for the two-tier stack — verifies the Bluetooth bridge (or a
direct USB link) without running the camera/YOLO tier::

    python -m software.perception_node.bench COM5 F --listen 5
    python -m software.perception_node.bench COM4 S

Always sends a final ``S`` before closing, mirroring the fail-safe contract.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from software.hardware.arduino_serial import VALID_COMMANDS

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Send F/B/L/R/S to the rover over a COM port and print telemetry")
    )
    parser.add_argument("port", help="COM port, e.g. COM5 (BT SPP) or COM3 (USB)")
    parser.add_argument(
        "command",
        nargs="?",
        default=None,
        help=f"one of {'/'.join(sorted(VALID_COMMANDS))}; omit to only listen",
    )
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument(
        "--listen",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="keep the port open for SECONDS, re-sending the command while printing telemetry",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="seconds between re-sends while listening (stay under the Arduino 3 s watchdog)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def _open_serial(port: str, baud_rate: int, timeout_s: float = 0.25):
    import serial

    return serial.Serial(port=port, baudrate=baud_rate, timeout=timeout_s)


def send_command(
    port: str,
    command: str | None = None,
    *,
    baud_rate: int = 9600,
    listen_s: float = 0.0,
    interval_s: float = 1.0,
    on_line: Callable[[str], None] = print,
    monotonic: Callable[[], float] = time.monotonic,
) -> bool:
    """Open the port, send ``command``, optionally stream telemetry.

    ``command=None`` listens without transmitting (never disturb a phone
    client that is actively driving the rover). A sent command is always
    followed by a final ``S`` before closing.
    """
    cmd = (command or "").strip().upper()
    if cmd and cmd not in VALID_COMMANDS:
        logger.error(
            "invalid command %r; expected one of %s", command, sorted(VALID_COMMANDS)
        )
        return False
    if interval_s <= 0:
        interval_s = 0.1
    try:
        link = _open_serial(port, baud_rate)
    except Exception as exc:
        logger.error("cannot open %s: %s", port, exc)
        return False
    try:
        if cmd:
            link.write(cmd.encode("ascii"))
            link.flush()
            on_line(f"sent {cmd} -> {port} @ {baud_rate}")
        else:
            on_line(f"listening on {port} @ {baud_rate} (nothing sent)")
        if listen_s > 0:
            deadline = monotonic() + listen_s
            next_send = monotonic() + interval_s
            while monotonic() < deadline:
                raw = link.readline()
                if raw:
                    text = raw.decode("ascii", "replace").strip()
                    text = text.encode("ascii", "replace").decode("ascii")
                    if text:
                        on_line(f"rover: {text}")
                if cmd and monotonic() >= next_send:
                    link.write(cmd.encode("ascii"))
                    link.flush()
                    next_send = monotonic() + interval_s
        return True
    except Exception as exc:
        logger.error("serial write failed: %s", exc)
        return False
    finally:
        if cmd:
            with contextlib.suppress(Exception):
                link.write(b"S")
                link.flush()
        with contextlib.suppress(Exception):
            link.close()


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    ok = send_command(
        args.port,
        args.command,
        baud_rate=args.baud,
        listen_s=max(0.0, args.listen) or (3.0 if args.command is None else 0.0),
        interval_s=args.interval,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
