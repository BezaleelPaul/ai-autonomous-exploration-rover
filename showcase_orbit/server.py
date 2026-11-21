#!/usr/bin/env python3
"""
AeroPulse Orbital Deck — Telemetry & Planetary Kinematics Server
Port: 5055
Provides real-time telemetry, simulated YOLOv11 perception, and waypoint dispatch.
"""
import os
import time
import math
import json
import random
from flask import Flask, render_template, jsonify, request, Response

app = Flask(__name__, template_folder="templates", static_folder="static")

# Rover State Store
state = {
    "sol": 342,
    "mission_time": 0.0,
    "mode": "AUTONOMOUS",  # AUTONOMOUS | MANUAL | HOLD
    "battery": {
        "soc_pct": 94.2,
        "voltage": 28.4,
        "current_draw": 3.8,
        "temp_c": 22.4
    },
    "attitude": {
        "pitch_deg": 1.2,
        "roll_deg": -0.8,
        "yaw_deg": 142.5
    },
    "kinematics": {
        "linear_vel": 0.45,  # m/s
        "angular_vel": 0.02, # rad/s
        "motor_rpm": [120, 118, 122, 119, 121, 120]
    },
    "vision": {
        "detections": [
            {"id": 1, "class": "crater_rim", "confidence": 0.94, "bbox": [120, 80, 240, 180], "dist_m": 4.2},
            {"id": 2, "class": "basalt_rock", "confidence": 0.89, "bbox": [320, 210, 390, 290], "dist_m": 2.1},
            {"id": 3, "class": "sample_target", "confidence": 0.97, "bbox": [480, 150, 530, 200], "dist_m": 6.8}
        ],
        "fps": 60.0,
        "inference_ms": 14.8
    },
    "waypoints": [
        {"x": 12.4, "y": 8.2, "status": "REACHED"},
        {"x": 18.9, "y": 14.5, "status": "ACTIVE"},
        {"x": 26.0, "y": 21.0, "status": "QUEUED"}
    ]
}

def update_simulation():
    """Generates continuous physical telemetry updates with sine/noise variations."""
    t = time.time()
    state["mission_time"] = round(t % 86400, 1)
    
    # Smooth attitude wobble
    state["attitude"]["pitch_deg"] = round(2.5 * math.sin(t * 0.4) + random.uniform(-0.1, 0.1), 2)
    state["attitude"]["roll_deg"] = round(1.8 * math.cos(t * 0.3) + random.uniform(-0.1, 0.1), 2)
    state["attitude"]["yaw_deg"] = round((state["attitude"]["yaw_deg"] + 0.15) % 360, 2)
    
    # Battery slow drain simulation
    state["battery"]["voltage"] = round(28.0 + 0.5 * math.sin(t * 0.05), 2)
    state["battery"]["current_draw"] = round(3.5 + random.uniform(0.1, 0.4), 2)
    
    # Dynamic motor RPM jitter
    base_rpm = 120 if state["mode"] == "AUTONOMOUS" else 0
    state["kinematics"]["motor_rpm"] = [
        int(base_rpm + random.randint(-4, 4)) for _ in range(6)
    ]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "service": "aeropulse-cockpit", "port": 5055, "mode": state["mode"]})

@app.route("/api/telemetry")
def api_telemetry():
    update_simulation()
    return jsonify(state)

@app.route("/api/nav/dispatch", methods=["POST"])
def api_dispatch():
    data = request.get_json() or {}
    x = float(data.get("x", random.uniform(20.0, 50.0)))
    y = float(data.get("y", random.uniform(20.0, 50.0)))
    new_wp = {"x": round(x, 2), "y": round(y, 2), "status": "QUEUED"}
    state["waypoints"].append(new_wp)
    return jsonify({"success": True, "waypoint": new_wp, "total": len(state["waypoints"])})

@app.route("/api/mode", methods=["POST"])
def api_set_mode():
    data = request.get_json() or {}
    new_mode = data.get("mode", "AUTONOMOUS").upper()
    if new_mode in ["AUTONOMOUS", "MANUAL", "HOLD"]:
        state["mode"] = new_mode
        return jsonify({"success": True, "mode": state["mode"]})
    return jsonify({"success": False, "error": "Invalid mode"}), 400

@app.route("/api/stream")
def api_stream():
    """SSE streaming endpoint for low-latency live telemetry updates."""
    def event_stream():
        while True:
            update_simulation()
            data = json.dumps(state)
            yield f"data: {data}\n\n"
            time.sleep(0.1)  # 10Hz stream
    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055, debug=False)
