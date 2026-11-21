/**
 * AeroPulse Orbital Deck — Cockpit Interaction Suite
 * Integrated Aceternity 3D Card, Codrops Magnetic & Scramble, GSAP Tweens
 */

document.addEventListener('DOMContentLoaded', () => {

  // ==========================================
  // 1. Text Scrambler Decoder (Codrops Effect)
  // ==========================================
  class TextScrambler {
    constructor(element) {
      this.el = element;
      this.chars = '!<>-_\\/[]{}—=+*^?#________';
      this.queue = [];
      this.frame = 0;
      this.frameRequest = null;
    }

    setText(newText) {
      const oldText = this.el.innerText || '';
      const length = Math.max(oldText.length, newText.length);
      const promise = new Promise(resolve => this.resolve = resolve);
      this.queue = [];
      for (let i = 0; i < length; i++) {
        const from = oldText[i] || '';
        const to = newText[i] || '';
        const start = Math.floor(Math.random() * 15);
        const end = start + Math.floor(Math.random() * 15);
        this.queue.push({ from, to, start, end });
      }
      cancelAnimationFrame(this.frameRequest);
      this.frame = 0;
      this.update();
      return promise;
    }

    update() {
      let output = '';
      let complete = 0;
      for (let i = 0; i < this.queue.length; i++) {
        let { from, to, start, end, char } = this.queue[i];
        if (this.frame >= end) {
          complete++;
          output += to;
        } else if (this.frame >= start) {
          if (!char || Math.random() < 0.28) {
            char = this.chars[Math.floor(Math.random() * this.chars.length)];
            this.queue[i].char = char;
          }
          output += `<span class="text-cyberCyan opacity-75">${char}</span>`;
        } else {
          output += from;
        }
      }
      this.el.innerHTML = output;
      if (complete === this.queue.length) {
        if (this.resolve) this.resolve();
      } else {
        this.frameRequest = requestAnimationFrame(() => this.update());
        this.frame++;
      }
    }
  }

  const logScrambler = new TextScrambler(document.getElementById('log-scramble'));

  // ==========================================
  // 2. Aceternity 3D Tilt Card Effect
  // ==========================================
  const attitudeCard = document.getElementById('card-attitude');
  if (attitudeCard) {
    const parentWrap = attitudeCard.closest('.card-3d-wrap');
    parentWrap.addEventListener('mousemove', (e) => {
      const rect = parentWrap.getBoundingClientRect();
      const x = (e.clientX - rect.left - rect.width / 2) / 12;
      const y = (e.clientY - rect.top - rect.height / 2) / 12;
      attitudeCard.style.transform = `rotateY(${x}deg) rotateX(${-y}deg) scale(1.02)`;
    });

    parentWrap.addEventListener('mouseleave', () => {
      attitudeCard.style.transform = 'rotateY(0deg) rotateX(0deg) scale(1.0)';
    });
  }

  // ==========================================
  // 3. Codrops Magnetic Buttons
  // ==========================================
  document.querySelectorAll('.magnetic-btn').forEach(btn => {
    btn.addEventListener('mousemove', (e) => {
      const rect = btn.getBoundingClientRect();
      const x = (e.clientX - rect.left - rect.width / 2) * 0.35;
      const y = (e.clientY - rect.top - rect.height / 2) * 0.35;
      btn.style.transform = `translate(${x}px, ${y}px)`;
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.transform = 'translate(0px, 0px)';
    });
  });

  // ==========================================
  // 4. Custom HUD Reticle & Spotlight Cursor
  // ==========================================
  const reticle = document.getElementById('hud-reticle');
  const spotlight = document.getElementById('spotlight');

  window.addEventListener('mousemove', (e) => {
    if (reticle) {
      reticle.style.left = `${e.clientX}px`;
      reticle.style.top = `${e.clientY}px`;
    }
    if (spotlight) {
      spotlight.style.left = `${e.clientX}px`;
      spotlight.style.top = `${e.clientY}px`;
    }
  });

  // ==========================================
  // 5. Film Grain Procedural Noise (Codrops)
  // ==========================================
  const noiseCanvas = document.getElementById('noise-canvas');
  if (noiseCanvas) {
    const nCtx = noiseCanvas.getContext('2d');
    const resizeNoise = () => {
      noiseCanvas.width = window.innerWidth;
      noiseCanvas.height = window.innerHeight;
    };
    resizeNoise();
    window.addEventListener('resize', resizeNoise);

    let nFrame = 0;
    const renderNoise = () => {
      nFrame++;
      if (nFrame % 2 === 0) {
        const w = noiseCanvas.width;
        const h = noiseCanvas.height;
        const imgData = nCtx.createImageData(w, h);
        const buf = new Uint32Array(imgData.data.buffer);
        for (let i = 0; i < buf.length; i++) {
          if (Math.random() < 0.05) {
            buf[i] = 0x12000000 | (Math.floor(Math.random() * 255) << 16);
          }
        }
        nCtx.putImageData(imgData, 0, 0);
      }
      requestAnimationFrame(renderNoise);
    };
    renderNoise();
  }

  // ==========================================
  // 6. Meteor & Starfield Canvas (Aceternity)
  // ==========================================
  const meteorCanvas = document.getElementById('meteor-canvas');
  if (meteorCanvas) {
    const mCtx = meteorCanvas.getContext('2d');
    const resizeMeteors = () => {
      meteorCanvas.width = window.innerWidth;
      meteorCanvas.height = window.innerHeight;
    };
    resizeMeteors();
    window.addEventListener('resize', resizeMeteors);

    // Generate static stars
    const stars = Array.from({ length: 90 }, () => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      r: Math.random() * 1.5,
      alpha: Math.random()
    }));

    // Dynamic falling meteors
    const meteors = [];
    const spawnMeteor = () => {
      if (meteors.length < 4 && Math.random() < 0.03) {
        meteors.push({
          x: Math.random() * window.innerWidth,
          y: -20,
          len: 80 + Math.random() * 100,
          speed: 6 + Math.random() * 8,
          angle: Math.PI / 4
        });
      }
    };

    const renderMeteors = () => {
      mCtx.clearRect(0, 0, meteorCanvas.width, meteorCanvas.height);

      // Draw stars
      stars.forEach(s => {
        mCtx.fillStyle = `rgba(255, 255, 255, ${s.alpha * 0.7})`;
        mCtx.beginPath();
        mCtx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        mCtx.fill();
      });

      // Update and draw meteors
      spawnMeteor();
      for (let i = meteors.length - 1; i >= 0; i--) {
        const m = meteors[i];
        m.x += Math.cos(m.angle) * m.speed;
        m.y += Math.sin(m.angle) * m.speed;

        const grad = mCtx.createLinearGradient(
          m.x, m.y,
          m.x - Math.cos(m.angle) * m.len,
          m.y - Math.sin(m.angle) * m.len
        );
        grad.addColorStop(0, 'rgba(0, 242, 254, 0.9)');
        grad.addColorStop(1, 'rgba(0, 242, 254, 0)');

        mCtx.strokeStyle = grad;
        mCtx.lineWidth = 1.8;
        mCtx.beginPath();
        mCtx.moveTo(m.x, m.y);
        mCtx.lineTo(m.x - Math.cos(m.angle) * m.len, m.y - Math.sin(m.angle) * m.len);
        mCtx.stroke();

        if (m.y > window.innerHeight + 100 || m.x > window.innerWidth + 100) {
          meteors.splice(i, 1);
        }
      }

      requestAnimationFrame(renderMeteors);
    };
    renderMeteors();
  }

  // ==========================================
  // 7. Radar Scanner Initialization
  // ==========================================
  const radar = new window.RadarScanner('radar-canvas');

  // ==========================================
  // 8. Live Telemetry Stream (SSE / EventSource)
  // ==========================================
  const sse = new EventSource('/api/stream');

  sse.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      // Attitude & Gyro
      const pitch = data.attitude.pitch_deg;
      const roll = data.attitude.roll_deg;
      const yaw = data.attitude.yaw_deg;

      document.getElementById('pitch-val').innerText = `${pitch.toFixed(2)}°`;
      document.getElementById('roll-val').innerText = `${roll.toFixed(2)}°`;
      document.getElementById('yaw-val').innerText = `${yaw.toFixed(1)}°`;

      const pointer = document.getElementById('gyro-pointer');
      if (pointer) {
        pointer.style.transform = `translate(${roll * 4}px, ${-pitch * 4}px) rotate(${yaw}deg)`;
      }

      // Battery & Motors
      const soc = data.battery.soc_pct;
      document.getElementById('battery-pct').innerText = `${soc.toFixed(1)}%`;
      document.getElementById('battery-bar').style.width = `${soc}%`;
      document.getElementById('battery-v').innerText = `${data.battery.voltage} V`;
      document.getElementById('battery-a').innerText = `${data.battery.current_draw} A DRAW`;
      document.getElementById('battery-temp').innerText = `${data.battery.temp_c} °C`;

      const rpms = data.kinematics.motor_rpm;
      ['fl', 'ml', 'rl', 'fr', 'mr', 'rr'].forEach((key, idx) => {
        const el = document.getElementById(`m-${key}`);
        if (el && rpms[idx] !== undefined) el.innerText = rpms[idx];
      });

      // Sol Time
      const secs = Math.floor(data.mission_time % 60);
      const mins = Math.floor((data.mission_time / 60) % 60);
      const hrs = Math.floor(data.mission_time / 3600);
      document.getElementById('sol-display').innerText = 
        `SOL ${data.sol} // ${String(hrs).padStart(2,'0')}:${String(mins).padStart(2,'0')}:${String(secs).padStart(2,'0')}`;

      // Update radar targets
      if (radar && data.vision && data.vision.detections) {
        radar.updateTargets(data.vision.detections);

        // Update detection list UI
        const dList = document.getElementById('detection-list');
        if (dList && dList.childElementCount === 0) {
          dList.innerHTML = data.vision.detections.map(d => `
            <div class="bg-obsidian/60 p-2 rounded border border-slate-800 text-[10px]">
              <div class="text-cyberCyan font-bold">${d.class.toUpperCase()}</div>
              <div class="text-slate-400">DIST: ${d.dist_m}m | CONF: ${Math.round(d.confidence*100)}%</div>
            </div>
          `).join('');
        }
      }

    } catch (err) {
      console.error('SSE telemetry parse error:', err);
    }
  };

  // ==========================================
  // 9. Command Button Interactivity
  // ==========================================
  const btnDispatch = document.getElementById('btn-dispatch');
  if (btnDispatch) {
    btnDispatch.addEventListener('click', async () => {
      btnDispatch.innerText = 'DISPATCHING...';
      const res = await fetch('/api/nav/dispatch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x: Math.random() * 30 + 10, y: Math.random() * 30 + 10 })
      });
      const json = await res.json();
      btnDispatch.innerText = 'QUEUE NEXT WAYPOINT';
      logScrambler.setText(`WAYPOINT QUEUED: [${json.waypoint.x}, ${json.waypoint.y}] (TOTAL: ${json.total})`);
    });
  }

  const btnHold = document.getElementById('btn-hold');
  if (btnHold) {
    btnHold.addEventListener('click', async () => {
      await fetch('/api/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'HOLD' })
      });
      document.getElementById('mode-badge').innerText = 'HOLD (E-STOP)';
      document.getElementById('mode-badge').className = 'text-sm font-bold text-amberAlert';
      logScrambler.setText('CRITICAL: EMERGENCY HOLD INITIATED. MOTORS DISENGAGED.');
    });
  }

  const btnAuto = document.getElementById('btn-auto');
  if (btnAuto) {
    btnAuto.addEventListener('click', async () => {
      await fetch('/api/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'AUTONOMOUS' })
      });
      document.getElementById('mode-badge').innerText = 'AUTONOMOUS';
      document.getElementById('mode-badge').className = 'text-sm font-bold text-emerald-400';
      logScrambler.setText('SYSTEM RESUMED: AUTONOMOUS KINEMATICS & PERCEPTION ENGAGED.');
    });
  }

});
