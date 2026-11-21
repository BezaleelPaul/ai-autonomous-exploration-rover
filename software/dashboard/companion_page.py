"""Mobile Companion Page: Zero-install smartphone controller, camera streamer, and telemetry HUD."""

from __future__ import annotations

COMPANION_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
  <title>RoverLink — Mobile Companion</title>
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
      padding: 10px 16px; background: #0f131a; border-bottom: 1px solid #1a2230;
    }
    .brand { font-size: 16px; font-weight: bold; color: #00f2fe; letter-spacing: 1px; }
    .badge {
      font-size: 11px; padding: 3px 8px; border-radius: 12px;
      background: #12201b; color: #10b981; border: 1px solid #10b981;
    }
    .badge.warn { background: #261908; color: #f59e0b; border-color: #f59e0b; }
    .badge.bad { background: #260d0d; color: #ef4444; border-color: #ef4444; }

    #viewports {
      flex: 1; display: flex; flex-direction: column; position: relative; background: #000;
    }
    #cam-preview {
      width: 100%; height: 100%; object-fit: cover; opacity: 0.9;
    }
    #hud-overlay {
      position: absolute; top: 12px; left: 12px; right: 12px;
      display: flex; justify-content: space-between; pointer-events: none;
    }
    .hud-box {
      background: rgba(8, 10, 15, 0.75); border: 1px solid #1e293b;
      border-radius: 6px; padding: 6px 10px; font-size: 12px;
      backdrop-filter: blur(4px);
    }
    .hud-val { font-size: 16px; font-weight: bold; color: #00f2fe; }

    #controls-container {
      background: #0f131a; padding: 14px 16px; border-top: 1px solid #1a2230;
      display: flex; flex-direction: column; gap: 10px;
    }
    .dpad-row {
      display: flex; justify-content: center; gap: 12px;
    }
    .btn-drive {
      width: 72px; height: 60px; border-radius: 8px;
      background: #1e293b; border: 1px solid #334155; color: #f8fafc;
      font-size: 20px; font-weight: bold; display: flex; align-items: center; justify-content: center;
      box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5);
    }
    .btn-drive:active, .btn-drive.active {
      background: #00f2fe; color: #000; border-color: #00f2fe; transform: scale(0.96);
    }
    .btn-stop {
      width: 80px; height: 60px; border-radius: 8px;
      background: #ef4444; border: 1px solid #dc2626; color: #fff;
      font-size: 15px; font-weight: bold; display: flex; align-items: center; justify-content: center;
    }
    .btn-stop:active { background: #b91c1c; transform: scale(0.96); }

    .action-row {
      display: flex; gap: 10px; justify-content: space-between;
    }
    .btn-action {
      flex: 1; padding: 8px 12px; border-radius: 6px;
      background: #1a2230; border: 1px solid #334155; color: #94a3b8;
      font-size: 12px; font-weight: 600; text-align: center; cursor: pointer;
    }
    .btn-action.active { background: #10b981; color: #000; border-color: #10b981; }
  </style>
</head>
<body>
  <header>
    <div class="brand">&#9670; ROVERLINK COMPANION</div>
    <div id="conn-pill" class="badge">CONNECTING…</div>
  </header>

  <div id="viewports">
    <video id="cam-preview" autoplay playsinline muted></video>
    <div id="hud-overlay">
      <div class="hud-box">
        <div>DISTANCE</div>
        <div id="dist-val" class="hud-val">— cm</div>
      </div>
      <div class="hud-box">
        <div>AUTONOMY</div>
        <div id="mode-val" class="hud-val">MANUAL</div>
      </div>
    </div>
  </div>

  <div id="controls-container">
    <div class="action-row">
      <button id="btn-camera" class="btn-action">&#128247; START PHONE CAMERA</button>
      <button id="btn-torch" class="btn-action">&#128294; TORCH OFF</button>
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
  </div>

  <script>
    let streamActive = false;
    let localStream = null;
    let videoTrack = null;
    let torchOn = false;

    // Send motion commands to laptop brain
    async function sendCmd(cmd) {
      try {
        await fetch("/api/cmd", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ c: cmd })
        });
      } catch (e) {}
    }

    // Touch handlers with pointer capture
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

    // Camera Broadcaster
    const btnCam = document.getElementById("btn-camera");
    const btnTorch = document.getElementById("btn-torch");
    const videoEl = document.getElementById("cam-preview");
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
            await fetch("/api/frame", {
              method: "POST",
              headers: { "Content-Type": "image/jpeg" },
              body: blob
            });
          } catch (e) {
          } finally {
            isUploading = false;
          }
        }, "image/jpeg", 0.65);
      }, 70);
    }

    function stopBroadcasting() {
      if (broadcastTimer) {
        clearInterval(broadcastTimer);
        broadcastTimer = null;
      }
      isUploading = false;
    }

    btnCam.addEventListener("click", async () => {
      if (!streamActive) {
        try {
          localStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "environment", width: { ideal: 640 }, height: { ideal: 480 } },
            audio: false
          });
          videoEl.srcObject = localStream;
          videoTrack = localStream.getVideoTracks()[0];
          streamActive = true;
          startBroadcasting();
          btnCam.classList.add("active");
          btnCam.textContent = "CAMERA BROADCASTING";
        } catch (err) {
          alert("Camera access failed: " + err.message);
        }
      } else {
        stopBroadcasting();
        if (localStream) localStream.getTracks().forEach(t => t.stop());
        videoEl.srcObject = null;
        streamActive = false;
        btnCam.classList.remove("active");
        btnCam.textContent = "📷 START PHONE CAMERA";
      }
    });

    // Flashlight / Torch toggle
    btnTorch.addEventListener("click", async () => {
      if (videoTrack && videoTrack.getCapabilities && videoTrack.getCapabilities().torch) {
        torchOn = !torchOn;
        await videoTrack.applyConstraints({ advanced: [{ torch: torchOn }] });
        btnTorch.textContent = torchOn ? "🔦 TORCH ON" : "🔦 TORCH OFF";
        btnTorch.classList.toggle("active", torchOn);
      } else {
        alert("Torch not supported on this device camera");
      }
    });

    // Telemetry Poller
    async function pollState() {
      try {
        const res = await fetch("/api/state");
        const data = await res.json();
        const connPill = document.getElementById("conn-pill");
        connPill.textContent = "ROVER LINK ACTIVE";
        connPill.className = "badge";

        if (data.link && data.link.distance_cm != null) {
          document.getElementById("dist-val").textContent = Math.round(data.link.distance_cm) + " cm";
        }
      } catch (e) {
        const connPill = document.getElementById("conn-pill");
        connPill.textContent = "DESKTOP OFFLINE";
        connPill.className = "badge bad";
      }
    }
    setInterval(pollState, 1000);
    pollState();
  </script>
</body>
</html>
"""
