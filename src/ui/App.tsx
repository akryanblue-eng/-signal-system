import { useCallback } from 'react';
import { useRuntime } from './hooks/useRuntime';
import { ControlPanel } from './components/ControlPanel';
import { StateViewer } from './components/StateViewer';
import { TimelineView } from './components/TimelineView';
import { SessionPanel } from './components/SessionPanel';

export default function App() {
  const { display, setControl, replay, stopReplay, fork, reset, saveSession } = useRuntime();
  const { state, env, trace, mode, frame } = display;

  const handleFork = useCallback((idx: number) => {
    fork(idx);
  }, [fork]);

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      height: '100vh', background: '#0b0b0f',
    }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 20px', borderBottom: '1px solid #1a1a1a',
        background: '#0d0d12',
      }}>
        <span style={{ color: '#4af', fontWeight: 'bold', fontSize: 13, letterSpacing: 2 }}>
          ◈ SIGNAL SYSTEM
        </span>
        <span style={{ color: '#2a2a3a', fontSize: 11 }}>|</span>
        <span style={{ color: '#333', fontSize: 11, letterSpacing: 1 }}>
          BEHAVIORAL INSTRUMENT
        </span>
      </div>

      {/* Main area */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <ControlPanel onChange={setControl} />
        <StateViewer
          state={state}
          env={env}
          identityScore={display.trace.at(-1)?.identityScore ?? 0}
          frameIndex={frame}
          mode={mode}
        />
        <SessionPanel
          frameCount={trace.length}
          mode={mode}
          onReplay={replay}
          onStop={stopReplay}
          onReset={reset}
          onSave={saveSession}
        />
      </div>

      {/* Timeline */}
      <TimelineView
        frames={trace}
        onFork={handleFork}
        isReplaying={mode === 'replaying'}
      />
    </div>
  );
}
