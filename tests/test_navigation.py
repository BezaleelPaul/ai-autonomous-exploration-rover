import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from software.ai.detection import Detection
from software.control.steering import SearchRotation
from software.perception.scene_analyzer import SceneAnalyzer


def test_search_finds_target():
    s = SearchRotation(timeout_s=30.0, max_rotations=2, rotation_duration_s=20.0)
    s.start(now=0.0)
    cmd, done, _ = s.update(False, now=5.0)
    assert cmd == "R" and not done
    cmd, done, _ = s.update(True, now=6.0)
    assert done and cmd == "S"


def test_search_timeout():
    s = SearchRotation(timeout_s=10.0, max_rotations=5, rotation_duration_s=20.0)
    s.start(now=0.0)
    cmd, done, msg = s.update(False, now=11.0)
    assert done and cmd == "S" and "timeout" in msg


def test_search_max_rotations():
    s = SearchRotation(timeout_s=100.0, max_rotations=1, rotation_duration_s=10.0)
    s.start(now=0.0)
    cmd, done, _ = s.update(False, now=11.0)
    assert done and cmd == "S"


def test_scan360_single_rotation_reports_not_found():
    s = SearchRotation(timeout_s=25.0, max_rotations=1, rotation_duration_s=20.0)
    s.start(now=0.0)
    _cmd, done, _ = s.update(False, now=21.0)
    assert done  # full rotation elapsed


def test_scene_very_close_flag():
    a = SceneAnalyzer(stop_width_ratio=0.45)
    d = Detection("bottle", 0.9, 0, 0, 400, 200)  # width 400/640 = 0.625
    r = a.analyze(d, [d], 640.0)
    assert r.very_close and r.position in ("LEFT", "CENTER", "RIGHT")
    r2 = a.analyze(None, [], 640.0)
    assert r2.position == "NONE"


def test_scene_center_error_feeds_psteering():
    a = SceneAnalyzer()
    d = Detection("bottle", 0.9, 0, 0, 200, 200)  # cx = 100/640 = 0.15625
    r = a.analyze(d, [d], 640.0)
    assert abs(r.center_error - (100 / 640 - 0.5)) < 1e-9
    assert r.center_error < 0  # target left of frame center
    r2 = a.analyze(None, [], 640.0)
    assert r2.center_error == 0.0  # no target -> no steering input
