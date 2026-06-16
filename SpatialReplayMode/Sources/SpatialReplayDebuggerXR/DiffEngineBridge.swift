import Foundation
import SpatialReplayDiff
import SpatialReplayDebugger

/// Converts two DebugSnapshot arrays into a real-time AsyncStream<DiffFrame>.
/// The stream yields one DiffFrame per tick at ~60 fps, then finishes.
/// For a live session, replace the sleep loop with actual sensor callbacks.
public enum DiffEngineBridge {

    public static func makeStream(
        left: [DebugSnapshot],
        right: [DebugSnapshot],
        tickInterval: Duration = .nanoseconds(16_666_667)   // ≈60 fps
    ) -> AsyncStream<DiffFrame> {
        let frames = DiffEngine.buildDiff(left: left, right: right)
        return AsyncStream { continuation in
            Task {
                for frame in frames {
                    continuation.yield(frame)
                    try? await Task.sleep(for: tickInterval)
                }
                continuation.finish()
            }
        }
    }

    /// Returns all frames at once (useful for replay mode — no streaming delay).
    public static func snapshot(
        left: [DebugSnapshot],
        right: [DebugSnapshot]
    ) -> [DiffFrame] {
        DiffEngine.buildDiff(left: left, right: right)
    }
}
