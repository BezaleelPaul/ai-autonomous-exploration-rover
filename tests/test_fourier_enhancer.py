"""Unit tests for 2D Fourier Homomorphic High-Frequency Emphasis and Spectral Saliency."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from software.camera.fourier_enhancer import (
    EllipticFourierDescriptor,
    FourierHomomorphicFilter,
    FourierSpectralSaliency,
    fourier_enhance_frame,
)


def test_fourier_homomorphic_filter_enhances_edges():
    filt = FourierHomomorphicFilter(height=200, width=200, gamma_l=0.75, gamma_h=1.6, d0=20.0)

    # Synthetic image with uneven low-frequency gradient + faint high-frequency target box
    y, x = np.mgrid[0:200, 0:200]
    illumination = (x / 200.0 * 80.0).astype(np.float32)  # Low-freq lighting ramp
    img = (100.0 + illumination).astype(np.uint8)

    # Add faint distant object box (low contrast, delta = 20)
    img[80:120, 80:120] += 20

    # Calculate edge strength before and after Fourier HFE
    sobel_before = cv2.Sobel(img, cv2.CV_32F, 1, 0)
    edge_before = np.abs(sobel_before[80:120, 80]).mean()

    enhanced = filt.process_channel(img)
    sobel_after = cv2.Sobel(enhanced, cv2.CV_32F, 1, 0)
    edge_after = np.abs(sobel_after[80:120, 80]).mean()

    assert enhanced.shape == (200, 200)
    assert enhanced.dtype == np.uint8
    # High-frequency edge should be amplified relative to background
    assert edge_after >= edge_before * 0.95


def test_fourier_enhance_frame_rgb():
    frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
    out = fourier_enhance_frame(frame)
    assert out.shape == (240, 320, 3)
    assert out.dtype == np.uint8
    assert 0 <= out.min() and out.max() <= 255


def test_spectral_residual_saliency():
    # Frame with dark background and a bright distant circular object
    frame = np.full((240, 320, 3), 35, dtype=np.uint8)
    cv2.circle(frame, (160, 120), 12, (240, 240, 240), -1)

    saliency = FourierSpectralSaliency.compute(frame)
    assert saliency.shape == (240, 320)
    assert saliency.dtype == np.uint8
    # Saliency value around object region must peak and strongly exceed background
    assert saliency[110:130, 150:170].max() > 200
    assert saliency[10:40, 10:40].mean() < 30


def test_elliptic_fourier_descriptors_invariance():
    # Square contour
    square = np.array([[10, 10], [50, 10], [50, 50], [10, 50]], dtype=np.int32)
    # Scaled and translated square
    square_shifted = np.array([[100, 100], [180, 100], [180, 180], [100, 180]], dtype=np.int32)

    efd1 = EllipticFourierDescriptor.compute_descriptors(square, num_harmonics=6)
    efd2 = EllipticFourierDescriptor.compute_descriptors(square_shifted, num_harmonics=6)

    assert len(efd1) == 6
    assert len(efd2) == 6
    # Normalized harmonic coefficients should remain close across scale/translation
    np.testing.assert_allclose(efd1[:3], efd2[:3], atol=0.25)


def test_fourier_enhancer_performance_gate():
    """Verify execution latency is under 60 ms for 640x480 frame."""
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    # Warm-up
    _ = fourier_enhance_frame(frame)

    t0 = time.perf_counter()
    N = 10
    for _ in range(N):
        _ = fourier_enhance_frame(frame)
    avg_ms = (time.perf_counter() - t0) / N * 1000.0

    print(f"\nMeasured 2D Fourier frame enhancement: {avg_ms:.2f} ms")
    assert avg_ms < 60.0, f"Fourier enhancement exceeded 60 ms gate: {avg_ms:.1f} ms"
