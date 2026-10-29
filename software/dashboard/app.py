"""Dashboard: live browser GUI (video + AI status) + legacy status API."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from software.dashboard.controls import validate_command

MAX_REPORT_EVENTS = 50

PAGE = """<!doctype html><html><head><meta charset='utf-8'>
<title>AI Visual Smart Rover — Live</title>
<style>body{font-family:Consolas,monospace;background:#111;color:#0f0;margin:0}
header{padding:10px 16px;background:#000;font-size:18px}
main{display:flex;gap:16px;padding:16px;flex-wrap:wrap}
img{max-width:640px;border:2px solid #0f0;background:#000}
#panel{min-width:280px;background:#000;padding:12px;border:1px solid #0f0}
table{border-collapse:collapse;width:100%}td{padding:3px 8px;border-bottom:1px solid #030}</style>
</head><body><header>AI VISUAL SMART ROVER — LIVE</header><main>
<div><img src='/video_feed' alt='live feed'></div>
<div id='panel'><div id='meta'>loading…</div><table id='objs'></table></div>
</main><script>
async function tick(){try{const r=await fetch('/api/state');const s=await r.json();
document.getElementById('meta').innerHTML=
`SRC ${s.source} | ${s.backend}<br>MODEL ${s.model}<br>CAM ${s.camera_fps} FPS | AI ${s.infer_ms} ms (${s.ai_age_s}s ago) | OBJS ${s.objects}`;
document.getElementById('objs').innerHTML=s.detections.map(d=>
`<tr><td>${d.label}${d.id!=null?' #'+d.id:''}</td><td>${d.conf}</td><td>${d.pos}</td><td>cx ${d.cx}</td></tr>`).join('')||'<tr><td>— no objects —</td></tr>';
}catch(e){}}setInterval(tick,1500);tick();</script></body></html>"""


def create_app(get_state_fn: Callable[[], dict[str, Any]]) -> Any:
    from flask import Flask, jsonify

    app = Flask(__name__)

    @app.get("/")
    def index():
        return (
            "<h1>AI Visual Smart Rover</h1>"
            "<p><a href='/api/state'>/api/state</a> live status. "
            "Live GUI: run scripts/dashboard.py and open /live.</p>"
        )

    @app.get("/api/state")
    def state():
        try:
            s = get_state_fn()
        except Exception as e:
            s = {"error": str(e)}
        return jsonify(s)

    return app


def create_live_app(feed) -> Any:
    """feed: LiveFeed (has .jpeg(), .state())."""
    from flask import Flask, Response, jsonify

    app = Flask(__name__)

    @app.get("/")
    @app.get("/live")
    def live():
        return PAGE

    @app.get("/api/state")
    def state():
        return jsonify(feed.state())

    @app.get("/snapshot.jpg")
    def snapshot():
        jpg = feed.jpeg()
        if jpg is None:
            return ("no frame yet", 503)
        return Response(jpg, mimetype="image/jpeg")

    @app.get("/video_feed")
    def video_feed():
        return _mjpeg(feed)

    return app


def _mjpeg(feed) -> Any:
    """Multipart JPEG stream built from ``feed.jpeg()`` (None until the first frame)."""
    from flask import Response

    def gen():
        while True:
            jpg = feed.jpeg()
            if jpg is None:
                time.sleep(0.2)
                continue
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\n"
                b"Content-Length: "
                + str(len(jpg)).encode()
                + b"\r\n\r\n"
                + jpg
                + b"\r\n"
            )
            time.sleep(0.1)

    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


def create_control_app(
    feed, link, pilot=None, recorder=None, explainer=None, journal=None
) -> Any:
    """Control deck: AI video + game-style pad feeding an ArduinoLink.

    ``feed`` is a LiveFeed-like object (or None for video-less operation) and
    ``link`` is the USB command/telemetry link the pad writes through.

    ``pilot`` (MissionPilot) adds the mission deck: /api/decision why-chain and
    POST /api/mode. ``recorder`` adds POST /api/recording + /api/events run
    capture, ``explainer`` adds GET /api/explain (CLIP zero-shot labels). All
    are optional: without them the original CONTROL_PAGE and its routes behave
    exactly as before.
    """
    from flask import Flask, Response, jsonify, request

    from software.dashboard.control_page import CONTROL_PAGE

    app = Flask(__name__)

    @app.get("/")
    @app.get("/live")
    def index():
        if pilot is None:
            return CONTROL_PAGE
        from software.dashboard.deck_page import DECK_PAGE

        return DECK_PAGE

    @app.get("/video_feed")
    def video_feed():
        if feed is None:
            return ("no camera", 503)
        return _mjpeg(feed)

    @app.get("/api/state")
    def state():
        out: dict[str, Any] = {}
        try:
            if link is not None and feed is not None:
                tele = link.telemetry()
                dist = tele.get("distance_cm")
                note = getattr(feed, "note_distance", None)
                if callable(note) and isinstance(dist, (int, float)):
                    note(float(dist))
                out["link"] = tele
            else:
                out["link"] = (
                    link.telemetry()
                    if link is not None
                    else {
                        "error": "no link",
                        "connected": False,
                    }
                )
        except Exception as e:
            out["link"] = {"error": str(e), "connected": False}
        try:
            out["feed"] = feed.state() if feed is not None else {}
        except Exception as e:
            out["feed"] = {"error": str(e)}
        return jsonify(out)

    def _param_from_request(name: str) -> str | None:
        raw = request.args.get(name)
        if raw is None and request.is_json:
            body = request.get_json(silent=True) or {}
            raw = body.get(name)
        if raw is None:
            raw = request.form.get(name)
        return raw

    def _command_from_request() -> str | None:
        return _param_from_request("c")

    def cmd():
        raw = _command_from_request()
        try:
            command = validate_command(raw or "")
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        try:
            sent = link.send(command)
        except Exception as e:
            return jsonify({"ok": False, "command": command, "error": str(e)}), 503
        if not sent:
            return jsonify({"ok": False, "command": command, "error": "link down"}), 503
        return jsonify({"ok": True, "command": command})

    app.add_url_rule("/api/cmd", "cmd_get", cmd, methods=["GET"])
    app.add_url_rule("/api/cmd", "cmd_post", cmd, methods=["POST"])

    if pilot is not None:

        @app.get("/api/decision")
        def decision():
            try:
                return jsonify(pilot.status())
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        def mode():
            raw = _param_from_request("mode")
            try:
                return jsonify(pilot.set_mode(raw or ""))
            except ValueError as e:
                return jsonify({"ok": False, "error": str(e)}), 400

        app.add_url_rule("/api/mode", "mode_post", mode, methods=["POST"])

    if recorder is not None:

        @app.get("/api/events")
        def events():
            raw = request.args.get("limit", "50")
            try:
                limit = max(1, min(500, int(raw)))
            except (TypeError, ValueError):
                limit = 50
            return jsonify(recorder.status(limit=limit))

        def recording():
            raw = _param_from_request("on")
            if raw is not None:
                on = str(raw).strip().lower() in ("1", "true", "on", "yes")
                if on:
                    recorder.start()
                else:
                    recorder.stop()
            return jsonify(recorder.status())

        app.add_url_rule("/api/recording", "recording_get", recording, methods=["GET"])
        app.add_url_rule(
            "/api/recording", "recording_post", recording, methods=["POST"]
        )

        @app.get("/api/report")
        def report():
            """Mars-rover-style mission report (markdown) for the latest run."""
            from software.dashboard.report import build_report

            try:
                status = recorder.status(limit=MAX_REPORT_EVENTS)
                world = {}
                if feed is not None:
                    try:
                        world = (feed.state() or {}).get("world") or {}
                    except Exception:
                        world = {}
                md = build_report(
                    duration_s=float(status.get("duration_s", 0.0) or 0.0),
                    decisions=int(status.get("decisions", 0) or 0),
                    images=int(status.get("frames", 0) or 0),
                    commands=status.get("commands") or {},
                    events=status.get("events") or [],
                    world=world or recorder.last_world(),
                    mode_mix=status.get("modes") or {},
                    path=status.get("path"),
                )
                return Response(md, mimetype="text/markdown")
            except Exception as e:
                return jsonify({"error": str(e)}), 500

    if explainer is not None:

        @app.get("/api/explain")
        def explain():
            if feed is None:
                return jsonify({"ok": False, "error": "no camera"}), 503
            try:
                frame, dets = feed.snapshot()
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)}), 500
            if frame is None:
                return jsonify({"ok": False, "error": "no frame yet"}), 503
            labels = list(getattr(explainer, "default_labels", []) or [])
            out: dict[str, Any] = {
                "ok": True,
                "available": bool(getattr(explainer, "available", False)),
                "backend": getattr(explainer, "backend", "none"),
                "frame": explainer.explain_frame(frame, labels),
            }
            best = None
            if dets:
                best = max(dets, key=lambda d: float(d.get("confidence", 0.0) or 0.0))
            if best is not None:
                out["label"] = best.get("class_name")
                out["target"] = explainer.explain_detection(frame, best, labels)
            if str(request.args.get("caption", "")).lower() in ("1", "true", "on"):
                out["caption"] = explainer.caption(frame)
            return jsonify(out)

    @app.post("/api/stream")
    def stream_post():
        """Repoint the video at a new URL (the phone IP changes between runs)."""
        if feed is None:
            return jsonify({"ok": False, "error": "no feed"}), 503
        data = request.get_json(silent=True) or {}
        url = str(data.get("url", "") or "").strip()
        set_source = getattr(feed, "set_source", None)
        if not callable(set_source):
            return jsonify({"ok": False, "error": "source switch unsupported"}), 400
        if not url:
            return jsonify(
                {"ok": False, "error": "url required (http://<PHONE_IP>:8080/video)"}
            ), 400
        try:
            applied = set_source(url)
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
        return jsonify({"ok": True, "source": applied})

    if journal is not None:

        @app.get("/api/journal")
        def journal_get():
            """Explorer journal: status as JSON, or the markdown with ?format=md."""
            try:
                status = journal.status()
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)}), 500
            if str(request.args.get("format", "")).lower() in ("md", "markdown"):
                return Response(journal.text(), mimetype="text/markdown")
            return jsonify({"ok": True, **status, "text": journal.text()[-4000:]})

    return app


def run_control_dashboard(
    feed,
    link,
    host: str = "127.0.0.1",
    port: int = 5000,
    pilot=None,
    recorder=None,
    explainer=None,
    journal=None,
) -> None:
    try:
        from software.dashboard.ws_bridge import WebSocketBridge

        ws_bridge = WebSocketBridge(feed=feed, link=link, pilot=pilot, host="0.0.0.0", port=8765)
        ws_bridge.start()
    except Exception as e:
        import warnings

        warnings.warn(f"WebSocketBridge could not start: {e}", RuntimeWarning, stacklevel=2)

    create_control_app(
        feed,
        link,
        pilot=pilot,
        recorder=recorder,
        explainer=explainer,
        journal=journal,
    ).run(host=host, port=port, threaded=True, use_reloader=False)


def run_dashboard(get_state_fn, host: str = "127.0.0.1", port: int = 5000) -> None:
    create_app(get_state_fn).run(host=host, port=port, threaded=True)


def run_live_dashboard(feed, host: str = "127.0.0.1", port: int = 5000) -> None:
    create_live_app(feed).run(host=host, port=port, threaded=True, use_reloader=False)
