import type { PerformanceAction, Dispatch } from './PerformanceAction';
import type { Style } from './Style';
import { applyStyle } from './Style';

// ─── Types ─────────────────────────────────────────────────────────────────────

export interface ParsedIntent {
  raw:        string;
  intensity:  number; // [0, 1] — parsed from modifiers like "hard", "subtle"
  targets:    IntentTarget[];
}

export type IntentTarget =
  | 'energy'
  | 'groove'
  | 'chaos'
  | 'calm'
  | 'tension'
  | 'stability';

// ─── Parser ────────────────────────────────────────────────────────────────────

const INTENSITY_MAP: Array<[RegExp, number]> = [
  [/\b(max|extreme|hard|crazy|huge|massive)\b/i,    0.9],
  [/\b(heavy|big|strong|lot)\b/i,                   0.7],
  [/\b(subtle|light|gentle|soft|tiny|little)\b/i,   0.25],
  [/\b(slight|small|bit|touch)\b/i,                 0.35],
];

const TARGET_MAP: Array<[RegExp, IntentTarget]> = [
  [/\b(energy|hype|lift|pump|push)\b/i,             'energy'],
  [/\b(groove|lock|sync|tight|rhythm)\b/i,          'groove'],
  [/\b(chaos|glitch|break|shatter|fract)\b/i,       'chaos'],
  [/\b(calm|settle|smooth|quiet|dampen)\b/i,        'calm'],
  [/\b(tension|build|rise|pressure|wind)\b/i,       'tension'],
  [/\b(stable|stability|control|hold|anchor)\b/i,   'stability'],
];

export function parseIntent(input: string): ParsedIntent {
  let intensity = 0.5;
  for (const [re, val] of INTENSITY_MAP) {
    if (re.test(input)) { intensity = val; break; }
  }

  const targets: IntentTarget[] = [];
  for (const [re, target] of TARGET_MAP) {
    if (re.test(input)) targets.push(target);
  }

  return { raw: input, intensity, targets };
}

// ─── Compiler ──────────────────────────────────────────────────────────────────

const clamp = (v: number, lo = 0, hi = 1): number => Math.max(lo, Math.min(hi, v));

export function compileIntent(intent: ParsedIntent): PerformanceAction[] {
  const i       = intent.intensity;
  const actions: PerformanceAction[] = [];

  for (const target of intent.targets) {
    switch (target) {
      case 'energy':
        actions.push({ type: 'TENSION_BUILD',     amount: clamp(0.2 * i) });
        actions.push({ type: 'GROOVE_LOCK' });
        break;

      case 'groove':
        actions.push({ type: 'GROOVE_LOCK' });
        actions.push({ type: 'STABILITY_RESTORE', amount: clamp(0.1 * i) });
        break;

      case 'chaos':
        actions.push({ type: 'CHAOS_SPIKE',       amount: clamp(0.25 * i) });
        actions.push({ type: 'DRIFT_INJECTION',   amount: clamp(0.1 * i) });
        break;

      case 'calm':
        actions.push({ type: 'TENSION_RELEASE' });
        actions.push({ type: 'STABILITY_RESTORE', amount: clamp(0.15 * i) });
        break;

      case 'tension':
        actions.push({ type: 'TENSION_BUILD',     amount: clamp(0.15 * i) });
        break;

      case 'stability':
        actions.push({ type: 'STABILITY_RESTORE', amount: clamp(0.2 * i) });
        actions.push({ type: 'GROOVE_LOCK' });
        break;
    }
  }

  return deduplicate(actions);
}

/**
 * Keep the first occurrence of each action type.
 * Prevents double-firing when overlapping intent keywords match the same action.
 */
function deduplicate(actions: PerformanceAction[]): PerformanceAction[] {
  const seen = new Set<string>();
  return actions.filter(a => {
    if (seen.has(a.type)) return false;
    seen.add(a.type);
    return true;
  });
}

// ─── Entry point ───────────────────────────────────────────────────────────────

/**
 * Parse a natural-language intent string and dispatch the resulting action
 * packets into the runtime.
 *
 * Usage:
 *   handleIntent("push energy up and add chaos", runtime.dispatch);
 */
export function handleIntent(input: string, dispatch: Dispatch): ParsedIntent {
  const intent  = parseIntent(input);
  const actions = compileIntent(intent);
  for (const action of actions) dispatch(action);
  return intent;
}

/**
 * Same as handleIntent but routes compiled actions through a Style filter
 * before dispatch. Same phrase → different emotional weight.
 *
 * Usage:
 *   handleIntentWithStyle("push energy", runtime.dispatch, STYLES.chaoticJazz);
 */
export function handleIntentWithStyle(
  input:    string,
  dispatch: Dispatch,
  style:    Style,
): ParsedIntent {
  const intent  = parseIntent(input);
  const raw     = compileIntent(intent);
  const styled  = applyStyle(raw, style);
  for (const action of styled) dispatch(action);
  return intent;
}
