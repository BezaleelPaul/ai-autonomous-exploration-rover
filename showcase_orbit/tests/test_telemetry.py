"""
Unit and Integration Tests for AeroPulse Orbital Deck
Tests kinematics calculations, API response schemas, and waypoint management.
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from server import app, state, update_simulation

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_api_health(client):
    """Verify health check endpoint returns 200 and healthy status."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["port"] == 5055

def test_telemetry_schema(client):
    """Verify telemetry payload contains all required subsystem fields."""
    res = client.get("/api/telemetry")
    assert res.status_code == 200
    data = res.get_json()
    assert "battery" in data
    assert "soc_pct" in data["battery"]
    assert "attitude" in data
    assert "pitch_deg" in data["attitude"]
    assert "kinematics" in data
    assert len(data["kinematics"]["motor_rpm"]) == 6
    assert "vision" in data
    assert len(data["vision"]["detections"]) > 0

def test_simulation_kinematics():
    """Verify physics kinematics calculations update dynamically."""
    initial_pitch = state["attitude"]["pitch_deg"]
    update_simulation()
    assert isinstance(state["attitude"]["pitch_deg"], float)
    assert 0.0 <= state["attitude"]["yaw_deg"] <= 360.0
    assert state["battery"]["voltage"] > 20.0

def test_waypoint_dispatch(client):
    """Verify queuing a new navigation waypoint increments queue."""
    initial_count = len(state["waypoints"])
    payload = {"x": 35.4, "y": 42.1}
    res = client.post("/api/nav/dispatch", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["waypoint"]["x"] == 35.4
    assert len(state["waypoints"]) == initial_count + 1

def test_mode_switch(client):
    """Verify emergency stop / hold and autonomous mode switching."""
    res = client.post("/api/mode", json={"mode": "HOLD"})
    assert res.status_code == 200
    assert res.get_json()["mode"] == "HOLD"
    assert state["mode"] == "HOLD"

    res_auto = client.post("/api/mode", json={"mode": "AUTONOMOUS"})
    assert res_auto.status_code == 200
    assert res_auto.get_json()["mode"] == "AUTONOMOUS"
    assert state["mode"] == "AUTONOMOUS"
