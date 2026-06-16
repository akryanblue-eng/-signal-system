import Foundation

// MARK: - ReplayResult

public struct ReplayResult: Equatable {
    public let projectionHashes: [Hash32]
    public let eventHashes: [Hash32]
    public let finalState: AppState

    public init(projectionHashes: [Hash32], eventHashes: [Hash32], finalState: AppState) {
        self.projectionHashes = projectionHashes
        self.eventHashes = eventHashes
        self.finalState = finalState
    }
}

// MARK: - Replay runner

/// Deterministic replay engine. Feeds an ordered event log through the reducer
/// and records projection + event hashes at every frame.
/// Throws ReducerError.hashChainBroken on the first chain violation.
public func runReplay(
    _ events: [OracleEventEnvelope<GazeSamplePayload>]
) throws -> ReplayResult {
    var state = AppState()
    var projectionHashes: [Hash32] = []
    var eventHashes: [Hash32] = []

    for event in events {
        state = try reduce(state, event)

        let projection = ProjectionFrame(
            frame_index: state.frame_index,
            gaze_origin_m: state.gaze_origin_m,
            gaze_direction_unit: state.gaze_direction_unit,
            last_hit_point_m: state.last_hit_point_m,
            trail: state.trail
        )
        projectionHashes.append(ProjectionHasher.projectionHash(projection))
        eventHashes.append(event.hash_this_event)
    }

    return ReplayResult(
        projectionHashes: projectionHashes,
        eventHashes: eventHashes,
        finalState: state
    )
}
