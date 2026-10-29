"""Visual HUD: three steering zones, target box, proximity bar, command badge."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from software.ai.detection import Detection
from software.perception_node.zones import SteeringDecision, Zone

IDLE_COLOR = (90, 90, 90)
ACTIVE_COLOR = (0, 220, 255)
BOX_COLOR = (0, 255, 0)
STOP_COLOR = (0, 0, 255)
GO_COLOR = (0, 255, 0)
PANEL_COLOR = (20, 20, 20)

ZONE_LABELS: dict[Zone, str] = {
    Zone.LEFT: "LEFT",
    Zone.CENTER: "CENTER",
    Zone.RIGHT: "RIGHT",
}


def _zone_span(
    width: int, zone: Zone, left_boundary: float, center_boundary: float
) -> tuple[int, int]:
    if zone is Zone.LEFT:
        return 0, int(width * left_boundary)
    if zone is Zone.CENTER:
        return int(width * left_boundary), int(width * center_boundary)
    return int(width * center_boundary), width


def draw_hud(
    frame: np.ndarray,
    decision: SteeringDecision,
    detections: Iterable[Detection] = (),
    *,
    fps: float = 0.0,
    serial_ok: bool = True,
    stream_ok: bool = True,
    left_boundary: float = 0.33,
    center_boundary: float = 0.66,
    stop_area_ratio: float = 0.35,
    target: str = "person",
) -> np.ndarray:
    """Return a copy of ``frame`` annotated with zones, boxes and status."""
    import cv2

    img = np.ascontiguousarray(frame).copy()
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    height, width = img.shape[:2]
    x_left = int(width * left_boundary)
    x_right = int(width * center_boundary)

    if decision.zone is not None:
        x0, x1 = _zone_span(width, decision.zone, left_boundary, center_boundary)
        overlay = img.copy()
        cv2.rectangle(overlay, (x0, 0), (max(x0 + 1, x1 - 1), height), ACTIVE_COLOR, -1)
        img = cv2.addWeighted(overlay, 0.12, img, 0.88, 0)

    for x in (x_left, x_right):
        cv2.line(img, (x, 0), (x, height), IDLE_COLOR, 1, cv2.LINE_AA)
    for zone in (Zone.LEFT, Zone.CENTER, Zone.RIGHT):
        x0, x1 = _zone_span(width, zone, left_boundary, center_boundary)
        color = ACTIVE_COLOR if zone is decision.zone else IDLE_COLOR
        cv2.putText(
            img,
            zone.value,
            (x0 + 8, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )

    for det in detections:
        p1 = (int(det.x1), int(det.y1))
        p2 = (int(det.x2), int(det.y2))
        cv2.rectangle(img, p1, p2, BOX_COLOR, 2)
        label = f"{det.class_name} {det.confidence:.2f}"
        cv2.putText(
            img,
            label,
            (p1[0], max(16, p1[1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            BOX_COLOR,
            2,
            cv2.LINE_AA,
        )

    bar_w = max(80, width // 3)
    bar_h = 14
    x0, y0 = 12, height - 58
    cv2.rectangle(img, (x0, y0), (x0 + bar_w, y0 + bar_h), PANEL_COLOR, -1)
    fill = (
        0.0 if stop_area_ratio <= 0 else min(1.0, decision.area_ratio / stop_area_ratio)
    )
    fill_color = STOP_COLOR if fill >= 1.0 else GO_COLOR
    cv2.rectangle(img, (x0, y0), (x0 + int(bar_w * fill), y0 + bar_h), fill_color, -1)
    cv2.rectangle(img, (x0, y0), (x0 + bar_w, y0 + bar_h), IDLE_COLOR, 1)
    cv2.putText(
        img,
        f"PROX {decision.area_ratio * 100:4.1f}% / {stop_area_ratio * 100:.0f}%",
        (x0 + bar_w + 10, y0 + bar_h + 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        IDLE_COLOR,
        1,
        cv2.LINE_AA,
    )

    badge = f"CMD {decision.command}"
    badge_color = STOP_COLOR if decision.command == "S" else GO_COLOR
    cv2.rectangle(img, (12, 12), (150, 56), PANEL_COLOR, -1)
    cv2.rectangle(img, (12, 12), (150, 56), badge_color, 2)
    cv2.putText(
        img,
        badge,
        (22, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        badge_color,
        2,
        cv2.LINE_AA,
    )

    status = f"FPS {fps:4.1f} | target {target} | serial {'OK' if serial_ok else 'RETRY'} | stream {'OK' if stream_ok else 'LOST'}"
    cv2.putText(
        img,
        status,
        (12, height - 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        IDLE_COLOR,
        1,
        cv2.LINE_AA,
    )
    if decision.target_present:
        zone_text = decision.zone.value if decision.zone is not None else "CLOSE"
        detail = f"{zone_text} | {decision.reason}"
    else:
        detail = decision.reason
    cv2.putText(
        img,
        detail[: width // 9],
        (12, 76),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        ACTIVE_COLOR,
        1,
        cv2.LINE_AA,
    )
    return img
