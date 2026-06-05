import type { PerformanceState } from '../../core/PerformanceState';

interface Props {
  state:         PerformanceState;
  env:           string;
  identityScore: number;
  frameIndex:    number;
  mode:          string;
}

const ENV_COLOR: Record<string, string> = {
  cinematic: '#4af',
  precision: '#4fa',
  chaosJam:  '#fa4',
};

const METRICS: { key: keyof PerformanceState; label: string; color: string }[] = [
  { key: 'energy',    label: 'ENERGY',    color: '#f4a' },
  { key: 'groove',    label: 'GROOVE',    color: '#4fa' },
  { key: 'stability', label: 'STABILITY', color: '#4af' },
  { key: 'chaos',     label: 'CHAOS',     color: '#fa4' },
  { key: 'tension',   label: 'TENSION',   color: '#a4f' },
  { key: 'drift',     label: 'DRIFT',     color: '#f84' },
];

function Bar({ value, color }: { value: number; color: string }) {
  return (
    <div style={{ height: 6, background: '#1a1a1a', borderRadius: 3, overflow: 'hidden' }}>
      <div style={{
        height: '100%',
        width: `${Math.min(1, Math.max(0, value)) * 100}%`,
        background: color,
        borderRadius: 3,
        transition: 'width 0.08s ease-out',
      }} />
    </div>
  );
}

export function StateViewer({ state, env, identityScore, frameIndex, mode }: Props) {
  const envColor = ENV_COLOR[env] ?? '#888';
  const modeColor = mode === 'replaying' ? '#fa4' : mode === 'forked' ? '#a4f' : '#4af';

  return (
    <div style={{ flex: 1, padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ color: '#444', fontSize: 11, letterSpacing: 2 }}>BEHAVIORAL STATE</span>
        <span style={{ marginLeft: 'auto', color: '#444', fontSize: 11 }}>
          frame <span style={{ color: '#666' }}>{frameIndex}</span>
        </span>
      </div>

      {/* Environment badge + mode */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <div style={{
          padding: '4px 12px', borderRadius: 3,
          background: `${envColor}22`, border: `1px solid ${envColor}66`,
          color: envColor, fontSize: 11, letterSpacing: 2, fontWeight: 'bold',
        }}>
          {env.toUpperCase()}
        </div>
        <div style={{
          padding: '4px 10px', borderRadius: 3,
          background: `${modeColor}11`, border: `1px solid ${modeColor}44`,
          color: modeColor, fontSize: 10, letterSpacing: 1,
        }}>
          {mode}
        </div>
      </div>

      {/* Metric bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {METRICS.map(m => {
          const raw = state[m.key];
          const val = typeof raw === 'number' ? raw : 0;
          return (
            <div key={m.key} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#555', letterSpacing: 1 }}>
                <span>{m.label}</span>
                <span style={{ color: m.color }}>{val.toFixed(3)}</span>
              </div>
              <Bar value={val} color={m.color} />
            </div>
          );
        })}
      </div>

      {/* Identity score */}
      <div style={{ marginTop: 'auto', borderTop: '1px solid #1a1a1a', paddingTop: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ color: '#444', fontSize: 10, letterSpacing: 2 }}>IDENTITY QUALITY</span>
          <span style={{
            fontSize: 18, fontWeight: 'bold',
            color: identityScore > 0.7 ? '#4fa' : identityScore > 0.4 ? '#fa4' : '#f44',
          }}>
            {identityScore.toFixed(3)}
          </span>
        </div>
        <Bar value={identityScore} color={identityScore > 0.7 ? '#4fa' : identityScore > 0.4 ? '#fa4' : '#f44'} />
      </div>
    </div>
  );
}
