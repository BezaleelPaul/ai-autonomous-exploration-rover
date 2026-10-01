"""Camera-vision enhancement for inference frames (display stays raw).

Pipeline: auto white-balance (gray-world) -> CLAHE contrast on L-channel ->
optional sharpen. All cheap on CPU (~5-15ms at 640x480). Denoise exists but
defaults OFF (fastNlMeans is ~200ms+ on CPU — enable only if grain dominates).
"""

from __future__ import annotations

import numpy as np


def gray_world_balance(frame: np.ndarray) -> np.ndarray:
    b, g, r = frame[:, :, 0].mean(), frame[:, :, 1].mean(), frame[:, :, 2].mean()
    avg = (b + g + r) / 3.0
    out = frame.astype(np.float32)
    for i, m in enumerate((b, g, r)):
        if m > 1e-3:
            out[:, :, i] *= avg / m
    return out.clip(0, 255).astype(np.uint8)


def enhance_for_inference(
    frame: np.ndarray,
    clahe: bool = True,
    sharpen: bool = True,
    denoise: bool = False,
    clip_limit: float = 2.0,
) -> np.ndarray:
    try:
        import cv2
    except ImportError:
        return frame
    try:
        out = gray_world_balance(frame)
        if clahe:
            lab = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)
            lightness, a, b = cv2.split(lab)
            lightness = cv2.createCLAHE(
                clipLimit=clip_limit, tileGridSize=(8, 8)
            ).apply(lightness)
            out = cv2.cvtColor(cv2.merge((lightness, a, b)), cv2.COLOR_LAB2BGR)
        if denoise:
            out = cv2.fastNlMeansDenoisingColored(out, None, 3, 3, 7, 21)
        if sharpen:
            blur = cv2.GaussianBlur(out, (0, 0), 2.0)
            out = cv2.addWeighted(out, 1.4, blur, -0.4, 0)
        return out
    except Exception:
        return frame
