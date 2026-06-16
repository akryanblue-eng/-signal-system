import Foundation

// All replay correctness reduces to canonical byte equality before hashing.
// Field order in every encode function is a versioned contract — never reorder.
public enum CanonicalEncoder {

    // MARK: - Vec3

    public static func encode(_ v: Vec3) -> Data {
        var d = Data()
        d.append(float(v.x))
        d.append(float(v.y))
        d.append(float(v.z))
        return d
    }

    // MARK: - Primitives

    public static func float(_ f: Float) -> Data {
        var bits = f.bitPattern.littleEndian
        return Data(bytes: &bits, count: 4)
    }

    public static func u64(_ v: UInt64) -> Data {
        var x = v.littleEndian
        return Data(bytes: &x, count: 8)
    }

    public static func uuid(_ id: UUID) -> Data {
        var u = id.uuid
        return Data(bytes: &u, count: 16)
    }

    // MARK: - Event envelope (generic — hash_this_event excluded; that's what we're computing)
    // Payload is encoded via JSONEncoder (v0). Field-level canonical encoding is the v1 upgrade.

    public static func encodeEvent<T: Codable & Equatable>(
        _ e: OracleEventEnvelope<T>
    ) -> Data {
        var d = Data()
        d.append(uuid(e.event_id))
        d.append(e.event_type.rawValue.data)
        d.append(u64(e.timestamp_device_ns))
        d.append(u64(e.timestamp_log_ns))
        d.append(e.source.rawValue.data)
        d.append(float(e.confidence))
        d.append(u64(e.frame_index))
        if let payloadData = try? JSONEncoder().encode(e.payload) {
            d.append(payloadData)
        }
        if let prev = e.hash_prev_event {
            d.append(prev.bytes)
        } else {
            d.append(Data(count: 32))
        }
        return d
    }

    // MARK: - ProjectionFrame

    public static func encode(_ p: ProjectionFrame) -> Data {
        var d = Data()
        d.append(u64(p.frame_index))
        if let o = p.gaze_origin_m {
            d.append(UInt8(1)); d.append(encode(o))
        } else {
            d.append(UInt8(0))
        }
        if let g = p.gaze_direction_unit {
            d.append(UInt8(1)); d.append(encode(g))
        } else {
            d.append(UInt8(0))
        }
        if let h = p.last_hit_point_m {
            d.append(UInt8(1)); d.append(encode(h))
        } else {
            d.append(UInt8(0))
        }
        d.append(u64(UInt64(p.trail.count)))
        for v in p.trail { d.append(encode(v)) }
        return d
    }
}
