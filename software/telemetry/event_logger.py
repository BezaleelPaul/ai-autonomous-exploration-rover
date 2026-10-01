"""Structured event logging for research data collection."""

from __future__ import annotations

import csv
import logging
from pathlib import Path


class EventLogger:
    def __init__(self, log_dir: str = "logs", level: str = "INFO"):
        self.dir = Path(log_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.dir / "events.csv"
        self._init_csv()
        lvl = getattr(logging, level.upper(), logging.INFO)
        logging.basicConfig(level=lvl, format="%(asctime)s %(levelname)s %(message)s")

    def _init_csv(self) -> None:
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(
                    [
                        "timestamp",
                        "mode",
                        "target",
                        "confidence",
                        "position",
                        "distance_cm",
                        "decision",
                        "safety",
                        "infer_ms",
                        "fps",
                    ]
                )

    def log_event(
        self,
        mode: str,
        target: str = "-",
        confidence: float = 0.0,
        position: str = "-",
        distance_cm: float | None = None,
        decision: str = "S",
        safety: str = "-",
        infer_ms: float = 0.0,
        fps: float = 0.0,
    ) -> None:
        import datetime

        ts = datetime.datetime.now().isoformat(timespec="seconds")
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                [
                    ts,
                    mode,
                    target,
                    round(confidence, 3),
                    position,
                    distance_cm,
                    decision,
                    safety,
                    round(infer_ms, 1),
                    round(fps, 1),
                ]
            )
        logging.info(
            f"{ts} TARGET={target} CONF={confidence:.2f} POS={position} "
            f"DIST={distance_cm} DEC={decision} SAFETY={safety}"
        )

    def log_text(self, msg: str) -> None:
        logging.info(msg)
