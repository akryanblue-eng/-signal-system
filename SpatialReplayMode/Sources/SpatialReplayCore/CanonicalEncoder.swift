import Foundation

// All replay correctness reduces to canonical byte equality before hashing.
// Order is contract — never reorder fields in these functions.
public enum CanonicalEncoder {

    // MARK: - Vec3

    public static func encode(_ v: Vec3) -> Data {
        var data = Data()
        data.append(floatBits(v.x))
        data.append(floatBits(v.y))
        data.append(floatBits(v.z))
        return data
    }

    public static func floatBits(_ f: Float) -> Data {
        var bitPattern = f.bitPattern.littleEndian
        return Data(bytes: &bitPattern, count: MemoryLayout<UInt32>.size)
    }

    // MARK: - GazeSamplePayload

    public static func encodeEventPayload(_ p: GazeSamplePayload) -> Data {
        var data = Data()
        data.append(encode(p.origin_m))
        data.append(encode(p.direction_unit))
        if let hit = p.hit_point_m {
            data.append(contentsOf: [1])
            data.append(encode(hit))
        } else {
            data.append(contentsOf: [0])
        }
        data.append(p.tracking_state.rawValue.data)
        data.append(p.calibration_context_hash.data)
        data.append(p.provenance.data)
        return data
    }

    // MARK: - OracleEventEnvelope (without hash_this_event — that's the field being computed)

    public static func encodeEventWithoutHash(
        _ e: OracleEventEnvelope<GazeSamplePayload>
    ) -> Data {
        var data = Data()
        data.append(uuidBytes(e.event_id))
        data.append(e.event_type.rawValue.data)
        data.append(u64(e.timestamp_device_ns))
        data.append(u64(e.timestamp_log_ns))
        data.append(e.source.rawValue.data)
        data.append(floatBits(e.confidence))
        data.append(u64(e.frame_index))
        data.append(encodeEventPayload(e.payload))
        if let prev = e.hash_prev_event {
            data.append(prev.bytes)
        } else {
            data.append(Data(count: 32))
        }
        return data
    }

    // MARK: - ProjectionFrame

    public static func encodeProjection(_ p: ProjectionFrame) -> Data {
        var data = Data()
        data.append(u64(p.frame_index))
        if let o = p.gaze_origin_m {
            data.append(contentsOf: [1]); data.append(encode(o))
        } else {
            data.append(contentsOf: [0])
        }
        if let d = p.gaze_direction_unit {
            data.append(contentsOf: [1]); data.append(encode(d))
        } else {
            data.append(contentsOf: [0])
        }
        if let h = p.last_hit_point_m {
            data.append(contentsOf: [1]); data.append(encode(h))
        } else {
            data.append(contentsOf: [0])
        }
        data.append(u64(UInt64(p.trail.count)))
        for v in p.trail {
            data.append(encode(v))
        }
        return data
    }

    // MARK: - Primitives

    public static func u64(_ v: UInt64) -> Data {
        var x = v.littleEndian
        return Data(bytes: &x, count: 8)
    }

    public static func uuidBytes(_ uuid: UUID) -> Data {
        var u = uuid.uuid
        return Data(bytes: &u, count: 16)
    }
}
