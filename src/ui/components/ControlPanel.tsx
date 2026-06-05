import { useState, useCallback } from 'react';
import type { ControlValues } from '../hooks/useRuntime';

interface Props {
  onChange: (values: ControlValues) => void;
}

const SLIDERS: { key: keyof ControlValues; label: string; default: number; color: string }[] = [
  { key: 'energy',    label: 'ENERGY',    default: 0.5, color: '#f4a' },
  { key: 'chaos',     label: 'CHAOS',     default: 0.2, color: '#fa4' },
  { key: 'stability', label: 'STABILITY', default: 0.5, color: '#4af' },
  { key: 'groove',    label: 'GROOVE',    default: 0.5, color: '#4fa' },
];

const s: Record<string, React.CSSProperties> = {
  root: {
    display: 'flex', flexDirection: 'column', gap: 16,
    padding: '16px 20px',
    borderRight: '1px solid #222',
    width: 220, flexShrink: 0,
  },
  heading: { color: '#888', letterSpacing: 2, fontSize: 11, marginBottom: 4 },
  row: { display: 'flex', flexDirection: 'column', gap: 4 },
  label: { fontSize: 10, letterSpacing: 2, color: '#666' },
  sliderWrap: { display: 'flex', alignItems: 'center', gap: 8 },
  value: { width: 32, textAlign: 'right', color: '#888', fontSize: 11 },
};

export function ControlPanel({ onChange }: Props) {
  const [values, setValues] = useState<ControlValues>(() => {
    const init: Record<string, number> = {};
    for (const sl of SLIDERS) init[sl.key] = sl.default;
    return init as ControlValues;
  });

  const update = useCallback((key: keyof ControlValues, raw: string) => {
    const v = parseFloat(raw);
    const next = { ...values, [key]: v };
    setValues(next);
    onChange(next);
  }, [values, onChange]);

  return (
    <div style={s.root}>
      <div style={s.heading}>CONTROL SURFACE</div>
      {SLIDERS.map(sl => (
        <div key={sl.key} style={s.row}>
          <div style={s.label}>{sl.label}</div>
          <div style={s.sliderWrap}>
            <input
              type="range" min="0" max="1" step="0.01"
              value={values[sl.key]}
              onChange={e => update(sl.key, e.target.value)}
              style={{
                flex: 1, height: 4, accentColor: sl.color,
                cursor: 'pointer',
              }}
            />
            <span style={s.value}>{values[sl.key].toFixed(2)}</span>
          </div>
          {/* Fill bar */}
          <div style={{ height: 2, background: '#1a1a1a', borderRadius: 1 }}>
            <div style={{ width: `${values[sl.key] * 100}%`, height: '100%', background: sl.color, borderRadius: 1, transition: 'width 0.05s' }} />
          </div>
        </div>
      ))}
    </div>
  );
}
