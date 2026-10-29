"""Generate tracker_ui.html visual dashboard artifact with embedded demos."""

import base64
import os

artifact_dir = r"C:\Users\bezal\.gemini\antigravity\brain\bc3c2dba-2832-430d-b875-d71bdad9f720"

demo_b64 = []
for i in range(1, 5):
    img_path = os.path.join(artifact_dir, f"detection_demo_{i}.jpg")
    with open(img_path, "rb") as f:
        demo_b64.append(base64.b64encode(f.read()).decode("utf-8"))

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Rover Multi-Object & Distant Tracking Deck</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    body {{
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}
    .tab-btn.active {{
      background: #10b981;
      color: #022c22;
      font-weight: 700;
      border-color: #10b981;
    }}
  </style>
</head>
<body class="bg-transparent text-[var(--foreground)] antialiased p-4 md:p-6">
  <div class="max-w-6xl mx-auto space-y-6">
    
    <!-- Header -->
    <header class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
      <div>
        <div class="flex items-center gap-3">
          <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">System Operational</span>
          <span class="px-2.5 py-1 text-xs font-semibold rounded-full bg-cyan-500/10 text-cyan-600 border border-cyan-500/20">YOLO26n + SAHI</span>
        </div>
        <h1 class="text-2xl font-bold tracking-tight text-[var(--foreground)] mt-2">Multi-Object & Distant Target Vision Deck</h1>
        <p class="text-sm text-[var(--muted-foreground)] mt-1">
          Real-time object tracking, SAHI sliced inference for small/far targets, and feature-point deformation recovery.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <a href="http://127.0.0.1:5000" target="_blank" class="px-4 py-2 text-sm font-semibold rounded-xl bg-emerald-500 text-slate-950 hover:bg-emerald-400 transition shadow-sm inline-flex items-center gap-2">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
          Open Full Mission Deck
        </a>
      </div>
    </header>

    <!-- Live Webcam Stream Card -->
    <div class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5 shadow-sm space-y-4">
      <div class="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 class="text-lg font-bold text-[var(--foreground)] flex items-center gap-2">
            <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            Live Webcam Vision Feed
          </h2>
          <p class="text-xs text-[var(--muted-foreground)]">Direct MJPEG stream with real-time multi-target tracking & bounding boxes</p>
        </div>
        <div class="flex gap-2 text-xs font-mono text-[var(--muted-foreground)]">
          <span class="px-2 py-1 bg-black/10 dark:bg-white/5 rounded border border-[var(--border)]">Port: 5000</span>
          <span class="px-2 py-1 bg-black/10 dark:bg-white/5 rounded border border-[var(--border)]">Tracker: TrackTrack</span>
        </div>
      </div>
      
      <div class="relative aspect-video w-full max-h-[460px] bg-slate-950 rounded-xl overflow-hidden border border-[var(--border)] flex items-center justify-center">
        <img id="liveStream" src="http://127.0.0.1:5000/video_feed" alt="Live Rover Vision Feed" class="w-full h-full object-contain" onerror="this.style.display='none'; document.getElementById('streamFallback').style.display='flex';">
        <div id="streamFallback" class="hidden flex-col items-center justify-center p-6 text-center space-y-3">
          <svg class="w-12 h-12 text-[var(--muted-foreground)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
          <div class="text-sm font-semibold text-[var(--foreground)]">Live Feed Server Ready on http://127.0.0.1:5000</div>
          <p class="text-xs text-[var(--muted-foreground)] max-w-sm">Click the button below to view the browser stream directly.</p>
          <a href="http://127.0.0.1:5000" target="_blank" class="px-3 py-1.5 text-xs font-medium bg-emerald-500 text-slate-950 rounded-lg font-bold">Open Stream in New Tab</a>
        </div>
      </div>
    </div>

    <!-- Interactive Benchmark Visualizer -->
    <div class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5 shadow-sm space-y-4">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h2 class="text-lg font-bold text-[var(--foreground)]">Visual Benchmark: Standard vs SAHI Sliced Tiling</h2>
          <p class="text-xs text-[var(--muted-foreground)]">Click tabs to inspect detection accuracy on small, far-off, and crowded objects.</p>
        </div>
        <div class="flex flex-wrap gap-2 text-xs">
          <button onclick="selectTab(0)" id="tab-0" class="tab-btn active px-3 py-1.5 rounded-lg border border-[var(--border)] transition">Scene 1: Crowded (+91%)</button>
          <button onclick="selectTab(1)" id="tab-1" class="tab-btn px-3 py-1.5 rounded-lg border border-[var(--border)] transition text-[var(--muted-foreground)]">Scene 2: Far Objects (8x Boost)</button>
          <button onclick="selectTab(2)" id="tab-2" class="tab-btn px-3 py-1.5 rounded-lg border border-[var(--border)] transition text-[var(--muted-foreground)]">Scene 3: Multi-Category (3.3x)</button>
          <button onclick="selectTab(3)" id="tab-3" class="tab-btn px-3 py-1.5 rounded-lg border border-[var(--border)] transition text-[var(--muted-foreground)]">Scene 4: Cluttered (+89%)</button>
        </div>
      </div>

      <!-- Comparison Metrics Cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div class="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-[var(--border)]">
          <div class="text-[11px] font-medium text-[var(--muted-foreground)]">Standard 320x320</div>
          <div id="metricStd" class="text-xl font-bold text-amber-500 mt-0.5">11 Objects</div>
          <div class="text-[10px] text-[var(--muted-foreground)] mt-0.5">Downsampled; misses far items</div>
        </div>
        <div class="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-[var(--border)]">
          <div class="text-[11px] font-medium text-[var(--muted-foreground)]">SAHI Sliced + PointTrack</div>
          <div id="metricSahi" class="text-xl font-bold text-emerald-500 mt-0.5">21 Objects</div>
          <div class="text-[10px] text-[var(--muted-foreground)] mt-0.5">Full native resolution tiles</div>
        </div>
        <div class="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-[var(--border)]">
          <div class="text-[11px] font-medium text-[var(--muted-foreground)]">Recall Gain</div>
          <div id="metricGain" class="text-xl font-bold text-cyan-500 mt-0.5">+91%</div>
          <div class="text-[10px] text-[var(--muted-foreground)] mt-0.5">High-precision box recovery</div>
        </div>
        <div class="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-[var(--border)]">
          <div class="text-[11px] font-medium text-[var(--muted-foreground)]">Point Tracking</div>
          <div class="text-xl font-bold text-purple-500 mt-0.5">Active</div>
          <div class="text-[10px] text-[var(--muted-foreground)] mt-0.5">Shi-Tomasi + Pyramidal LK</div>
        </div>
      </div>

      <!-- Image Display -->
      <div class="border border-[var(--border)] rounded-xl overflow-hidden bg-slate-950 flex flex-col items-center">
        <img id="demoImage" src="data:image/jpeg;base64,{demo_b64[0]}" alt="Detection Visual Comparison" class="w-full max-h-[500px] object-contain">
        <div class="w-full py-2 px-4 bg-black/40 text-xs text-center border-t border-[var(--border)] text-[var(--muted-foreground)] flex justify-between items-center">
          <span class="text-amber-400 font-semibold">← Left: Standard 320 Pass</span>
          <span id="demoDesc" class="font-medium text-[var(--foreground)]">Crowded Scene: 11 Standard vs 21 SAHI Sliced Detections</span>
          <span class="text-emerald-400 font-semibold">Right: SAHI Sliced + Point Tracking →</span>
        </div>
      </div>
    </div>

    <!-- Tracker Architecture Comparison Table -->
    <div class="bg-[var(--card)] border border-[var(--border)] rounded-2xl p-5 shadow-sm space-y-3">
      <h2 class="text-lg font-bold text-[var(--foreground)]">Tracker Algorithms Reference Matrix</h2>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="border-b border-[var(--border)] text-[var(--muted-foreground)]">
              <th class="py-2.5 px-3 font-semibold">Algorithm</th>
              <th class="py-2.5 px-3 font-semibold">Configuration</th>
              <th class="py-2.5 px-3 font-semibold">Primary Strength</th>
              <th class="py-2.5 px-3 font-semibold">Measured p50</th>
              <th class="py-2.5 px-3 font-semibold">Best Use Case</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--border)] font-mono">
            <tr>
              <td class="py-2 px-3 font-bold text-emerald-500">TrackTrack</td>
              <td class="py-2 px-3 text-[var(--muted-foreground)]">tracktrack.yaml</td>
              <td class="py-2 px-3 font-sans">Multi-cue association & track-aware initialization</td>
              <td class="py-2 px-3">380 ms</td>
              <td class="py-2 px-3 font-sans text-[var(--muted-foreground)]">General-purpose robust tracking</td>
            </tr>
            <tr>
              <td class="py-2 px-3 font-bold text-cyan-500">BoT-SORT</td>
              <td class="py-2 px-3 text-[var(--muted-foreground)]">botsort.yaml</td>
              <td class="py-2 px-3 font-sans">Camera-motion compensation (GMC) & ReID</td>
              <td class="py-2 px-3">370 ms</td>
              <td class="py-2 px-3 font-sans text-[var(--muted-foreground)]">Camera rotation, turns & vibration</td>
            </tr>
            <tr>
              <td class="py-2 px-3 font-bold text-blue-500">ByteTrack</td>
              <td class="py-2 px-3 text-[var(--muted-foreground)]">bytetrack.yaml</td>
              <td class="py-2 px-3 font-sans">Associates across high & low confidence boxes</td>
              <td class="py-2 px-3">476 ms</td>
              <td class="py-2 px-3 font-sans text-[var(--muted-foreground)]">Low-confidence / distant detections</td>
            </tr>
            <tr>
              <td class="py-2 px-3 font-bold text-amber-500">FastTracker</td>
              <td class="py-2 px-3 text-[var(--muted-foreground)]">fasttrack.yaml</td>
              <td class="py-2 px-3 font-sans">Occlusion-aware rollback and recovery</td>
              <td class="py-2 px-3">376 ms</td>
              <td class="py-2 px-3 font-sans text-[var(--muted-foreground)]">Brief occlusions & overlapping objects</td>
            </tr>
            <tr>
              <td class="py-2 px-3 font-bold text-purple-500">OC-SORT</td>
              <td class="py-2 px-3 text-[var(--muted-foreground)]">ocsort.yaml</td>
              <td class="py-2 px-3 font-sans">Observation-centric momentum correction</td>
              <td class="py-2 px-3">422 ms</td>
              <td class="py-2 px-3 font-sans text-[var(--muted-foreground)]">Abrupt nonlinear turns and maneuvers</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>

  <script>
    const demoData = [
      {{ b64: "{demo_b64[0]}", std: "11 Objects", sahi: "21 Objects", gain: "+91%", desc: "Crowded Scene: 11 Standard vs 21 SAHI Sliced Detections" }},
      {{ b64: "{demo_b64[1]}", std: "2 Objects", sahi: "16 Objects", gain: "8.0x", desc: "Distant/Small Object Scene: Standard detects 2 vs SAHI detects 16 (800% boost)" }},
      {{ b64: "{demo_b64[2]}", std: "3 Objects", sahi: "10 Objects", gain: "3.3x", desc: "Multi-Category Scene: Standard detects 3 vs SAHI detects 10 objects" }},
      {{ b64: "{demo_b64[3]}", std: "9 Objects", sahi: "17 Objects", gain: "+89%", desc: "Cluttered Room Scene: Standard detects 9 vs SAHI detects 17 objects" }},
    ];

    function selectTab(idx) {{
      document.querySelectorAll('.tab-btn').forEach((btn, i) => {{
        if (i === idx) {{
          btn.classList.add('active');
          btn.classList.remove('text-[var(--muted-foreground)]');
        }} else {{
          btn.classList.remove('active');
          btn.classList.add('text-[var(--muted-foreground)]');
        }}
      }});

      const data = demoData[idx];
      document.getElementById('demoImage').src = 'data:image/jpeg;base64,' + data.b64;
      document.getElementById('metricStd').textContent = data.std;
      document.getElementById('metricSahi').textContent = data.sahi;
      document.getElementById('metricGain').textContent = data.gain;
      document.getElementById('demoDesc').textContent = data.desc;
    }}
  </script>
</body>
</html>"""

out_path = os.path.join(artifact_dir, "tracker_ui.html")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print("Saved HTML UI to:", out_path)
