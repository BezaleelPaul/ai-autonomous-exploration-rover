"""Tests for High-Fidelity Differential Drive Kinematics and Sonar Simulator."""

from __future__ import annotations

import math
import pytest

from software.simulation.rover_physics import DifferentialDriveSimulator, PhysicsConfig


def test_motor_deadband_enforcement():
    sim = DifferentialDriveSimulator()

    # Below stiction PWM (60), wheel velocity must be strictly 0
    assert sim.pwm_to_wheel_speed(0) == 0.0
    assert sim.pwm_to_wheel_speed(45) == 0.0
    assert sim.pwm_to_wheel_speed(-59) == 0.0

    # At or above stiction PWM, speed must be non-zero and signed
    speed_pos = sim.pwm_to_wheel_speed(150)
    speed_neg = sim.pwm_to_wheel_speed(-150)
    assert speed_pos > 0.0
    assert speed_neg == -speed_pos


def test_battery_voltage_scaling():
    cfg = PhysicsConfig(nominal_battery_v=7.4)
    sim = DifferentialDriveSimulator(cfg)

    sim.state.battery_v = 8.4  # Full charge
    w_full = sim.pwm_to_wheel_speed(200)

    sim.state.battery_v = 6.4  # Depleted charge
    w_depleted = sim.pwm_to_wheel_speed(200)

    assert w_full > w_depleted


def test_forward_kinematics_and_encoders():
    sim = DifferentialDriveSimulator()

    # Step forward for 1 second at PWM 180
    sim.step(pwm_left=180, pwm_right=180, dt_s=1.0)

    # Should translate in +X direction with ~0 rotation
    assert sim.state.x > 0.1
    assert abs(sim.state.y) < 1e-4
    assert abs(sim.state.theta) < 1e-4
    assert sim.state.ticks_left > 0
    assert sim.state.ticks_left == sim.state.ticks_right


def test_turning_kinematics():
    sim = DifferentialDriveSimulator()

    # Pivot turn: left reverse, right forward
    sim.step(pwm_left=-180, pwm_right=180, dt_s=0.5)

    assert sim.state.w_angular > 0.0
    assert sim.state.theta > 0.0


def test_sonar_raycast_direct_hit():
    sim = DifferentialDriveSimulator()
    # Place obstacle wall at x = 1.0 m, spanning y in [-1, 1]
    sim.add_box_obstacle(cx=1.0, cy=0.0, width=0.1, height=2.0)

    dist = sim.raycast_sonar()
    assert dist is not None
    assert 0.9 <= dist <= 1.05


def test_sonar_specular_miss():
    sim = DifferentialDriveSimulator()
    # Place wall nearly grazing the forward ray (incident angle > 45 deg cutoff)
    from software.simulation.rover_physics import ObstacleSegment
    sim.obstacles.append(ObstacleSegment(x1=0.5, y1=0.1, x2=2.5, y2=0.3, is_specular=True))

    # Steep incidence angle causes acoustic specular bounce away
    dist = sim.raycast_sonar()
    assert dist is None

