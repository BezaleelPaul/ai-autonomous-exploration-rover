"""Interactive calibration guide: zones, ultrasonic, widths.
Usage: python scripts/calibration.py
"""

print("""
CALIBRATION GUIDE
1. Rover width: measure widest point (wheels) in cm -> config/thresholds.yaml gap.rover_width_cm
2. Ultrasonic: place flat wall at 15/30/50cm, compare DIST: readings, adjust emergency_stop_cm/slow_cm.
3. Vision zones: hold target left/center/right, note center_x_norm via logs, adjust left_max/center_max.
4. Approach stop: drive toward bottle, note bbox width_ratio when ~20cm away -> target_approach.stop_width_ratio.
5. Motors: time a 90-degree turn -> navigation turning_duration_s. Repeat 3x, use median.
See docs for details.
""")
