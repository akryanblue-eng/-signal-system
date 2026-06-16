import Foundation

// MARK: - DiffFrame

/// Unified comparison unit for two causal traces at a single frame index.
public struct DiffFrame: Identifiable {
    public let id: UInt64
    public let frame_index: UInt64

    // Left trace (live)
    public let left_event_hash: String
    public let left_projection_hash: String

    // Right trace (replay / alt run)
    public let right_event_hash: String
    public let right_projection_hash: String

    // Divergence signals
    public let event_diverged: Bool
    public let projection_diverged: Bool

    public init(
        frame_index: UInt64,
        left_event_hash: String,
        right_event_hash: String,
        left_projection_hash: String,
        right_projection_hash: String,
        event_diverged: Bool,
        projection_diverged: Bool
    ) {
        self.id = frame_index
        self.frame_index = frame_index
        self.left_event_hash = left_event_hash
        self.right_event_hash = right_event_hash
        self.left_projection_hash = left_projection_hash
        self.right_projection_hash = right_projection_hash
        self.event_diverged = event_diverged
        self.projection_diverged = projection_diverged
    }
}

// MARK: - Fork detection

public struct ForkPoint {
    public let frame_index: UInt64
    public let type: ForkType

    public init(frame_index: UInt64, type: ForkType) {
        self.frame_index = frame_index
        self.type = type
    }
}

public enum ForkType: String {
    /// First event hash mismatch — causal history differs.
    case eventFork
    /// Projection hash drifts but event hashes match — state evolution differs.
    case projectionFork
    /// Fork followed by widening delta across subsequent frames.
    case cascadingDrift
}
