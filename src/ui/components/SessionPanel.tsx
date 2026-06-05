interface Props {
  frameCount:   number;
  mode:         string;
  onReplay:     () => void;
  onStop:       () => void;
  onReset:      () => void;
  onSave:       () => void;
}

const BTN: React.CSSProperties = {
  background: '#1a1a22', border: '1px solid #333', color: '#aaa',
  padding: '6px 14px', borderRadius: 3, cursor: 'pointer',
  fontSize: 11, letterSpacing: 1,
  transition: 'border-color 0.1s, color 0.1s',
};

const BTN_ACTIVE: React.CSSProperties = { ...BTN, borderColor: '#4af', color: '#4af' };

export function SessionPanel({ frameCount, mode, onReplay, onStop, onReset, onSave }: Props) {
  const isReplaying = mode === 'replaying';

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 12,
      padding: '16px 20px',
      borderLeft: '1px solid #222', width: 200, flexShrink: 0,
    }}>
      <div style={{ color: '#444', fontSize: 10, letterSpacing: 2 }}>SESSION</div>

      <div style={{ color: '#666', fontSize: 11 }}>
        <span style={{ color: '#888' }}>{frameCount}</span> frames captured
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <button
          style={isReplaying ? BTN_ACTIVE : BTN}
          onClick={isReplaying ? onStop : onReplay}
          disabled={frameCount === 0}
        >
          {isReplaying ? '⏹ STOP' : '▶ REPLAY'}
        </button>

        <button style={BTN} onClick={onSave} disabled={frameCount === 0}>
          ↓ SAVE JSON
        </button>

        <button
          style={{ ...BTN, color: '#f44', borderColor: '#622' }}
          onClick={onReset}
        >
          ↺ RESET
        </button>
      </div>

      <div style={{ marginTop: 8, borderTop: '1px solid #1a1a1a', paddingTop: 12 }}>
        <div style={{ color: '#333', fontSize: 10, letterSpacing: 1, marginBottom: 6 }}>TIPS</div>
        <div style={{ color: '#333', fontSize: 10, lineHeight: 1.6 }}>
          Move sliders to shape behavior.<br />
          Click timeline to fork from that moment.<br />
          Bright bars = policy path.
        </div>
      </div>
    </div>
  );
}
