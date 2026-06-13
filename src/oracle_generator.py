"""
DSVM-0 CI Run Matrix Generator

Usage:
    python -m src.oracle_generator            # regenerate fixtures + Swift files
    python -m src.oracle_generator --verify   # verify frozen fixtures match current impl

Outputs (written to spatial_vm_fixtures/):
    oracle_runs.json     — frozen expected TravelerState snapshots, commits, event streams
    DSVM0Oracle.swift    — Swift oracle for drop-in Xcode integration
    ReplayHarnessCI.swift  — CI gate harness (extend for your QSEvent types)
    ReplayHarnessDiff.swift — Failure diff visualizer

The JSON fixtures are the canonical source of truth for CI.  The Swift files are
generated from the same fixture data so they stay in sync automatically.

Exit codes (--verify mode):
    0  — all fixtures match current implementation
    1  — one or more runs diverged from frozen oracle
    2  — fixture file missing or unreadable
"""
import argparse
import json
import sys
import textwrap
from pathlib import Path

from .spatial_vm_conformance import (
    run_a, run_b, run_c, run_d,
    STREAM_RUN_A, STREAM_RUN_B, STREAM_RUN_C, STREAM_RUN_D,
    RunResult,
)
from .traveler_state import TravelerState

FIXTURES_DIR = Path(__file__).parent.parent / "spatial_vm_fixtures"
ORACLE_JSON = FIXTURES_DIR / "oracle_runs.json"
DSVM0_ORACLE_SWIFT = FIXTURES_DIR / "DSVM0Oracle.swift"
HARNESS_CI_SWIFT = FIXTURES_DIR / "ReplayHarnessCI.swift"
HARNESS_DIFF_SWIFT = FIXTURES_DIR / "ReplayHarnessDiff.swift"
APP_FLOW_SWIFT = FIXTURES_DIR / "AppFlow.swift"
APP_NAVIGATOR_SWIFT = FIXTURES_DIR / "AppNavigator.swift"
QUANTUM_STAR_APP_SWIFT = FIXTURES_DIR / "QuantumStarApp.swift"


# ---------------------------------------------------------------------------
# JSON serialization helpers
# ---------------------------------------------------------------------------

def _state_to_dict(state: TravelerState) -> dict:
    return {
        "visited_nodes": list(state.visited_nodes),
        "discovered_artifacts": list(state.discovered_artifacts),
        "revealed_lore": list(state.revealed_lore),
        "ascension": state.ascension,
        "convergence_score": state.convergence_score,
    }


def _run_to_dict(result: RunResult) -> dict:
    return {
        "id": result.run_id,
        "proves": result.proves,
        "events": result.events,
        "expected_state": _state_to_dict(result.final_state),
        "state_commit_hex": result.state_commit.hex(),
        "run_commit_hex": result.commit.hex(),
        "ct0_verdict": result.ct0_verdict,
        "advisory_projection_hashes": result.projection_hashes,
    }


def generate_oracle_json(results: dict[str, RunResult]) -> dict:
    return {
        "schema": "dsvm0-oracle-v1",
        "oracle_sentinel_run_id": "DSVM0-STATE-ORACLE",
        "runs": {key: _run_to_dict(r) for key, r in results.items()},
    }


# ---------------------------------------------------------------------------
# Swift code generators
# ---------------------------------------------------------------------------

def _swift_string_array(items: list[str], indent: int = 12) -> str:
    pad = " " * indent
    if not items:
        return "[]"
    inner = (",\n" + pad).join(f'"{v}"' for v in items)
    return f'[\n{pad}{inner}\n{" " * (indent - 4)}]'


def _swift_events(events: list[dict], indent: int = 12) -> str:
    pad = " " * indent
    lines = []
    for ev in events:
        t = ev["type"]
        if t == "enter_node":
            lines.append(f'.enterNode("{ev["node_id"]}")')
        elif t == "discover_artifact":
            lines.append(f'.discoverArtifact("{ev["artifact_id"]}")')
        elif t == "reveal_lore":
            lines.append(f'.revealLore("{ev["lore_id"]}")')
        elif t == "choose_ascension":
            lines.append(".chooseAscension")
        elif t == "choose_creation":
            lines.append(".chooseCreation")
        elif t == "node_completed":
            lines.append(f'.nodeCompleted("{ev["node_id"]}")')
        elif t == "portal_unlocked":
            lines.append(f'.portalUnlocked("{ev["portal_id"]}")')
    inner = (",\n" + pad).join(lines)
    return f'[\n{pad}{inner}\n{" " * (indent - 4)}]'


def generate_dsvm0_oracle_swift(results: dict[str, RunResult]) -> str:
    runs_code = []
    for label, r in results.items():
        s = r.final_state
        events_swift = _swift_events(r.events)
        nodes_swift = _swift_string_array(list(s.visited_nodes))
        arts_swift = _swift_string_array(list(s.discovered_artifacts))
        lore_swift = _swift_string_array(list(s.revealed_lore))
        ascension_val = "true" if s.ascension else "false"
        runs_code.append(f'''\
    // MARK: Run {label} — {r.proves}
    // State oracle commit: {r.state_commit.hex()[:24]}…
    static let run{label} = ReplayRun(
        id: "{r.run_id}",
        events: {events_swift},
        expected: TravelerState(
            visitedNodes: {nodes_swift},
            discoveredArtifacts: {arts_swift},
            revealedLore: {lore_swift},
            ascension: {ascension_val}
        )
    )''')

    run_refs = ", ".join(f"run{k}" for k in results)

    return textwrap.dedent(f"""\
    // GENERATED by src/oracle_generator.py — do not edit manually.
    // To regenerate: python -m src.oracle_generator
    //
    // DSVM-0 Oracle — CI Run Matrix
    //
    // State oracle commits (use for cross-run equality assertions):
    {chr(10).join(f"//   Run {k}: {r.state_commit.hex()}" for k, r in results.items())}
    //
    // Schema: dsvm0-oracle-v1

    import Foundation

    struct DSVM0Oracle {{
    {chr(10).join(runs_code)}

        // MARK: - Export for CI harness
        static let runs: [ReplayRun] = [{run_refs}]
    }}
    """)


def generate_harness_ci_swift() -> str:
    return textwrap.dedent("""\
    // GENERATED by src/oracle_generator.py — do not edit manually.
    //
    // DSVM-0 CI Gate Harness
    // Drop-in for Xcode; wire to your QSEvent enum and TravelerState reducer.

    import Foundation

    // MARK: - CI Gate Failure

    struct CIGateFailure: Error, CustomStringConvertible {
        let message: String
        let failingRuns: [ReplayRun]

        var description: String {
            var out = "\\n❌ DSVM-0 VIOLATION: TravelerState divergence detected\\n"
            out += message + "\\n"
            for run in failingRuns {
                out += "\\n── Run: \\(run.id) ──\\n"
                out += "  Expected: \\(run.expected.debugDescription)\\n"
                out += "  Actual:   \\(run.actual?.debugDescription ?? "nil")\\n"
            }
            return out
        }
    }

    // MARK: - CI Harness

    struct ReplayHarnessCI {
        static func runCIGate() async throws {
            let runs = DSVM0Oracle.runs
            let harness = ReplayHarness()
            let results = harness.verifyDeterminism(runs: runs)

            let failing = results.filter { !$0.stateMatches }
            guard failing.isEmpty else {
                let failure = CIGateFailure(
                    message: "DSVM-0 oracle divergence detected",
                    failingRuns: failing
                )
                print(ReplayHarnessDiff.visualize(failure))
                throw failure
            }

            print("✅ DSVM-0 CI gate passed: \\(results.count) runs, deterministic equality verified")
        }
    }

    // MARK: - ReplayHarness contract (implement against your app's reducer)

    // final class ReplayHarness {
    //     func verifyDeterminism(runs: [ReplayRun]) -> [ReplayRun] {
    //         runs.map { run in
    //             let final = execute(run.events)
    //             return ReplayRun(id: run.id, events: run.events, expected: run.expected, actual: final)
    //         }
    //     }
    //     private func execute(_ events: [QSEvent]) -> TravelerState {
    //         var s = TravelerState()
    //         for event in events {
    //             let reactions = evaluate(event: event)
    //             s = applyReducer(s, reactions)
    //         }
    //         return s
    //     }
    // }

    // MARK: - XCTest wrapper

    // import XCTest
    // @MainActor
    // final class ReplayHarnessTests: XCTestCase {
    //     func testDSVM0_CIGate() async throws {
    //         try await ReplayHarnessCI.runCIGate()
    //     }
    // }
    """)


def generate_quantum_star_app_swift() -> str:
    return textwrap.dedent("""\
    // GENERATED by src/oracle_generator.py — do not edit manually.
    //
    // QuantumStarApp — DSVM-0 entry point
    // Drop-in for Xcode alongside AppFlow.swift and AppNavigator.swift.

    import SwiftUI

    @main
    struct QuantumStarApp: App {
        @StateObject private var appFlow = AppFlow()

        var body: some Scene {
            WindowGroup {
                AppNavigator()
                    .environmentObject(appFlow)
            }
        }
    }
    """)


def generate_app_flow_swift() -> str:
    return textwrap.dedent("""\
    // GENERATED by src/oracle_generator.py — do not edit manually.
    //
    // AppFlow — DSVM-0 interface #2 (the only write authority for TravelerState)
    //
    // Routing is intentionally semantics-free.
    // All semantic changes MUST happen via send(_:) → reducer.

    import SwiftUI

    @MainActor
    final class AppFlow: ObservableObject {
        @Published private(set) var travelerState: TravelerState
        @Published var currentNode: CurrentNode

        init(
            initialState: TravelerState = TravelerState(),
            initialNode: CurrentNode = .neonInNirvana
        ) {
            self.travelerState = initialState
            self.currentNode = initialNode
        }

        // DSVM-0 interface #1
        func initialState() -> TravelerState { TravelerState() }

        // DSVM-0 interface #2 — single write authority for TravelerState
        func send(_ event: QSEvent) {
            travelerState = applyReducer(travelerState, event)
        }

        // Navigation-only: switches currentNode without touching TravelerState
        func navigateTo(_ node: CurrentNode) {
            currentNode = node
        }

        // DSVM-0 interface #3 (optional — for projection oracle in CI)
        func projectHash(node: String, state: TravelerState) -> String {
            // Replace with your projectWorld() implementations.
            // Must be a pure function of state — no Entity reads.
            return ""
        }
    }
    """)


def generate_app_navigator_swift() -> str:
    return textwrap.dedent("""\
    // GENERATED by src/oracle_generator.py — do not edit manually.
    //
    // AppNavigator — pure projection selector
    //
    // Navigation is a pure selection of projection, not a causality step.
    // The only causality step remains: send(event) → reducer → new TravelerState.

    import SwiftUI

    struct AppNavigator: View {
        @EnvironmentObject private var appFlow: AppFlow

        var body: some View {
            switch appFlow.currentNode {
            case .neonInNirvana:
                NeonInNirvanaView(
                    travelerState: appFlow.travelerState,
                    send: appFlow.send,
                    navigateTo: appFlow.navigateTo
                )
            case .godlyDNA:
                GodlyDNAView(
                    travelerState: appFlow.travelerState,
                    send: appFlow.send,
                    navigateTo: appFlow.navigateTo
                )
            case .skyHigh:
                SkyHighView(
                    travelerState: appFlow.travelerState,
                    send: appFlow.send,
                    navigateTo: appFlow.navigateTo
                )
            }
        }
    }

    enum CurrentNode: String, Equatable {
        case neonInNirvana = "neon-in-nirvana"
        case godlyDNA      = "godly-dna"
        case skyHigh       = "sky-high"
    }

    // MARK: - Minimal view signatures
    // Views receive TravelerState as a value and can only call send(event).
    // They must not mutate TravelerState directly.

    struct NeonInNirvanaView: View {
        let travelerState: TravelerState
        let send: (QSEvent) -> Void
        let navigateTo: (CurrentNode) -> Void

        var body: some View {
            // Wire your existing NeonInNirvanaView content here.
            // Example: Button("Enter Godly DNA") {
            //     send(.onNodeCompleted(nodeId: "neon-in-nirvana"))
            //     navigateTo(.godlyDNA)
            // }
            Text("Node A: Neon In Nirvana")
        }
    }

    struct GodlyDNAView: View {
        let travelerState: TravelerState
        let send: (QSEvent) -> Void
        let navigateTo: (CurrentNode) -> Void

        var body: some View {
            // Wire your existing GodlyDNAView content here.
            // Branch choice example:
            // Button("Ascend") { send(.onChoiceAscension); navigateTo(.skyHigh) }
            // Button("Create") { send(.onChoiceCreation); navigateTo(.skyHigh) }
            Text("Node B: Godly DNA")
        }
    }

    struct SkyHighView: View {
        let travelerState: TravelerState
        let send: (QSEvent) -> Void
        let navigateTo: (CurrentNode) -> Void

        var body: some View {
            // Wire your existing SkyHighView content here.
            // Temporal drift: projectWorld() reads travelerState, never scene state.
            Text("Node C: Sky High")
        }
    }
    """)


def generate_harness_diff_swift() -> str:
    return textwrap.dedent("""\
    // GENERATED by src/oracle_generator.py — do not edit manually.
    //
    // DSVM-0 Replay Harness Diff Visualizer
    // Emits state diff trees, event divergence traces, and first-point-of-failure
    // localization when CI fails. Wire to your reducer for step-by-step replay.

    import Foundation

    struct ReplayHarnessDiff {

        // MARK: - Top-level visualizer (called by ReplayHarnessCI on failure)

        static func visualize(_ failure: CIGateFailure) -> String {
            var out = "\\n❌ DSVM-0 VIOLATION: TravelerState divergence detected\\n"
            out += "\\n📊 State Diff Trees:\\n"
            for run in failure.failingRuns {
                out += "\\n── Run: \\(run.id) ──\\n"
                if let actual = run.actual {
                    out += stateDiffTree(expected: run.expected, actual: actual)
                }
                out += "\\n🔍 Event Divergence Trace:\\n"
                out += eventTrace(run: run)
                out += "\\n🎯 First Point of Failure:\\n"
                out += firstFailure(run: run)
            }
            return out
        }

        // MARK: - State diff tree

        private static func stateDiffTree(expected: TravelerState, actual: TravelerState) -> String {
            var diff = ""
            diff += field("visitedNodes",        expected.visitedNodes.count,        actual.visitedNodes.count)
            diff += field("discoveredArtifacts",  expected.discoveredArtifacts.count, actual.discoveredArtifacts.count)
            diff += field("revealedLore",         expected.revealedLore.count,        actual.revealedLore.count)
            diff += field("ascension",            expected.ascension,                 actual.ascension)
            return diff
        }

        private static func field<T: Equatable>(_ name: String, _ exp: T, _ act: T) -> String {
            let mark = exp == act ? "  ✅" : "  ❌"
            return "\\(mark) \\(name): expected=\\(exp), actual=\\(act)\\n"
        }

        // MARK: - Event divergence trace
        // Replays events one-by-one to find where actual state first diverges from expected.

        private static func eventTrace(run: ReplayRun) -> String {
            // Wire `stepReplay` to your reducer for live tracing.
            // Without it, this reports final-state divergence only.
            guard let actual = run.actual else {
                return "  (no actual state — reducer not wired)\\n"
            }
            if actual == run.expected {
                return "  No divergence (state matches)\\n"
            }
            return "  Final state diverges from expected (wire stepReplay for per-event trace)\\n"
        }

        // MARK: - First point of failure
        // Requires stepReplay(state:event:) to be implemented.

        private static func firstFailure(run: ReplayRun) -> String {
            guard let actual = run.actual else {
                return "  (no actual state — reducer not wired)\\n"
            }
            if actual == run.expected {
                return "  No failure (state matches)\\n"
            }
            return "  Final ascension=\\(actual.ascension), visitedNodes=\\(actual.visitedNodes.count)\\n"
        }

        // MARK: - Step replay hook (implement against your app's reducer)
        //
        // static func stepReplay(_ state: TravelerState, _ event: QSEvent) -> TravelerState {
        //     let reactions = evaluate(event: event)
        //     return applyReducer(state, reactions)
        // }
    }
    """)


# ---------------------------------------------------------------------------
# Verify mode: load frozen JSON and compare against current impl
# ---------------------------------------------------------------------------

def _format_divergence(label: str, result: RunResult, frozen: dict) -> str:
    lines = [f"\n── Run {label}: {result.run_id} ──"]
    frozen_commit = frozen["state_commit_hex"]
    actual_commit = result.state_commit.hex()
    if frozen_commit != actual_commit:
        lines.append(f"  state_commit DIVERGED")
        lines.append(f"    frozen:  {frozen_commit[:32]}…")
        lines.append(f"    actual:  {actual_commit[:32]}…")

    frozen_state = frozen["expected_state"]
    actual_state = _state_to_dict(result.final_state)
    for field in ("visited_nodes", "discovered_artifacts", "revealed_lore", "ascension", "convergence_score"):
        fv, av = frozen_state.get(field), actual_state.get(field)
        mark = "✅" if fv == av else "❌"
        if fv != av:
            lines.append(f"  {mark} {field}: frozen={fv!r}, actual={av!r}")
    return "\n".join(lines)


def verify_fixtures(results: dict[str, RunResult]) -> int:
    if not ORACLE_JSON.exists():
        print(f"ERROR: oracle fixture not found: {ORACLE_JSON}", file=sys.stderr)
        print("Run `python -m src.oracle_generator` to generate it.", file=sys.stderr)
        return 2

    try:
        frozen = json.loads(ORACLE_JSON.read_text())
    except Exception as exc:
        print(f"ERROR: cannot read oracle fixture: {exc}", file=sys.stderr)
        return 2

    failures = []
    for label, result in results.items():
        frozen_run = frozen["runs"].get(label)
        if frozen_run is None:
            failures.append(f"Run {label} missing from frozen fixtures.")
            continue
        if result.state_commit.hex() != frozen_run["state_commit_hex"]:
            failures.append(_format_divergence(label, result, frozen_run))

    if failures:
        print("❌ DSVM-0 CI GATE FAIL: oracle divergence detected\n")
        for f in failures:
            print(f)
        return 1

    print("✅ DSVM-0 CI gate passed: all runs match frozen oracle")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="DSVM-0 CI Run Matrix Generator")
    parser.add_argument("--verify", action="store_true",
                        help="Verify frozen fixtures; exit 1 on divergence, 2 on missing")
    args = parser.parse_args()

    results = {"A": run_a(), "B": run_b(), "C": run_c(), "D": run_d()}

    if args.verify:
        sys.exit(verify_fixtures(results))

    # Generate mode: write all fixture files
    FIXTURES_DIR.mkdir(exist_ok=True)

    oracle = generate_oracle_json(results)
    ORACLE_JSON.write_text(json.dumps(oracle, indent=2))
    print(f"✅ Written: {ORACLE_JSON}")

    DSVM0_ORACLE_SWIFT.write_text(generate_dsvm0_oracle_swift(results))
    print(f"✅ Written: {DSVM0_ORACLE_SWIFT}")

    HARNESS_CI_SWIFT.write_text(generate_harness_ci_swift())
    print(f"✅ Written: {HARNESS_CI_SWIFT}")

    HARNESS_DIFF_SWIFT.write_text(generate_harness_diff_swift())
    print(f"✅ Written: {HARNESS_DIFF_SWIFT}")

    QUANTUM_STAR_APP_SWIFT.write_text(generate_quantum_star_app_swift())
    print(f"✅ Written: {QUANTUM_STAR_APP_SWIFT}")

    APP_FLOW_SWIFT.write_text(generate_app_flow_swift())
    print(f"✅ Written: {APP_FLOW_SWIFT}")

    APP_NAVIGATOR_SWIFT.write_text(generate_app_navigator_swift())
    print(f"✅ Written: {APP_NAVIGATOR_SWIFT}")

    print("\nState oracle commits:")
    for label, r in results.items():
        print(f"  Run {label}: {r.state_commit.hex()}")


if __name__ == "__main__":
    main()
