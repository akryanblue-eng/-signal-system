import type { RuntimeSnapshot } from '../core/manifold/RuntimeSnapshot';
import type { SteeringState } from '../core/manifold/SteeringState';
import { forceAlignment } from '../core/manifold/SteeringState';

const PANEL_CSS = `
  position: fixed; top: 16px; left: 16px; z-index: 1000;
  background: rgba(8, 8, 18, 0.88); color: #00ffcc;
  font: 12px/1.8 'Courier New', monospace; padding: 12px 16px; border-radius: 6px;
  pointer-events: none; min-width: 240px; border: 1px solid rgba(0,255,204,0.2);
  backdrop-filter: blur(4px);
`.replace(/\s+/g, ' ').trim();

/**
 * Minimal DOM overlay that shows the live runtime state snapshot.
 * No framework required — pure DOM.
 *
 * Usage:
 *   const inspector = new RuntimeInspector(document.body);
 *   // in your render loop:
 *   inspector.update(runtime.getLatestSnapshot(), runtime.getSteeringState());
 */
export class RuntimeInspector {
  private el: HTMLElement;

  constructor(parent: HTMLElement = document.body) {
    this.el = document.createElement('pre');
    this.el.setAttribute('style', PANEL_CSS);
    parent.appendChild(this.el);
  }

  update(
    snapshot:  RuntimeSnapshot | null,
    steering:  SteeringState | null = null,
    attractor = 'Pocket',
  ): void {
    if (!snapshot) {
      this.el.textContent = '— awaiting first frame —';
      return;
    }

    const alignment = steering ? forceAlignment(steering) : 0;
    const alignLabel = alignment > 0.5 ? '✔ aligned' : alignment < -0.3 ? '✖ fighting' : '~ neutral';

    this.el.innerHTML = [
      header(`FRAME ${snapshot.frame.toString().padStart(6, '0')}`),
      row('DRIFT',      snapshot.drift),
      row('ENERGY',     snapshot.energy),
      row('STABILITY',  snapshot.stability),
      row('CHAOS',      snapshot.chaos),
      plain('ATTRACTOR', attractor.padEnd(14)),
      row('PULL',       snapshot.attractorPull),
      row('PRESSURE',   snapshot.driftPressure),
      plain('TIMING',   fmt(snapshot.timingOffset) + ' ms'),
      separator(),
      plain('STEERING', alignLabel),
      ...(steering ? [
        vec2row('PERFORMER', steering.performerForce, '#4488ff'),
        vec2row('KERNEL',    steering.kernelForce,    '#44ff88'),
        vec2row('FINAL',     steering.finalForce,     '#ffffff'),
      ] : []),
    ].join('');
  }

  dispose(): void {
    this.el.remove();
  }
}

// ─── Rendering helpers ────────────────────────────────────────────────────────

function header(text: string): string {
  return `<span style="color:#ffffff;font-weight:bold">${text}</span>\n`;
}

function separator(): string {
  return `<span style="color:#223333">${'─'.repeat(28)}</span>\n`;
}

function plain(label: string, value: string): string {
  return `<span style="color:#556677">${label.padEnd(12)}</span><span style="color:#aaccbb">${value}</span>\n`;
}

function row(label: string, value: number): string {
  const clamped = Math.min(Math.max(value, 0), 1);
  const filled  = Math.round(clamped * 12);
  const bar     = '█'.repeat(filled) + '░'.repeat(12 - filled);
  const color   = barColor(clamped);
  return [
    `<span style="color:#556677">${label.padEnd(12)}</span>`,
    `<span style="color:${color}">${bar}</span>`,
    `<span style="color:#aaccbb"> ${fmt(value)}</span>`,
    '\n',
  ].join('');
}

function vec2row(label: string, v: readonly [number, number], color: string): string {
  return [
    `<span style="color:#334455"> ${label.padEnd(10)}</span>`,
    `<span style="color:${color}">[${fmt(v[0])}, ${fmt(v[1])}]</span>`,
    '\n',
  ].join('');
}

function fmt(n: number): string {
  return (n >= 0 ? '+' : '') + n.toFixed(3);
}

function barColor(t: number): string {
  if (t > 0.8) return '#ff4444';
  if (t > 0.5) return '#ffaa44';
  if (t > 0.3) return '#44ffaa';
  return '#44aaff';
}
