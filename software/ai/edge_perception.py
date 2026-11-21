"""Edge Perception and Optical Enhancement Engine for Embedded Rover Vision.

Implements:
1. Low-Light Detection & Auto-Flash Trigger:
   - Measures frame luminance; if below safety threshold (e.g. 40 lux equivalent),
     flags flash LED activation (ESP32 GPIO 4) and applies dynamic gamma/CLAHE enhancement.
2. Lens Distortion Rectification:
   - Rectifies barrel distortion common in wide-angle OV2640 camera modules.
3. Resilient Multi-Backend Vision Runner:
   - Seamlessly executes deep learning object detection with sub-20ms fallback
     to deterministic HSV color-blob centroid tracking.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Sequence

import cv2
import numpy as np

from software.ai.detection import Detection


@dataclass
class OpticalConfig:
    low_light_luma_threshold: float = 40.0  # Mean luminance threshold triggering night mode
    gamma_boost: float = 0.55               # Non-linear gamma curve for shadow lifting
    clahe_clip_limit: float = 2.5           # Adaptive histogram equalization contrast limit
    clahe_grid_size: tuple[int, int] = (8, 8)
    camera_fov_deg: float = 65.0            # OV2640 standard lens horizontal FOV
    k1_distortion: float = -0.15            # Barrel distortion coefficient (radial)
    k2_distortion: float = 0.02


@dataclass
class PerceptionOutput:
    detections: list[Detection]
    processed_frame: np.ndarray
    is_low_light: bool
    flash_led_active: bool
    mean_luminance: float
    inference_latency_ms: float
    backend_used: str  # "yolo" | "color_blob" | "heuristic"


class EdgePerceptionPipeline:
    """Pre-processes raw ESP32-CAM video frames and executes robust multi-modal perception."""

    def __init__(self, config: OpticalConfig | None = None) -> None:
        self.cfg = config or OpticalConfig()
        self._clahe = cv2.createCLAHE(
            clipLimit=self.cfg.clahe_clip_limit,
            tileGridSize=self.cfg.clahe_grid_size,
        )

        # Precompute gamma lookup table
        inv_gamma = 1.0 / self.cfg.gamma_boost
        self._gamma_lut = np.array(
            [((i / 255.0) ** self.cfg.gamma_boost) * 255 for i in range(256)],
            dtype=np.uint8,
        )

    def assess_lighting(self, frame_bgr: np.ndarray) -> tuple[float, bool]:
        """Compute average image luminance and determine if low-light condition is present."""
        if frame_bgr is None or frame_bgr.size == 0:
            return 0.0, True

        # Quick luminance estimation using standard rec601 weights: Y = 0.299 R + 0.587 G + 0.114 B
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        mean_luma = float(np.mean(gray))
        is_low_light = mean_luma < self.cfg.low_light_luma_threshold
        return mean_luma, is_low_light

    def enhance_low_light(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Apply gamma correction and CLAHE in LAB color space to recover shadow details."""
        # Convert to LAB to equalize luminance without color shift
        lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
        l_chan, a_chan, b_chan = cv2.split(lab)

        # Apply gamma expansion then CLAHE
        l_gamma = cv2.LUT(l_chan, self._gamma_lut)
        l_enhanced = self._clahe.apply(l_gamma)

        enhanced_lab = cv2.merge((l_enhanced, a_chan, b_chan))
        return cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    def rectify_lens_distortion(self, frame_bgr: np.ndarray) -> np.ndarray:
        """Correct barrel distortion from wide-angle OV2640 camera lenses."""
        h, w = frame_bgr.shape[:2]
        focal_length = w / (2.0 * math.tan(math.radians(self.cfg.camera_fov_deg / 2.0)))
        cx, cy = w / 2.0, h / 2.0

        camera_matrix = np.array(
            [[focal_length, 0.0, cx], [0.0, focal_length, cy], [0.0, 0.0, 1.0]],
            dtype=np.float32,
        )
        dist_coeffs = np.array(
            [self.cfg.k1_distortion, self.cfg.k2_distortion, 0.0, 0.0],
            dtype=np.float32,
        )

        return cv2.undistort(frame_bgr, camera_matrix, dist_coeffs)

    def detect_color_blob(
        self,
        frame_bgr: np.ndarray,
        hsv_lower: tuple[int, int, int] = (15, 100, 100),
        hsv_upper: tuple[int, int, int] = (35, 255, 255),
        target_class: str = "beacon",
    ) -> list[Detection]:
        """Fallback deterministic HSV color-blob detector (runs in < 5ms without neural weights)."""
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(hsv_lower), np.array(hsv_upper))

        # Morphological clean
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[Detection] = []

        h, w = frame_bgr.shape[:2]
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 150.0:  # Minimum blob threshold
                continue
            bx, by, bw, bh = cv2.boundingRect(cnt)
            aspect_ratio = float(bw) / float(bh) if bh > 0 else 0.0
            if 0.2 < aspect_ratio < 5.0:
                # Confidence proportional to fill density
                density = min(1.0, area / (bw * bh))
                detections.append(
                    Detection(
                        class_name=target_class,
                        confidence=float(0.70 + 0.25 * density),
                        x1=float(bx),
                        y1=float(by),
                        x2=float(bx + bw),
                        y2=float(by + bh),
                        track_id=None,
                    )
                )

        return sorted(detections, key=lambda d: d.width * d.height, reverse=True)

    def process(
        self,
        raw_frame: np.ndarray,
        primary_detector_fn: Any | None = None,
    ) -> PerceptionOutput:
        """Full perception pass: lighting assessment -> enhancement -> rectification -> detection."""
        t_start = time.perf_counter()

        # Step 1: Lighting Assessment
        mean_luma, is_low_light = self.assess_lighting(raw_frame)
        active_frame = raw_frame

        # Step 2: Night Mode Enhancement
        flash_active = False
        if is_low_light:
            flash_active = True
            active_frame = self.enhance_low_light(active_frame)

        # Step 3: Lens Rectification
        rectified_frame = self.rectify_lens_distortion(active_frame)

        # Step 4: Primary Detection with Fallback
        detections: list[Detection] = []
        backend = "heuristic"

        if primary_detector_fn is not None:
            try:
                detections = primary_detector_fn(rectified_frame)
                backend = "yolo"
            except Exception:
                # Fallback to color blob tracking if neural inference fails
                detections = self.detect_color_blob(rectified_frame)
                backend = "color_blob"
        else:
            detections = self.detect_color_blob(rectified_frame)
            backend = "color_blob"

        dt_ms = (time.perf_counter() - t_start) * 1000.0

        return PerceptionOutput(
            detections=detections,
            processed_frame=rectified_frame,
            is_low_light=is_low_light,
            flash_led_active=flash_active,
            mean_luminance=mean_luma,
            inference_latency_ms=dt_ms,
            backend_used=backend,
        )
