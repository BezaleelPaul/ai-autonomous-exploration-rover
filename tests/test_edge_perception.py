"""Tests for Edge Perception, Low-Light Enhancement, and Rectification."""

from __future__ import annotations

import numpy as np
import pytest

from software.ai.edge_perception import EdgePerceptionPipeline, OpticalConfig


def test_lighting_assessment_and_enhancement():
    pipe = EdgePerceptionPipeline()

    # Synthesize dark image (mean value ~15)
    dark_frame = np.full((120, 160, 3), 15, dtype=np.uint8)
    luma, is_low_light = pipe.assess_lighting(dark_frame)
    assert is_low_light
    assert luma < pipe.cfg.low_light_luma_threshold

    # Apply low light enhancement
    enhanced = pipe.enhance_low_light(dark_frame)
    luma_enh, _ = pipe.assess_lighting(enhanced)
    # Enhanced frame must have elevated luminance
    assert luma_enh > luma


def test_lens_rectification_shape():
    pipe = EdgePerceptionPipeline()
    frame = np.zeros((240, 320, 3), dtype=np.uint8)

    rectified = pipe.rectify_lens_distortion(frame)
    assert rectified.shape == frame.shape


def test_color_blob_detection():
    pipe = EdgePerceptionPipeline()

    # Synthesize bright yellow/beacon block on black background
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    # BGR for saturated yellow: [0, 255, 255]
    frame[50:110, 80:160] = [0, 255, 255]

    detections = pipe.detect_color_blob(
        frame,
        hsv_lower=(20, 100, 100),
        hsv_upper=(35, 255, 255),
        target_class="beacon",
    )

    assert len(detections) >= 1
    top = detections[0]
    assert top.class_name == "beacon"
    assert top.confidence >= 0.70
    bx1, by1, bx2, by2 = top.x1, top.y1, top.x2, top.y2
    assert 75 <= bx1 <= 85
    assert 45 <= by1 <= 55


def test_full_pipeline_process_fallback():
    pipe = EdgePerceptionPipeline()
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    frame[40:100, 60:120] = [0, 255, 255]

    output = pipe.process(frame, primary_detector_fn=None)
    assert output.backend_used == "color_blob"
    assert output.processed_frame.shape == frame.shape
    assert len(output.detections) >= 1
