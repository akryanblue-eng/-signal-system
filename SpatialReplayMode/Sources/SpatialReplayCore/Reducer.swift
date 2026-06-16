import Foundation

// MARK: - AppState

public struct AppState: Equatable {
    public var frame_index: UInt64 = 0
    public var gaze_origin_m: Vec3? = nil
    public var gaze_direction_unit: Vec3? = nil
    public var last_hit_point_m: Vec3? = nil
    public var trail: [Vec3] = []
    public var last_event_hash: Hash32? = nil

    public init() {}
}

// MARK: - ReducerError

public enum ReducerError: Error, Equatable {
    case hashChainBroken
}

// MARK: - reduce

/// Pure function — given a state and a verified event, returns the next state.
/// Throws ReducerError.hashChainBroken if the event's hash_prev_event does not
/// match the state's last_event_hash, preventing silent chain corruption.
public func reduce(
    _ state: AppState,
    _ event: OracleEventEnvelope<GazeSamplePayload>
) throws -> AppState {
    guard state.last_event_hash == event.hash_prev_event else {
        throw ReducerError.hashChainBroken
    }

    var next = state
    next.frame_index = event.frame_index
    next.last_event_hash = event.hash_this_event

    switch event.event_type {
    case .oracleGazeSample:
        next.gaze_origin_m = event.payload.origin_m
        next.gaze_direction_unit = event.payload.direction_unit
        next.last_hit_point_m = event.payload.hit_point_m
        if let hit = event.payload.hit_point_m {
            next.trail.append(hit)
        }
    case .oracleGazeFixation:
        break
    case .oracleGazeLost:
        next.last_hit_point_m = nil
    }

    return next
}
