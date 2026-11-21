"""Mobile Companion Page: High-performance smartphone controller, AR HUD, and camera streamer."""

from __future__ import annotations

COMPANION_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="theme-color" content="#00f2fe">
  <link rel="manifest" href="/manifest.json">
  <title>RoverLink — Mobile Companion & AR HUD</title>
  <style>
    * { box-sizing: border-box; -webkit-touch-callout: none; -webkit-user-select: none; user-select: none; }
    body {
      margin: 0; padding: 0;
      background: #080a0f; color: #e0e6ed;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
      height: 100vh; display: flex; flex-direction: column; overflow: hidden;
    }
    header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 10px 14px; background: #0f131a; border-bottom: 1px solid #1a2230; z-index: 10;
    }
    .brand { font-size: 15px; font-weight: bold; color: #00f2fe; letter-spacing: 1px; display: flex; align-items: center; gap: 6px; }
    .badge {
      font-size: 11px; padding: 3px 8px; border-radius: 12px;
      background: #12201b; color: #10b981; border: 1px solid #10b981; font-weight: bold;
    }
    .badge.warn { background: #261908; color: #f59e0b; border-color: #f59e0b; }
    .badge.bad { background: #260d0d; color: #ef4444; border-color: #ef4444; }

    #viewports {
      flex: 1; display: flex; flex-direction: column; position: relative; background: #000; overflow: hidden;
    }
    #cam-preview {
      width: 100%; height: 100%; object-fit: cover; opacity: 0.95;
    }
    #ar-canvas {
      position: absolute; top: 0; left: 0; width: 100%; height: 100%;
      pointer-events: none; z-index: 2;
    }
    #hud-overlay {
      position: absolute; top: 10px; left: 10px; right: 10px;
      display: flex; justify-content: space-between; pointer-events: none; z-index: 3;
    }
    .hud-box {
      background: rgba(8, 10, 15, 0.8); border: 1px solid #1e293b;
      border-radius: 6px; padding: 5px 8px; font-size: 11px;
      backdrop-filter: blur(4px); box-shadow: 0 2px 4px rgba(0,0,0,0.5);
    }
    .hud-box.alert-flash {
      border-color: #ef4444; background: rgba(80, 10, 10, 0.85); animation: pulseAlert 0.8s infinite;
    }
    @keyframes pulseAlert {
      0% { transform: scale(1); }
      50% { transform: scale(1.05); }
      100% { transform: scale(1); }
    }
    .hud-val { font-size: 15px; font-weight: bold; color: #00f2fe; }

    #controls-container {
      background: #0f131a; padding: 10px 14px; border-top: 1px solid #1a2230;
      display: flex; flex-direction: column; gap: 8px; z-index: 10;
    }
    .quick-toolbar {
      display: flex; gap: 6px; justify-content: space-between;
    }
    .btn-tool {
      flex: 1; padding: 7px 4px; border-radius: 6px;
      background: #1a2230; border: 1px solid #334155; color: #94a3b8;
      font-size: 11px; font-weight: 600; text-align: center; cursor: pointer;
    }
    .btn-tool.active { background: #00f2fe; color: #000; border-color: #00f2fe; font-weight: bold; }

    .speed-row {
      display: flex; gap: 6px; justify-content: center; align-items: center;
    }
    .speed-btn {
      padding: 4px 10px; border-radius: 12px; background: #14181b;
      border: 1px solid #334155; color: #94a3b8; font-size: 10px; font-weight: bold; cursor: pointer;
    }
    .speed-btn.active {
      background: #10b981; color: #000; border-color: #10b981;
    }

    .dpad-row {
      display: flex; justify-content: center; gap: 10px;
    }
    .btn-drive {
      width: 68px; height: 54px; border-radius: 8px;
      background: #1e293b; border: 1px solid #334155; color: #f8fafc;
      font-size: 20px; font-weight: bold; display: flex; align-items: center; justify-content: center;
      box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5);
    }
    .btn-drive:active, .btn-drive.active {
      background: #00f2fe; color: #000; border-color: #00f2fe; transform: scale(0.96);
    }
    .btn-stop {
      width: 76px; height: 54px; border-radius: 8px;
      background: #ef4444; border: 1px solid #dc2626; color: #fff;
      font-size: 14px; font-weight: bold; display: flex; align-items: center; justify-content: center;
    }
    .btn-stop:active { background: #b91c1c; transform: scale(0.96); }

    .failover-row {
      display: flex; gap: 5px; align-items: center; justify-content: space-between;
      margin-top: 2px; padding: 4px 8px; background: #080a0f; border-radius: 6px;
      font-size: 10px; border: 1px solid #1e293b;
    }
    .failover-title { color: #f59e0b; font-weight: bold; font-size: 9px; letter-spacing: 0.5px; }
    .failover-btn {
      flex: 1; padding: 4px 4px; border-radius: 4px; background: #14181b;
      border: 1px solid #334155; color: #94a3b8; font-size: 9px; text-align: center;
      text-decoration: none; cursor: pointer; font-weight: 600;
    }
    .failover-btn.active {
      background: #08201a; color: #10b981; border-color: #10b981;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">&#9670; ROVERLINK AR HUD</div>
    <div style="display:flex;align-items:center;gap:6px;">
      <span id="ping-pill" style="font-size:10px;color:#64748b;font-weight:bold;">PING: —</span>
      <span id="batt-pill" style="font-size:10px;color:#10b981;font-weight:bold;">⚡ 7.4V</span>
      <div id="conn-pill" class="badge">CONNECTING…</div>
    </div>
  </header>

  <div id="viewports">
    <video id="cam-preview" autoplay playsinline muted></video>
    <canvas id="ar-canvas"></canvas>
    <div id="hud-overlay">
      <div id="dist-box" class="hud-box">
        <div>DISTANCE</div>
        <div id="dist-val" class="hud-val">— cm</div>
      </div>
      <div class="hud-box" style="display:flex;align-items:center;gap:4px;padding:3px 6px;">
        <canvas id="mini-radar" width="68" height="42" style="background:#000;border:1px solid #1e293b;border-radius:4px;"></canvas>
      </div>
      <div class="hud-box" style="text-align:right;">
        <div>AUTONOMY</div>
        <div id="mode-val" class="hud-val" style="cursor:pointer;">MANUAL</div>
      </div>
    </div>
  </div>

  <div id="controls-container">
    <div class="quick-toolbar">
      <button id="btn-camera" class="btn-tool">&#128247; START CAM</button>
      <button id="btn-torch" class="btn-tool">&#128294; TORCH</button>
      <button id="btn-flip" class="btn-tool">&#128257; FLIP</button>
      <button id="btn-snap" class="btn-tool">&#128248; SNAP</button>
      <button id="btn-voice" class="btn-tool">&#127908; VOICE</button>
    </div>

    <!-- Speed Profiles -->
    <div class="speed-row">
      <span style="font-size:10px;color:#64748b;font-weight:bold;">SPEED:</span>
      <button class="speed-btn" data-speed="130">ECO</button>
      <button class="speed-btn active" data-speed="185">NORMAL</button>
      <button class="speed-btn" data-speed="255">TURBO</button>
    </div>

    <!-- Directional Pad -->
    <div class="dpad-row">
      <button class="btn-drive" data-cmd="F">&#9650;</button>
    </div>
    <div class="dpad-row">
      <button class="btn-drive" data-cmd="L">&#9664;</button>
      <button class="btn-stop" data-cmd="S">STOP</button>
      <button class="btn-drive" data-cmd="R">&#9654;</button>
    </div>
    <div class="dpad-row">
      <button class="btn-drive" data-cmd="B">&#9660;</button>
    </div>

    <!-- Failover / Backup System Selector -->
    <div class="failover-row">
      <span class="failover-title">BACKUP:</span>
      <button id="plan-a-btn" class="failover-btn active">Plan A (WebCam)</button>
      <button id="plan-b-btn" class="failover-btn">Plan B (IP Webcam)</button>
      <a href="http://192.168.4.1" target="_blank" class="failover-btn">Plan C (Soft-AP)</a>
    </div>
  </div>

  <script>
    let streamActive = false;
    let localStream = null;
    let videoTrack = null;
    let torchOn = false;
    let facingMode = "environment";
    let activeSpeed = 185;
    let currentMode = "manual";
    let myClientIp = "";

    const videoEl = document.getElementById("cam-preview");
    const arCanvas = document.getElementById("ar-canvas");
    const arCtx = arCanvas.getContext("2d");
    const distBox = document.getElementById("dist-box");

    // Dynamic AR Reticle Drawing
    function drawAROverlay(detections) {
      arCanvas.width = videoEl.clientWidth;
      arCanvas.height = videoEl.clientHeight;
      arCtx.clearRect(0, 0, arCanvas.width, arCanvas.height);

      if (!detections || !detections.length) return;

      const scaleX = arCanvas.width / (videoEl.videoWidth || 640);
      const scaleY = arCanvas.height / (videoEl.videoHeight || 480);

      detections.forEach(det => {
        let x = 0, y = 0, w = 0, h = 0, label = "OBJECT";
        if (det.box && det.box.length === 4) {
          x = det.box[0] * scaleX;
          y = det.box[1] * scaleY;
          w = det.box[2] * scaleX;
          h = det.box[3] * scaleY;
        } else {
          // Centered HUD bracket if box coords not normalized
          x = arCanvas.width * 0.25; y = arCanvas.height * 0.25;
          w = arCanvas.width * 0.5; h = arCanvas.height * 0.5;
        }
        label = (det.label || "TARGET").toUpperCase();
        const conf = det.score ? Math.round(det.score * 100) + "%" : "";

        // Sci-Fi Target Reticle
        arCtx.strokeStyle = "#00f2fe";
        arCtx.lineWidth = 2;
        arCtx.strokeRect(x, y, w, h);

        // Corner brackets
        const bLen = Math.min(w, h) * 0.2;
        arCtx.strokeStyle = "#10b981";
        arCtx.lineWidth = 3;
        // Top-left
        arCtx.beginPath(); arCtx.moveTo(x, y + bLen); arCtx.lineTo(x, y); arCtx.lineTo(x + bLen, y); arCtx.stroke();
        // Top-right
        arCtx.beginPath(); arCtx.moveTo(x + w - bLen, y); arCtx.lineTo(x + w, y); arCtx.lineTo(x + w, y + bLen); arCtx.stroke();

        // Label Badge
        arCtx.fillStyle = "rgba(0, 242, 254, 0.85)";
        arCtx.fillRect(x, Math.max(0, y - 20), arCtx.measureText(label + " " + conf).width + 12, 18);
        arCtx.fillStyle = "#000";
        arCtx.font = "bold 11px monospace";
        arCtx.fillText(label + " " + conf, x + 6, Math.max(14, y - 6));
      });
    }

    // Motion Command Sender with Speed and Haptics
    async function sendCmd(cmd) {
      if (navigator.vibrate) navigator.vibrate(20);
      try {
        await fetch("/api/cmd", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ c: cmd, speed: activeSpeed })
        });
      } catch (e) {}
    }

    // Speed Selector Buttons
    document.querySelectorAll(".speed-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".speed-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        activeSpeed = parseInt(btn.dataset.speed, 10);
      });
    });

    // Touch D-Pad with Pointer Capture
    document.querySelectorAll("[data-cmd]").forEach(btn => {
      const cmd = btn.dataset.cmd;
      btn.addEventListener("pointerdown", e => {
        e.preventDefault();
        btn.classList.add("active");
        sendCmd(cmd);
      });
      btn.addEventListener("pointerup", e => {
        btn.classList.remove("active");
        if (cmd !== "S") sendCmd("S");
      });
      btn.addEventListener("pointercancel", e => {
        btn.classList.remove("active");
        if (cmd !== "S") sendCmd("S");
      });
    });

    // Camera Streamer with Sub-50ms Response Telemetry Ingestion
    const btnCam = document.getElementById("btn-camera");
    const btnTorch = document.getElementById("btn-torch");
    const btnFlip = document.getElementById("btn-flip");
    const btnSnap = document.getElementById("btn-snap");
    const btnVoice = document.getElementById("btn-voice");
    let broadcastTimer = null;
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");
    let isUploading = false;

    function startBroadcasting() {
      if (broadcastTimer) clearInterval(broadcastTimer);
      broadcastTimer = setInterval(() => {
        if (!streamActive || !videoEl.videoWidth || isUploading) return;
        canvas.width = 480;
        canvas.height = 360;
        ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(async blob => {
          if (!blob || !streamActive) return;
          isUploading = true;
          try {
            const res = await fetch("/api/frame", {
              method: "POST",
              headers: { "Content-Type": "image/jpeg" },
              body: blob
            });
            const data = await res.json();
            // Immediate real-time HUD update from frame response
            if (data && data.ok) {
              if (data.detections) drawAROverlay(data.detections);
              if (data.distance_cm != null) updateDistanceHUD(data.distance_cm);
            }
          } catch (e) {
          } finally {
            isUploading = false;
          }
        }, "image/jpeg", 0.65);
      }, 70);
    }

    function stopBroadcasting() {
      if (broadcastTimer) { clearInterval(broadcastTimer); broadcastTimer = null; }
      arCtx.clearRect(0, 0, arCanvas.width, arCanvas.height);
      isUploading = false;
    }

    async function initCamera() {
      if (localStream) localStream.getTracks().forEach(t => t.stop());
      try {
        localStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: facingMode, width: { ideal: 640 }, height: { ideal: 480 } },
          audio: false
        });
        videoEl.srcObject = localStream;
        videoTrack = localStream.getVideoTracks()[0];
        streamActive = true;
        startBroadcasting();
        btnCam.classList.add("active");
        btnCam.textContent = "CAM ON";
      } catch (err) {
        alert("Camera start failed: " + err.message);
      }
    }

    btnCam.addEventListener("click", () => {
      if (!streamActive) {
        initCamera();
      } else {
        stopBroadcasting();
        if (localStream) localStream.getTracks().forEach(t => t.stop());
        videoEl.srcObject = null;
        streamActive = false;
        btnCam.classList.remove("active");
        btnCam.textContent = "START CAM";
      }
    });

    btnFlip.addEventListener("click", () => {
      facingMode = (facingMode === "environment") ? "user" : "environment";
      if (streamActive) initCamera();
    });

    btnTorch.addEventListener("click", async () => {
      if (videoTrack && videoTrack.getCapabilities && videoTrack.getCapabilities().torch) {
        torchOn = !torchOn;
        await videoTrack.applyConstraints({ advanced: [{ torch: torchOn }] });
        btnTorch.textContent = torchOn ? "TORCH ON" : "TORCH";
        btnTorch.classList.toggle("active", torchOn);
      } else {
        alert("Torch hardware not available on this camera.");
      }
    });

    btnSnap.addEventListener("click", () => {
      window.open("/snapshot.jpg", "_blank");
    });

    // Web Speech API Voice Driving
    let recognizing = false;
    btnVoice.addEventListener("click", () => {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        alert("Voice driving requires Google Chrome on Android or desktop.");
        return;
      }
      if (!recognizing) {
        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.lang = "en-US";
        recognition.onstart = () => {
          recognizing = true;
          btnVoice.classList.add("active");
          btnVoice.textContent = "LISTENING…";
        };
        recognition.onresult = (event) => {
          const last = event.results.length - 1;
          const text = event.results[last][0].transcript.trim().toLowerCase();
          if (text.includes("forward") || text.includes("ahead")) sendCmd("F");
          else if (text.includes("back") || text.includes("reverse")) sendCmd("B");
          else if (text.includes("left")) sendCmd("L");
          else if (text.includes("right")) sendCmd("R");
          else if (text.includes("stop") || text.includes("halt")) sendCmd("S");
        };
        recognition.onerror = () => {
          recognizing = false;
          btnVoice.classList.remove("active");
          btnVoice.textContent = "VOICE";
        };
        recognition.onend = () => {
          recognizing = false;
          btnVoice.classList.remove("active");
          btnVoice.textContent = "VOICE";
        };
        recognition.start();
      }
    });

    // Autonomy Mode Switcher
    const modeVal = document.getElementById("mode-val");
    modeVal.addEventListener("click", async () => {
      const target = (currentMode === "manual") ? "auto" : "manual";
      try {
        const res = await fetch("/api/mode", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: "mode=" + target
        });
        const d = await res.json();
        if (d.mode) {
          currentMode = d.mode;
          modeVal.textContent = currentMode.toUpperCase();
        }
      } catch (e) {}
    });

    // Top-down Sonar Radar Sweep Minimap
    const radarCanvas = document.getElementById("mini-radar");
    const rCtx = radarCanvas.getContext("2d");
    let sweepAngle = -0.6;
    let sweepDir = 0.04;
    let lastKnownDistance = null;

    function drawMiniRadar(cm) {
      const w = radarCanvas.width, h = radarCanvas.height;
      rCtx.fillStyle = "rgba(0, 5, 10, 0.45)";
      rCtx.fillRect(0, 0, w, h);

      const cx = w / 2, cy = h - 3;
      const maxR = h - 5;

      // Range rings
      rCtx.strokeStyle = "#1e293b";
      rCtx.lineWidth = 1;
      rCtx.beginPath(); rCtx.arc(cx, cy, maxR * 0.4, Math.PI, 2 * Math.PI); rCtx.stroke();
      rCtx.beginPath(); rCtx.arc(cx, cy, maxR * 0.75, Math.PI, 2 * Math.PI); rCtx.stroke();
      rCtx.beginPath(); rCtx.arc(cx, cy, maxR, Math.PI, 2 * Math.PI); rCtx.stroke();

      // Sweep Beam
      sweepAngle += sweepDir;
      if (sweepAngle > 0.6 || sweepAngle < -0.6) sweepDir = -sweepDir;
      rCtx.strokeStyle = "rgba(0, 242, 254, 0.5)";
      rCtx.beginPath();
      rCtx.moveTo(cx, cy);
      rCtx.lineTo(cx + maxR * Math.sin(sweepAngle), cy - maxR * Math.cos(sweepAngle));
      rCtx.stroke();

      // Rover center
      rCtx.fillStyle = "#00f2fe";
      rCtx.beginPath(); rCtx.arc(cx, cy, 2.5, 0, 2 * Math.PI); rCtx.fill();

      // Obstacle Blip
      if (cm != null && cm > 0 && cm < 120) {
        const normDist = Math.min(1.0, cm / 75.0);
        const obR = Math.max(6, normDist * maxR);
        rCtx.fillStyle = cm < 25 ? "#ef4444" : (cm < 45 ? "#f59e0b" : "#10b981");
        rCtx.beginPath();
        rCtx.arc(cx, cy - obR, 3.5, 0, 2 * Math.PI);
        rCtx.fill();
      }
    }
    setInterval(() => drawMiniRadar(lastKnownDistance), 80);

    // Distance HUD and Proximity Haptics
    function updateDistanceHUD(cm) {
      if (cm != null) {
        lastKnownDistance = cm;
        const rounded = Math.round(cm);
        document.getElementById("dist-val").textContent = rounded + " cm";
        drawMiniRadar(rounded);
        if (rounded < 25) {
          distBox.classList.add("alert-flash");
          if (navigator.vibrate) navigator.vibrate([100, 50, 100]);
        } else {
          distBox.classList.remove("alert-flash");
        }
      }
    }

    // Failover Handlers
    document.getElementById("plan-a-btn").addEventListener("click", () => {
      document.getElementById("plan-a-btn").classList.add("active");
      document.getElementById("plan-b-btn").classList.remove("active");
      alert("Plan A Active: In-Browser Camera streaming to YOLOv11.");
    });

    document.getElementById("plan-b-btn").addEventListener("click", async () => {
      const ip = prompt("Confirm Phone IP for IP Webcam stream (default port 8080):", myClientIp || "192.168.1.50");
      if (!ip) return;
      const url = ip.startsWith("http") ? ip : `http://${ip}:8080/video`;
      try {
        const res = await fetch("/api/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: url })
        });
        const d = await res.json();
        if (d.ok) {
          alert("✓ Plan B Active! Laptop repointed to " + url);
          document.getElementById("plan-b-btn").classList.add("active");
          document.getElementById("plan-a-btn").classList.remove("active");
        } else {
          alert("Stream switch error: " + (d.error || "unknown"));
        }
      } catch (err) {
        alert("Connection error: " + err.message);
      }
    });

    // Poller fallback
    let lastPingMs = 0;
    async function pollState() {
      const t0 = performance.now();
      try {
        const res = await fetch("/api/state");
        const data = await res.json();
        lastPingMs = Math.round(performance.now() - t0);
        const pingPill = document.getElementById("ping-pill");
        if (pingPill) {
          pingPill.textContent = "PING: " + lastPingMs + "ms";
          pingPill.style.color = (lastPingMs < 40) ? "#10b981" : "#f59e0b";
        }
        if (data.client_ip) myClientIp = data.client_ip;
        const connPill = document.getElementById("conn-pill");
        connPill.textContent = "LINK OK";
        connPill.className = "badge";

        if (data.link && data.link.distance_cm != null) {
          updateDistanceHUD(data.link.distance_cm);
        }
        if (data.pilot && data.pilot.mode) {
          currentMode = data.pilot.mode;
          modeVal.textContent = currentMode.toUpperCase();
        }
      } catch (e) {
        const connPill = document.getElementById("conn-pill");
        connPill.textContent = "OFFLINE";
        connPill.className = "badge bad";
      }
    }
    setInterval(pollState, 1500);
    pollState();
  </script>
</body>
</html>
"""
