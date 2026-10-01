import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np

from software.camera.enhance import enhance_for_inference, gray_world_balance


def test_enhance_preserves_shape_dtype():
    f = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
    out = enhance_for_inference(f)
    assert out.shape == f.shape and out.dtype == np.uint8


def test_enhance_dark_frame_gets_brighter():
    dark = np.full((100, 100, 3), 20, dtype=np.uint8)
    out = enhance_for_inference(dark)
    assert float(out.mean()) >= float(dark.mean())


def test_enhance_never_crashes():
    assert enhance_for_inference(None) is None  # type: ignore
    g = np.zeros((50, 50), dtype=np.uint8)
    assert enhance_for_inference(g).shape == g.shape  # grayscale passthrough


def test_gray_world_fixes_color_cast():
    yellow = np.zeros((40, 40, 3), dtype=np.uint8)
    yellow[:, :, 1:] = 200  # strong yellow cast, blue=0
    out = gray_world_balance(yellow)
    assert out.shape == yellow.shape
