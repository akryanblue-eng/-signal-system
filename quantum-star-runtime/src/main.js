import { TimelineClock }  from './clock/TimelineClock.js';
import { BeatTape }       from './tapes/BeatTape.js';
import { PhysicsTape }    from './tapes/PhysicsTape.js';
import { VisualTape }     from './tapes/VisualTape.js';
import { MetaTape }       from './tapes/MetaTape.js';
import { MultiTapeBus }   from './core/MultiTapeBus.js';
import { BeatManiaSkin }  from './systems/SkinRuntime.js';
import { render }         from './render/render.js';

const clock = new TimelineClock();
const tapes = {
  beat:    new BeatTape(),
  physics: new PhysicsTape(),
  visual:  new VisualTape(),
  meta:    new MetaTape(),
};
let bus = new MultiTapeBus();

const canvas = document.getElementById('stage');
const ctx    = canvas.getContext('2d');

// Beat scheduling — no setTimeout; beat boundaries derived from clock cursor
const BPM           = 120;
const BEAT_INTERVAL = 60 / BPM;
let lastBeatTick    = -1;

function emitScheduledBeats(t) {
  const currentTick = Math.floor(t / BEAT_INTERVAL);
  for (let tick = lastBeatTick + 1; tick <= currentTick; tick++) {
    const bt = tick * BEAT_INTERVAL;
    tapes.beat.beat(bt, tick, BPM);
    tapes.visual.pulse(bt, 'ring', 0.5);
  }
  lastBeatTick = currentTick;
}

function loop() {
  requestAnimationFrame(loop);

  const dt = clock.tick();
  const t  = clock.cursor;

  if (clock.isRunning) emitScheduledBeats(t);

  // MultiTapeBus dispatches each tape to its runtime — ZapRuntime sees BeatTape only
  const world = bus.step(dt, t, tapes);
  const vis   = BeatManiaSkin.project(world);

  render(ctx, vis);
  updateHUD(world, t);
}

function updateHUD(world, t) {
  const c = world.zap.core;
  document.getElementById('s-t').textContent       = t.toFixed(2);
  document.getElementById('s-score').textContent   = c.score;
  document.getElementById('s-combo').textContent   = c.comboCount;
  document.getElementById('s-hits').textContent    = c.hitCount;
  document.getElementById('s-force').textContent   = c.zap.force.toFixed(2);
  document.getElementById('s-flow').textContent    = c.zap.flow.toFixed(2);
  document.getElementById('s-chaos').textContent   = c.zap.chaos.toFixed(2);
  document.getElementById('s-focus').textContent   = c.zap.focus.toFixed(2);
}

function setMode(label) {
  document.getElementById('mode').textContent = label;
}

document.addEventListener('keydown', e => {
  if (e.repeat) return;

  if (e.code === 'Space') {
    e.preventDefault();
    if (clock.isRunning) { clock.pause(); setMode('PAUSED'); }
    else                 { clock.play();  setMode('LIVE');   }
  }

  if (clock.isRunning) {
    const t = clock.cursor;
    if (e.code === 'KeyH') {
      tapes.beat.hit(t, 0);
      tapes.visual.flash(t);
    }
    if (e.code === 'KeyM') {
      tapes.beat.miss(t, 0);
      tapes.visual.distort(t, 0.4);
    }
  }

  // R = deterministic replay: create fresh bus, replay all tapes via time slicing, swap in
  if (e.code === 'KeyR') {
    const t = clock.cursor;
    clock.pause();
    setMode('VERIFYING…');

    const replayBus = new MultiTapeBus();
    const frameDt   = 1 / 60;
    let tCursor     = 0;
    let replayedWorld;

    while (tCursor < t) {
      const dt  = Math.min(frameDt, t - tCursor);
      replayedWorld = replayBus.stepReplay(dt, tCursor, tapes);
      tCursor += dt;
    }

    // Swap: live bus replaced by replayed bus; seq pointers advance to tape ends
    bus = replayBus;
    bus.catchUpSeqs(tapes);

    console.log('[QSR] replay complete', replayedWorld?.zap.core);
    setMode('REPLAY ✓');
    setTimeout(() => { clock.play(); setMode('LIVE'); }, 800);
  }

  // X = full reset
  if (e.code === 'KeyX') {
    clock.pause();
    clock.seek(0);
    lastBeatTick = -1;
    Object.values(tapes).forEach(tape => tape.reset());
    bus = new MultiTapeBus();
    setMode('PAUSED');
  }
});

requestAnimationFrame(loop);
