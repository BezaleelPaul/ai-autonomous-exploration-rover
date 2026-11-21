/*
 * web_ui.h - single-file mobile drive pad served from ESP32 flash.
 *
 * Design contracts (asserted by tests/test_esp32_contracts.py):
 *   - pointerdown starts a hold, pointerup/pointercancel/lostpointercapture stop
 *   - a held command is re-sent every 150 ms (link watchdog is 500 ms)
 *   - every release sends S; hidden tab / page hide also sends S
 *   - speed slider is clamped to the 60..255 stiction window
 */
#ifndef ROVER_WEB_UI_H
#define ROVER_WEB_UI_H

#include <Arduino.h>

const char INDEX_HTML[] PROGMEM = R"HTML(<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#070b12">
<title>AI Rover Control</title>
<style>
  :root{
    --bg:#070b12; --panel:#0f1622; --line:#1e2a3a; --ink:#e8f1ff;
    --dim:#7f93ab; --accent:#22d3ee; --accent2:#0ea5b7; --stop:#ef4444;
    --ok:#22c55e; --warn:#f59e0b;
  }
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  html,body{margin:0;height:100%}
  body{
    background:radial-gradient(1200px 800px at 50% -10%,#12202f 0%,var(--bg) 55%);
    color:var(--ink);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    display:flex;flex-direction:column;overscroll-behavior:none;user-select:none;
    padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);
  }
  header{display:flex;align-items:center;gap:10px;padding:14px 18px;border-bottom:1px solid var(--line)}
  .logo{font-size:15px;font-weight:700;letter-spacing:.18em;color:var(--accent)}
  .sub{font-size:11px;color:var(--dim);letter-spacing:.08em}
  .dot{margin-left:auto;width:9px;height:9px;border-radius:50%;background:var(--dim);box-shadow:0 0 0 4px #ffffff08;transition:.2s}
  .dot.on{background:var(--ok);box-shadow:0 0 12px var(--ok)}
  .dot.off{background:var(--warn);box-shadow:0 0 12px var(--warn)}
  main{flex:1;display:flex;flex-direction:column;gap:14px;padding:16px 18px 26px;max-width:520px;width:100%;margin:0 auto}
  .hud{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
  .chip{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 6px;text-align:center;min-width:0}
  .chip b{display:block;font-size:15px;font-weight:700;color:var(--ink)}
  .chip span{font-size:9px;letter-spacing:.1em;color:var(--dim);text-transform:uppercase}
  .pad{display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(3,minmax(74px,1fr));gap:12px;margin-top:2px}
  .btn{
    border:1px solid var(--line);border-radius:18px;background:linear-gradient(180deg,#16222f,#0d1520);
    color:var(--ink);font-size:26px;font-family:inherit;display:flex;align-items:center;justify-content:center;
    touch-action:none;transition:transform .06s,box-shadow .12s,background .12s,border-color .12s;
  }
  .btn small{font-size:9px;letter-spacing:.12em;color:var(--dim);display:block}
  .btn:active,.btn.on{
    transform:scale(.97);border-color:var(--accent);background:linear-gradient(180deg,#0b3b46,#062229);
    box-shadow:0 0 22px #22d3ee44,inset 0 0 18px #22d3ee22;
  }
  .up{grid-area:1/2}.left{grid-area:2/1}.right{grid-area:2/3}.down{grid-area:3/2}
  .stop{
    grid-area:2/2;background:linear-gradient(180deg,#3a1216,#1d090c);border-color:#7f1d1d;color:#fecaca;
    font-size:13px;font-weight:700;letter-spacing:.16em;border-radius:999px;
  }
  .stop:active{background:#7f1d1d;box-shadow:0 0 24px #ef444466}
  .speed{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:12px 14px}
  .speed .row{display:flex;justify-content:space-between;font-size:11px;letter-spacing:.1em;color:var(--dim);text-transform:uppercase}
  .speed output{color:var(--accent);font-weight:700;font-size:13px}
  input[type=range]{width:100%;margin:12px 0 2px;-webkit-appearance:none;background:transparent}
  input[type=range]::-webkit-slider-runnable-track{height:8px;border-radius:999px;background:linear-gradient(90deg,var(--accent2),var(--accent))}
  input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:26px;height:26px;border-radius:50%;background:#e8f1ff;border:4px solid #0b1a22;margin-top:-9px;box-shadow:0 0 14px #22d3ee88}
  input[type=range]::-moz-range-track{height:8px;border-radius:999px;background:var(--accent2)}
  input[type=range]::-moz-range-thumb{width:20px;height:20px;border-radius:50%;background:#e8f1ff;border:4px solid #0b1a22}
  details{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:10px 14px;font-size:12px;color:var(--dim)}
  summary{cursor:pointer;letter-spacing:.08em;text-transform:uppercase;font-size:10px;outline:none}
  .camrow{display:flex;gap:8px;margin-top:10px}
  .camrow input{flex:1;min-width:0;background:#0a1119;border:1px solid var(--line);border-radius:9px;color:var(--ink);padding:9px;font-family:inherit;font-size:12px}
  .camrow button,.camrow a{background:#12222e;border:1px solid var(--line);border-radius:9px;color:var(--accent);padding:9px 12px;font-family:inherit;font-size:11px;text-decoration:none;display:flex;align-items:center}
  footer{text-align:center;font-size:9px;color:#3f5166;letter-spacing:.14em;padding-bottom:10px}
  .banner{display:none;background:#3a1216;border:1px solid #7f1d1d;color:#fecaca;
    border-radius:12px;padding:11px 14px;font-size:11px;letter-spacing:.1em;text-align:center}
  .banner.show{display:block;animation:pulse 1.2s infinite}
  @keyframes pulse{50%{opacity:.55}}
  .toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(20px);opacity:0;
    background:#111c28;border:1px solid var(--line);color:var(--ink);padding:10px 16px;border-radius:999px;font-size:11px;
    transition:.25s;pointer-events:none}
  .toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
</style>
</head>
<body>
<header>
  <div>
    <div class="logo">AI ROVER</div>
    <div class="sub" id="ssid">AI_Rover_Control</div>
  </div>
  <div class="dot" id="link"></div>
</header>

<main>
  <div class="hud">
    <div class="chip"><b id="hUp">--</b><span>uptime</span></div>
    <div class="chip"><b id="hFwd">--</b><span>packets</span></div>
    <div class="chip"><b id="hRej">--</b><span>rejected</span></div>
    <div class="chip"><b id="hUno">--</b><span>uno</span></div>
  </div>

  <div class="banner" id="faultBanner">UNO FAULT &mdash; MOTION DISABLED</div>

  <div class="pad">
    <button class="btn up" data-cmd="F" aria-label="Forward">&#9650;</button>
    <button class="btn left" data-cmd="L" aria-label="Turn left">&#9664;</button>
    <button class="btn stop" id="stopBtn" aria-label="Stop">STOP</button>
    <button class="btn right" data-cmd="R" aria-label="Turn right">&#9654;</button>
    <button class="btn down" data-cmd="B" aria-label="Reverse">&#9660;</button>
  </div>

  <div class="speed">
    <div class="row"><span>PWM 60 &rarr; 255</span><output id="spdOut">180</output></div>
    <input type="range" id="speed" min="60" max="255" step="5" value="180">
  </div>

  <details>
    <summary>Camera stream</summary>
    <div class="camrow">
      <input id="camUrl" type="url" inputmode="url" placeholder="http://192.168.4.2:8080/video">
      <button id="camSave">Save</button>
      <a id="camOpen" href="#" target="_blank" rel="noopener">Open</a>
    </div>
  </details>
  <footer>HOLD TO DRIVE &middot; RELEASE TO STOP &middot; 500 ms FAILSAFE</footer>
</main>

<div class="toast" id="toast"></div>

<script>
(function () {
  "use strict";
  var TOKEN = "__TOKEN__";   // filled in by the ESP32 from API_TOKEN (empty = open)
  function withToken(url) {
    if (!TOKEN) return url;
    return url + (url.indexOf("?") >= 0 ? "&" : "?") + "k=" + encodeURIComponent(TOKEN);
  }

  var speedInput = document.getElementById("speed");
  var spdOut = document.getElementById("spdOut");
  var linkDot = document.getElementById("link");
  var toastEl = document.getElementById("toast");
  var held = null;        // {btn, cmd}
  var repeatTimer = null;
  var REPEAT_MS = 150;    // << 500 ms watchdog

  function speed() {
    var v = parseInt(speedInput.value, 10) || 180;
    if (v < 60) v = 60;
    if (v > 255) v = 255;
    return v;
  }

  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { toastEl.classList.remove("show"); }, 1600);
  }

  function send(cmd, withSpeed) {
    var url = "/cmd?c=" + cmd + (withSpeed ? String(speed()) : "");
    try {
      return fetch(withToken(url), { cache: "no-store", keepalive: true }).then(function (r) {
        linkDot.className = "dot " + (r.ok ? "on" : "off");
        return r.ok;
      }).catch(function () {
        linkDot.className = "dot off";
        return false;
      });
    } catch (e) { return Promise.resolve(false); }
  }

  function stopAll() {
    if (repeatTimer) { clearInterval(repeatTimer); repeatTimer = null; }
    if (held) { held.btn.classList.remove("on"); held = null; }
    send("S", false);
  }

  function begin(btn, cmd) {
    if (held) stopAll();
    held = { btn: btn, cmd: cmd };
    btn.classList.add("on");
    send(cmd, true);
    if (navigator.vibrate) { try { navigator.vibrate(12); } catch (e) {} }
    repeatTimer = setInterval(function () { send(cmd, true); }, REPEAT_MS);
  }

  function release(btn) {
    if (!held || (btn && held.btn !== btn)) return;
    stopAll();
  }

  // --- hold-to-drive with pointer capture (drag off the button = still held)
  Array.prototype.forEach.call(document.querySelectorAll(".btn[data-cmd]"), function (btn) {
    btn.addEventListener("pointerdown", function (e) {
      e.preventDefault();
      try { btn.setPointerCapture(e.pointerId); } catch (err) {}
      begin(btn, btn.getAttribute("data-cmd"));
    });
    btn.addEventListener("pointerup", function () { release(btn); });
    btn.addEventListener("pointercancel", function () { release(btn); });
    btn.addEventListener("lostpointercapture", function () { release(btn); });
    btn.addEventListener("contextmenu", function (e) { e.preventDefault(); });
  });

  document.getElementById("stopBtn").addEventListener("pointerdown", function (e) {
    e.preventDefault();
    stopAll();
    if (navigator.vibrate) { try { navigator.vibrate([20, 30, 20]); } catch (e) {} }
  });

  // --- keyboard teleop (laptop browser / presentation)
  var keymap = { ArrowUp: "F", w: "F", W: "F", ArrowDown: "B", s: "B", S: "B",
                 ArrowLeft: "L", a: "L", A: "L", ArrowRight: "R", d: "R", D: "R" };
  window.addEventListener("keydown", function (e) {
    if (e.target && e.target.tagName === "INPUT") return;
    if (e.key === " " || e.key === "Escape") { e.preventDefault(); stopAll(); return; }
    var cmd = keymap[e.key];
    if (!cmd) return;
    e.preventDefault();
    if (e.repeat) return;
    var btn = document.querySelector('.btn[data-cmd="' + cmd + '"]');
    begin(btn, cmd);
  });
  window.addEventListener("keyup", function (e) {
    if (!keymap[e.key]) return;
    release(null);
  });

  // --- failsafe on tab hide / page leave
  document.addEventListener("visibilitychange", function () { if (document.hidden) stopAll(); });
  window.addEventListener("pagehide", function () { stopAll(); });
  window.addEventListener("blur", stopAll);

  // --- speed slider
  speedInput.addEventListener("input", function () { spdOut.textContent = speed(); });
  spdOut.textContent = speed();

  // --- camera URL
  var camUrl = document.getElementById("camUrl");
  var camOpen = document.getElementById("camOpen");
  document.getElementById("camSave").addEventListener("click", function () {
    var u = camUrl.value.trim();
    if (!/^https?:\/\//.test(u)) { toast("URL must start with http://"); return; }
    fetch(withToken("/cam?u=" + encodeURIComponent(u)), { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j.ok) { camOpen.href = u; toast("Camera saved"); } else { toast("Rejected"); }
      }).catch(function () { toast("Gateway unreachable"); });
  });
  camOpen.addEventListener("click", function (e) {
    if (camOpen.getAttribute("href") === "#") { e.preventDefault(); toast("Set a camera URL first"); }
  });

  // --- status HUD
  function fmtUptime(ms) {
    var s = Math.floor(ms / 1000);
    if (s < 60) return s + "s";
    var m = Math.floor(s / 60);
    if (m < 60) return m + "m";
    return Math.floor(m / 60) + "h";
  }
  function poll() {
    fetch("/status", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (j) {
      linkDot.className = "dot on";
      document.getElementById("hUp").textContent = fmtUptime(j.uptime_ms || 0);
      document.getElementById("hFwd").textContent = j.forwarded || 0;
      document.getElementById("hRej").textContent = j.rejected || 0;

      var uno = j.uno || {};
      var chip = document.getElementById("hUno");
      var banner = document.getElementById("faultBanner");
      chip.style.color = "";
      if (!uno.wired) {
        chip.textContent = "--";
      } else if (uno.fault_pin) {
        chip.textContent = "FAULT";
        chip.style.color = "#fca5a5";
      } else if (uno.alive) {
        chip.textContent = uno.has_telemetry ? (uno.state || "OK") : "OK";
      } else {
        chip.textContent = "LOST";
        chip.style.color = "#fbbf24";
      }
      banner.classList.toggle("show", !!uno.fault_pin);

      if (j.camera && !camUrl.value) { camUrl.value = j.camera; camOpen.href = j.camera; }
      var sub = "AI_Rover_Control";
      if (uno.has_telemetry && uno.state) sub += " \u00b7 " + uno.state;
      if (uno.has_telemetry && uno.battery_mv) sub += " \u00b7 " + (uno.battery_mv / 1000).toFixed(2) + "V";
      if (uno.has_telemetry && uno.odometer_mm) sub += " \u00b7 " + (uno.odometer_mm / 1000).toFixed(2) + "m";
      document.getElementById("ssid").textContent = sub;
    }).catch(function () { linkDot.className = "dot off"; });
  }
  setInterval(poll, 1000);
  poll();
})();
</script>
</body>
</html>
)HTML";

#endif  // ROVER_WEB_UI_H
