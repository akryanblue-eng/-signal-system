import { useRef, useCallback } from 'react';
import type { Frame } from '../../replay/TraceBuffer';

interface Props {
  frames:        Frame[];
  onFork:        (index: number) => void;
  isReplaying:   boolean;
}

const ENV_COLOR: Record<string, string> = {
  cinematic: '#4af',
  precision: '#4fa',
  chaosJam:  '#fa4',
};

export function TimelineView({ frames, onFork, isReplaying }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  const handleClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (isReplaying || frames.length === 0) return;
    const rect  = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    const idx   = Math.floor(ratio * frames.length);
    onFork(Math.min(idx, frames.length - 1));
  }, [frames, onFork, isReplaying]);

  return (
    <div style={{
      borderTop: '1px solid #222', background: '#0d0d12',
      padding: '8px 0',
    }}>
      {/* Label row */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '0 16px', marginBottom: 6,
      }}>
        <span style={{ color: '#444', fontSize: 10, letterSpacing: 2 }}>
          TIMELINE — {frames.length} frames
        </span>
        <span style={{ color: '#333', fontSize: 10 }}>click to fork</span>
      </div>

      {/* Track */}
      <div
        ref={containerRef}
        onClick={handleClick}
        style={{
          height: 48, margin: '0 16px',
          cursor: isReplaying ? 'default' : 'crosshair',
          position: 'relative', display: 'flex', alignItems: 'flex-end', gap: 1,
        }}
      >
        {frames.map((f, i) => {
          const color = ENV_COLOR[f.env] ?? '#555';
          const h     = Math.max(4, f.identityScore * 44);
          const alpha = f.usedPolicy ? 'ff' : '77';
          return (
            <div
              key={i}
              title={`t=${f.t} | ${f.env} | id=${f.identityScore.toFixed(2)} | ${f.thought}`}
              style={{
                flex: '0 0 3px',
                height: h,
                background: `${color}${alpha}`,
                borderRadius: 1,
              }}
            />
          );
        })}

        {/* Replay cursor overlay */}
        {isReplaying && frames.length > 0 && (
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
            background: 'linear-gradient(90deg, transparent, #0d0d12aa)',
            pointerEvents: 'none',
          }} />
        )}
      </div>

      {/* Legend */}
      <div style={{
        display: 'flex', gap: 16, padding: '6px 16px 0',
        fontSize: 10, color: '#444', letterSpacing: 1,
      }}>
        {Object.entries(ENV_COLOR).map(([name, color]) => (
          <span key={name} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, background: color, display: 'inline-block', borderRadius: 1 }} />
            {name}
          </span>
        ))}
        <span style={{ marginLeft: 'auto', color: '#333' }}>
          bright = policy path &nbsp;|&nbsp; dim = oracle fallback
        </span>
      </div>
    </div>
  );
}
