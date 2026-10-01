"""Dashboard: live browser GUI (video + AI status) + legacy status API."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

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

    return app


def run_dashboard(get_state_fn, host: str = "127.0.0.1", port: int = 5000) -> None:
    create_app(get_state_fn).run(host=host, port=port, threaded=True)


def run_live_dashboard(feed, host: str = "127.0.0.1", port: int = 5000) -> None:
    create_live_app(feed).run(host=host, port=port, threaded=True, use_reloader=False)
