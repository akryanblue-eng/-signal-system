import XCTest
@testable import SpatialReplayCore

final class CanonicalHashingTests: XCTestCase {

    // Identical Vec3 values must produce identical bytes every time.
    func testVec3Determinism() {
        let a = Vec3(x: 1.0, y: 2.0, z: 3.0)
        let b = Vec3(x: 1.0, y: 2.0, z: 3.0)
        XCTAssertEqual(CanonicalEncoder.encode(a), CanonicalEncoder.encode(b))
    }

    // Same seed → same event → same hash.
    func testEventHashStability() {
        let e1 = makeSyntheticEvent(seed: 1)
        let e2 = makeSyntheticEvent(seed: 1)
        XCTAssertEqual(ProjectionHasher.eventHash(e1), ProjectionHasher.eventHash(e2))
    }

    // Appending a point to the trail must change the projection hash.
    func testProjectionDriftDetection() {
        let p1 = makeProjection(seed: 1)
        var p2 = p1
        p2.trail.append(Vec3(x: 9, y: 9, z: 9))
        XCTAssertNotEqual(
            ProjectionHasher.projectionHash(p1),
            ProjectionHasher.projectionHash(p2)
        )
    }

    // MARK: - Helpers

    private func makeSyntheticEvent(seed: Int) -> OracleEventEnvelope<GazeSamplePayload> {
        let f = Float(seed)
        let payload = GazeSamplePayload(
            origin_m: Vec3(x: f, y: f, z: f),
            direction_unit: Vec3(x: 0, y: 0, z: 1),
            hit_point_m: Vec3(x: f * 2, y: f * 2, z: f * 2),
            tracking_state: .tracked,
            calibration_context_hash: "ctx-\(seed)",
            provenance: "test-\(seed)"
        )
        return OracleEventEnvelope(
            event_id: uuidForSeed(seed),
            event_type: .gazeSample,
            timestamp_device_ns: UInt64(seed) * 1_000,
            timestamp_log_ns: UInt64(seed) * 1_001,
            source: .device,
            confidence: 1.0,
            frame_index: UInt64(seed),
            payload: payload,
            hash_prev_event: nil,
            hash_this_event: nil
        )
    }

    private func makeProjection(seed: Int) -> ProjectionFrame {
        let f = Float(seed)
        return ProjectionFrame(
            frame_index: UInt64(seed),
            gaze_origin_m: Vec3(x: f, y: f, z: f),
            gaze_direction_unit: Vec3(x: 0, y: 0, z: 1),
            last_hit_point_m: Vec3(x: f * 2, y: f * 2, z: f * 2),
            trail: [Vec3(x: f, y: f, z: 0)]
        )
    }

    private func uuidForSeed(_ seed: Int) -> UUID {
        let hex = String(format: "%012x", seed)
        return UUID(uuidString: "00000000-0000-0000-0000-\(hex)")!
    }
}
