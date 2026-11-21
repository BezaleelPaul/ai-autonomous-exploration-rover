"""Application configuration loader for the AI Rover laptop tier."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .pilot import PilotConfig
from .steering import ZoneConfig


@dataclass
class AppConfig:
    gateway: str = "http://192.168.4.1"
    camera: str = "http://192.168.4.2:8080/video"
    weights: str = "models/rover24.onnx"
    imgsz: int = 320
    conf: float = 0.35
    device: str = "cpu"
    classes: list[str] = field(default_factory=list)
    max_fps: float = 5.0
    heartbeat_s: float = 0.2
    max_frame_age_s: float = 1.5
    stream_port: int = 8080
    dry_run: bool = False
    zones: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str = "config/rover.json") -> AppConfig:
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, path: Path | str = "config/rover.json") -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def to_pilot_config(self) -> PilotConfig:
        return PilotConfig(
            max_fps=self.max_fps,
            heartbeat_s=self.heartbeat_s,
            max_frame_age_s=self.max_frame_age_s,
            dry_run=self.dry_run,
        )

    def to_zone_config(self) -> ZoneConfig:
        clean_zones = {k: v for k, v in self.zones.items() if k in ZoneConfig.__dataclass_fields__}
        return ZoneConfig(**clean_zones)
