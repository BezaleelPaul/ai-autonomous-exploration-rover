/**
 * AeroPulse Orbital Deck — Live 2D LiDAR & Perception Radar Scanner
 * Sweeps a 360-degree radar beam and plots real-time target blips with phosphor trail.
 */

class RadarScanner {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');
    this.angle = 0;
    this.targets = [
      { angle: 0.8, dist: 75, class: 'sample_target', color: '#00f2fe', label: 'SAMPLE #01' },
      { angle: 2.2, dist: 95, class: 'crater_rim', color: '#f59e0b', label: 'CRATER #04' },
      { angle: 4.5, dist: 50, class: 'basalt_rock', color: '#10b981', label: 'ROCK #12' }
    ];
    this.init();
  }

  init() {
    this.render();
  }

  updateTargets(visionDetections) {
    if (!visionDetections || visionDetections.length === 0) return;
    this.targets = visionDetections.map((d, i) => {
      const angle = (i * 1.8 + 0.5) % (Math.PI * 2);
      const dist = Math.min(110, Math.max(30, d.dist_m * 15));
      const color = d.class === 'sample_target' ? '#00f2fe' : (d.class === 'crater_rim' ? '#f59e0b' : '#10b981');
      return { angle, dist, class: d.class, color, label: `${d.class.toUpperCase()} [${Math.round(d.confidence*100)}%]` };
    });
  }

  render() {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;
    const cx = w / 2;
    const cy = h / 2;
    const radius = Math.min(cx, cy) - 20;

    // Faded trailing wipe
    ctx.fillStyle = 'rgba(7, 9, 14, 0.12)';
    ctx.fillRect(0, 0, w, h);

    // Draw Polar Range Rings
    ctx.strokeStyle = 'rgba(0, 242, 254, 0.15)';
    ctx.lineWidth = 1;
    [0.33, 0.66, 1.0].forEach(factor => {
      ctx.beginPath();
      ctx.arc(cx, cy, radius * factor, 0, Math.PI * 2);
      ctx.stroke();
    });

    // Crosshairs
    ctx.beginPath();
    ctx.moveTo(cx - radius, cy);
    ctx.lineTo(cx + radius, cy);
    ctx.moveTo(cx, cy - radius);
    ctx.lineTo(cx, cy + radius);
    ctx.stroke();

    // Sweeping Radar Beam
    this.angle += 0.035;
    if (this.angle > Math.PI * 2) this.angle = 0;

    const beamX = cx + Math.cos(this.angle) * radius;
    const beamY = cy + Math.sin(this.angle) * radius;

    // Beam Line
    ctx.strokeStyle = 'rgba(0, 242, 254, 0.7)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(beamX, beamY);
    ctx.stroke();

    // Sweep Sector Gradient
    const sweepGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
    sweepGrad.addColorStop(0, 'rgba(0, 242, 254, 0.0)');
    sweepGrad.addColorStop(1, 'rgba(0, 242, 254, 0.08)');
    ctx.fillStyle = sweepGrad;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, radius, this.angle - 0.4, this.angle);
    ctx.closePath();
    ctx.fill();

    // Plot Targets
    this.targets.forEach(t => {
      const tx = cx + Math.cos(t.angle) * t.dist;
      const ty = cy + Math.sin(t.angle) * t.dist;

      // Target Reticle
      ctx.fillStyle = t.color;
      ctx.beginPath();
      ctx.arc(tx, ty, 3.5, 0, Math.PI * 2);
      ctx.fill();

      // Pulsing Ring
      ctx.strokeStyle = t.color;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(tx, ty, 7 + Math.sin(Date.now() * 0.005) * 2, 0, Math.PI * 2);
      ctx.stroke();

      // Label
      ctx.fillStyle = 'rgba(255, 255, 255, 0.75)';
      ctx.font = '9px monospace';
      ctx.fillText(t.label, tx + 10, ty + 3);
    });

    requestAnimationFrame(() => this.render());
  }
}

window.RadarScanner = RadarScanner;
