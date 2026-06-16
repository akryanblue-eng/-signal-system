import Foundation
import SpatialReplayDebugger

// MARK: - Safe subscript

extension Array {
    subscript(safe index: Int) -> Element? {
        guard index >= 0, index < count else { return nil }
        return self[index]
    }
}

// MARK: - Diff Engine

/// Pure function — no IO, no time, no randomness.
/// All inputs are DebugSnapshot arrays; all outputs are DiffFrame arrays.
public enum DiffEngine {

    /// Align two traces by frame_index and produce a divergence record per frame.
    public static func buildDiff(
        left: [DebugSnapshot],
        right: [DebugSnapshot]
    ) -> [DiffFrame] {
        let count = max(left.count, right.count)
        return (0..<count).map { i in
            let l = left[safe: i]
            let r = right[safe: i]
            return DiffFrame(
                frame_index: UInt64(i),
                left_event_hash: l?.event_hash ?? "nil",
                right_event_hash: r?.event_hash ?? "nil",
                left_projection_hash: l?.projection_hash ?? "nil",
                right_projection_hash: r?.projection_hash ?? "nil",
                event_diverged: l?.event_hash != r?.event_hash,
                projection_diverged: l?.projection_hash != r?.projection_hash
            )
        }
    }

    /// Returns the earliest frame where divergence begins, with propagation classification.
    public static func detectForkPoint(in frames: [DiffFrame]) -> ForkPoint? {
        guard let firstEventFork = frames.first(where: { $0.event_diverged }) else {
            // No event divergence — check for isolated projection drift.
            if let first = frames.first(where: { $0.projection_diverged }) {
                return ForkPoint(frame_index: first.frame_index, type: .projectionFork)
            }
            return nil
        }

        // Classify: does projection drift propagate beyond the event fork?
        let trailingFrames = frames.filter { $0.frame_index > firstEventFork.frame_index }
        let cascades = trailingFrames.filter { $0.projection_diverged }.count
        let forkType: ForkType = cascades > 1 ? .cascadingDrift : .eventFork
        return ForkPoint(frame_index: firstEventFork.frame_index, type: forkType)
    }
}
