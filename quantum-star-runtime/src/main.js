import { TimelineClock }   from './clock/TimelineClock.js';
import { BeatTape }        from './tapes/BeatTape.js';
import { PhysicsTape }     from './tapes/PhysicsTape.js';
import { VisualTape }      from './tapes/VisualTape.js';
import { MetaTape }        from './tapes/MetaTape.js';
import { MultiTapeBus }    from './core/MultiTapeBus.js';
import { TimelineGraph }   from './timeline/TimelineGraph.js';
import { BranchExecutor }  from './timeline/BranchExecutor.js';
import { BeatManiaSkin }   from './systems/SkinRuntime.js';
import { render }          from './render/render.js';

// ─── Runtime instances ───────────────────────────────────────────────────────
const clock = new TimelineClock();
const tapes = {
  beat:    new BeatTape(),
  physics: new PhysicsTape(),
  visual:  new VisualTape(),
  meta:    new MetaTape(),
};
let bus      = new MultiTapeBus();
const graph  = new TimelineGraph();
const executor = new BranchExecutor(graph);

const canvas = document.getElementById('stage');
const ctx    = canvas.getContext('2d');

// ─── Beat scheduling (no setTimeout — derived from clock cursor) ─────────────
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

// ─── Timeline / Checkpoint ───────────────────────────────────────────────────
const CHECKPOINT_INTERVAL = 5; // seconds between automatic checkpoints

// Bootstrap: root node + main branch at t=0
const rootWorld   = bus.step(0, 0, tapes);
const rootNode    = graph.createNode(0, rootWorld, tapes);
let mainBranch    = graph.createBranch(rootNode.id, 'main');
let lastCheckpointT = 0;
let lastWorld     = rootWorld;

function maybeCheckpoint(world, t) {
  if (!clock.isRunning) return;
  if (t - lastCheckpointT < CHECKPOINT_INTERVAL) return;
  const node = graph.createNode(t, world, tapes);
  graph.advanceBranch(mainBranch, node.id, 'live');
  lastCheckpointT = t;
  updateGraphHUD();
}

// ─── Main loop ───────────────────────────────────────────────────────────────
function loop() {
  requestAnimationFrame(loop);

  const dt = clock.tick();
  const t  = clock.cursor;

  if (clock.isRunning) emitScheduledBeats(t);

  // MultiTapeBus: ZapRuntime sees BeatTape only
  const world = bus.step(dt, t, tapes);
  lastWorld   = world;

  maybeCheckpoint(world, t);

  const vis = BeatManiaSkin.project(world);
  render(ctx, vis);
  updateHUD(world, t);
}

// ─── HUD ─────────────────────────────────────────────────────────────────────
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

function updateGraphHUD() {
  document.getElementById('s-nodes').textContent    = graph.nodeCount;
  document.getElementById('s-branches').textContent = graph.branchCount;
}

function setMode(label) {
  document.getElementById('mode').textContent = label;
}

// ─── Controls ────────────────────────────────────────────────────────────────
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

  // G = manual checkpoint at current time
  if (e.code === 'KeyG') {
    const t    = clock.cursor;
    const node = graph.createNode(t, lastWorld, tapes);
    graph.advanceBranch(mainBranch, node.id, 'live');
    lastCheckpointT = t;
    updateGraphHUD();
    setMode(`CHECKPOINT @ ${t.toFixed(2)}s`);
    setTimeout(() => setMode(clock.isRunning ? 'LIVE' : 'PAUSED'), 1200);
  }

  // R = fork branch from nearest checkpoint, replay to current t, compare
  if (e.code === 'KeyR') {
    const t           = clock.cursor;
    const nearestNode = graph.getNearestNodeBefore(t);
    if (!nearestNode) { setMode('NO CHECKPOINT YET — press G'); return; }

    clock.pause();
    setMode('VERIFYING BRANCH…');

    // Fork a read-only verification branch from the checkpoint
    const forkId    = graph.createBranch(nearestNode.id, `verify@${t.toFixed(1)}`);
    const forkWorld = executor.executeBranch(forkId, tapes, t);
    updateGraphHUD();

    const liveCore = lastWorld.zap.core;
    const forkCore = forkWorld?.zap.core;
    const match    = forkCore &&
                     liveCore.score    === forkCore.score &&
                     liveCore.hitCount === forkCore.hitCount;

    console.log('[QSR] Branch verification (from checkpoint t=' + nearestNode.t.toFixed(2) + ')', {
      match,
      live:  { score: liveCore.score,    hits: liveCore.hitCount },
      fork:  { score: forkCore?.score,   hits: forkCore?.hitCount },
      checksum: nearestNode.checksum,
    });

    setMode(match ? `BRANCH ✓ (from ${nearestNode.t.toFixed(1)}s)` : 'BRANCH ✗ DIVERGED');
    setTimeout(() => { clock.play(); setMode('LIVE'); }, 1200);
  }

  // F = fork a named "what-if" branch from nearest checkpoint (doesn't swap live bus)
  if (e.code === 'KeyF') {
    const nearestNode = graph.getNearestNodeBefore(clock.cursor);
    if (!nearestNode) { setMode('NO CHECKPOINT — press G first'); return; }
    const forkId = graph.createBranch(nearestNode.id, `what-if-${Date.now()}`);
    updateGraphHUD();
    console.log('[QSR] What-if branch created:', forkId, 'from node', nearestNode.id,
                'at t=', nearestNode.t.toFixed(2), '| graph:', graph.status());
    setMode(`FORK created (${graph.branchCount} branches)`);
    setTimeout(() => setMode(clock.isRunning ? 'LIVE' : 'PAUSED'), 1500);
  }

  // X = full reset
  if (e.code === 'KeyX') {
    clock.pause();
    clock.seek(0);
    lastBeatTick    = -1;
    lastCheckpointT = 0;
    Object.values(tapes).forEach(tape => tape.reset());
    bus = new MultiTapeBus();
    setMode('PAUSED');
    updateGraphHUD();
  }
});

updateGraphHUD();
requestAnimationFrame(loop);
