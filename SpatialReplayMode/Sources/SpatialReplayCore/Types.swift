import Foundation

// MARK: - Primitives

public struct Vec3: Equatable {
    public let x: Float
    public let y: Float
    public let z: Float

    public init(x: Float, y: Float, z: Float) {
        self.x = x
        self.y = y
        self.z = z
    }
}

public struct Hash32: Equatable {
    public let bytes: Data

    public init(bytes: Data) {
        precondition(bytes.count == 32, "Hash32 requires exactly 32 bytes")
        self.bytes = bytes
    }
}

// MARK: - Enums

public enum TrackingState: String {
    case tracked
    case limited
    case notAvailable
}

public enum EventType: String {
    case gazeSample
}

public enum EventSource: String {
    case device
    case replay
}

// MARK: - Payloads

public struct GazeSamplePayload {
    public let origin_m: Vec3
    public let direction_unit: Vec3
    public let hit_point_m: Vec3?
    public let tracking_state: TrackingState
    public let calibration_context_hash: String
    public let provenance: String

    public init(
        origin_m: Vec3,
        direction_unit: Vec3,
        hit_point_m: Vec3?,
        tracking_state: TrackingState,
        calibration_context_hash: String,
        provenance: String
    ) {
        self.origin_m = origin_m
        self.direction_unit = direction_unit
        self.hit_point_m = hit_point_m
        self.tracking_state = tracking_state
        self.calibration_context_hash = calibration_context_hash
        self.provenance = provenance
    }
}

// MARK: - Event envelope

public struct OracleEventEnvelope<Payload> {
    public let event_id: UUID
    public let event_type: EventType
    public let timestamp_device_ns: UInt64
    public let timestamp_log_ns: UInt64
    public let source: EventSource
    public let confidence: Float
    public let frame_index: UInt64
    public let payload: Payload
    public let hash_prev_event: Hash32?
    public var hash_this_event: Hash32?

    public init(
        event_id: UUID,
        event_type: EventType,
        timestamp_device_ns: UInt64,
        timestamp_log_ns: UInt64,
        source: EventSource,
        confidence: Float,
        frame_index: UInt64,
        payload: Payload,
        hash_prev_event: Hash32?,
        hash_this_event: Hash32?
    ) {
        self.event_id = event_id
        self.event_type = event_type
        self.timestamp_device_ns = timestamp_device_ns
        self.timestamp_log_ns = timestamp_log_ns
        self.source = source
        self.confidence = confidence
        self.frame_index = frame_index
        self.payload = payload
        self.hash_prev_event = hash_prev_event
        self.hash_this_event = hash_this_event
    }
}

// MARK: - Projection frame

public struct ProjectionFrame {
    public let frame_index: UInt64
    public let gaze_origin_m: Vec3?
    public let gaze_direction_unit: Vec3?
    public let last_hit_point_m: Vec3?
    public var trail: [Vec3]

    public init(
        frame_index: UInt64,
        gaze_origin_m: Vec3?,
        gaze_direction_unit: Vec3?,
        last_hit_point_m: Vec3?,
        trail: [Vec3]
    ) {
        self.frame_index = frame_index
        self.gaze_origin_m = gaze_origin_m
        self.gaze_direction_unit = gaze_direction_unit
        self.last_hit_point_m = last_hit_point_m
        self.trail = trail
    }
}

// MARK: - String → Data helper (UTF-8, for canonical encoding only)

extension String {
    var data: Data { Data(utf8) }
}
