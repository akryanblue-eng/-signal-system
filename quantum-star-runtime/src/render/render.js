// render.js: time-blind canvas layer.
// Input: visual state from SkinRuntime only.
// Forbidden: event access, dt, Date.now(). Animation driven by state.t exclusively.
export function render(ctx, vis) {
  const { width: W, height: H } = ctx.canvas;
  const {
    padCount, padGlow, ringGlow, pulseRate, pulseAmount,
    trailDensity, chaosShake, distortion, flashAmount,
    backgroundColor, accentColor, entropyFlicker, t,
  } = vis;

  const shake = (chaosShake + distortion) * 3;
  const ox = shake > 0 ? (Math.random() - 0.5) * shake : 0;
  const oy = shake > 0 ? (Math.random() - 0.5) * shake : 0;
  ctx.save();
  ctx.translate(ox, oy);

  ctx.fillStyle = backgroundColor;
  ctx.fillRect(-shake, -shake, W + shake * 2, H + shake * 2);

  // Center pulse ring — animation driven by state.t, not Date.now
  const cx  = W / 2;
  const cy  = H * 0.40;
  const osc = Math.sin(t * Math.PI * 2 * (0.5 + pulseRate * 1.5)) * 0.5 + 0.5;
  const r   = 45 + ringGlow * 55 + osc * 15 + pulseAmount * 25;

  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.strokeStyle = accentColor;
  ctx.globalAlpha = 0.25 + ringGlow * 0.6 + entropyFlicker * 0.15 * Math.random();
  ctx.lineWidth   = 1 + trailDensity * 4;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(cx, cy, r * 0.38, 0, Math.PI * 2);
  ctx.strokeStyle = accentColor;
  ctx.globalAlpha = ringGlow * 0.7 + osc * 0.2;
  ctx.lineWidth   = 2;
  ctx.stroke();

  ctx.globalAlpha = 1;

  // Pads
  const gap  = 6;
  const padW = (W - gap * (padCount + 1)) / padCount;
  const padH = 72;
  const padY = H - padH - 12;

  for (let i = 0; i < padCount; i++) {
    const x    = gap + i * (padW + gap);
    const glow = padGlow + osc * 0.1 + pulseAmount * 0.2;
    ctx.fillStyle   = accentColor;
    ctx.globalAlpha = 0.08 + glow * 0.55;
    ctx.fillRect(x, padY, padW, padH);
    ctx.globalAlpha = 0.35 + glow * 0.65;
    ctx.fillRect(x, padY, padW, 2);
  }

  ctx.globalAlpha = 1;

  // Flash overlay
  if (flashAmount > 0.01) {
    ctx.fillStyle   = accentColor;
    ctx.globalAlpha = flashAmount * 0.35;
    ctx.fillRect(0, 0, W, H);
    ctx.globalAlpha = 1;
  }

  ctx.restore();
}
