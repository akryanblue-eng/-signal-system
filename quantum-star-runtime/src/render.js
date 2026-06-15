// render.js consumes visual state only — downstream of everything.
// Uses state.t for animation so rendering is also deterministic.

export function render(ctx, vis) {
  const { width: W, height: H } = ctx.canvas;
  const { padGlow, padCount, pulseRate, trailDensity, chaosShake,
          backgroundColor, accentColor, entropyFlicker, t } = vis;

  // Chaos shake transform
  const shake = chaosShake * 4;
  const ox = shake > 0 ? (Math.random() - 0.5) * shake : 0;
  const oy = shake > 0 ? (Math.random() - 0.5) * shake : 0;
  ctx.save();
  ctx.translate(ox, oy);

  ctx.fillStyle = backgroundColor;
  ctx.fillRect(-shake, -shake, W + shake * 2, H + shake * 2);

  // Center pulse ring — driven by t (deterministic, not Date.now)
  const cx = W / 2;
  const cy = H * 0.42;
  const pulse = Math.sin(t * Math.PI * 2 * (0.5 + pulseRate * 1.5)) * 0.5 + 0.5;
  const r = 40 + pulseRate * 60 + pulse * 20;

  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.strokeStyle = accentColor;
  ctx.globalAlpha = 0.3 + padGlow * 0.6 + entropyFlicker * 0.1 * Math.random();
  ctx.lineWidth = 1 + trailDensity * 5;
  ctx.stroke();

  // Inner ring
  ctx.beginPath();
  ctx.arc(cx, cy, r * 0.4, 0, Math.PI * 2);
  ctx.strokeStyle = accentColor;
  ctx.globalAlpha = padGlow * 0.8;
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.globalAlpha = 1;

  // Pads at bottom
  const gap = 6;
  const totalGap = gap * (padCount + 1);
  const padW = (W - totalGap) / padCount;
  const padH = 72;
  const padY = H - padH - 16;

  for (let i = 0; i < padCount; i++) {
    const x = gap + i * (padW + gap);
    const glow = padGlow + pulse * 0.15;
    ctx.fillStyle = accentColor;
    ctx.globalAlpha = 0.1 + glow * 0.5;
    ctx.fillRect(x, padY, padW, padH);

    // Top edge highlight
    ctx.fillStyle = accentColor;
    ctx.globalAlpha = 0.4 + glow * 0.6;
    ctx.fillRect(x, padY, padW, 2);
  }

  ctx.globalAlpha = 1;
  ctx.restore();
}
