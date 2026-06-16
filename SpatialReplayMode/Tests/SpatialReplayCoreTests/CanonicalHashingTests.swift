import XCTest
@testable import SpatialReplayCore

final class CanonicalHashingTests: XCTestCase {

    // Identical Vec3 values must produce identical encoded bytes.
    func testVec3Determinism() {
        let a = Vec3(x: 1.0, y: 2.0, z: 3.0)
        let b = Vec3(x: 1.0, y: 2.0, z: 3.0)
        XCTAssertEqual(CanonicalEncoder.encode(a), CanonicalEncoder.encode(b))
    }

    // Same seed → same event → identical hash every time.
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

    // Reducer must reject an event whose hash_prev_event doesn't match state.
    func testReducerRejectsChainBrokenEvent() {
        let state = AppState()
        let event = makeChainBrokenEvent()
        XCTAssertThrowsError(try reduce(state, event)) { error in
            XCTAssertEqual(error as? ReducerError, .hashChainBroken)
        }
    }

    // Reducer must accept first event (nil prev hash matches empty state).
    func testReducerAcceptsFirstEvent() throws {
        let state = AppState()
        let event = makeSyntheticEvent(seed: 1)   // hash_prev_event: nil
        let next = try reduce(state, event)
        XCTAssertEqual(next.frame_index, 1)
        XCTAssertEqual(next.last_event_hash, event.hash_this_event)
    }

    // Consecutive events must chain correctly.
    func testReducerEventChain() throws {
        var state = AppState()
        let e1 = makeSyntheticEvent(seed: 1)           // prev = nil
        state = try reduce(state, e1)
        let e2 = makeSyntheticEvent(seed: 2, prevHash: e1.hash_this_event)
        state = try reduce(state, e2)
        XCTAssertEqual(state.frame_index, 2)
        XCTAssertEqual(state.last_event_hash, e2.hash_this_event)
    }

    // MARK: - Helpers

    private func makeSyntheticEvent(
        seed: Int,
        prevHash: Hash32? = nil
    ) -> OracleEventEnvelope<GazeSamplePayload> {
        let f = Float(seed)
        let payload = GazeSamplePayload(
            origin_m: Vec3(x: f, y: f, z: f),
            direction_unit: Vec3(x: 0, y: 0, z: 1),
            hit_point_m: Vec3(x: f * 2, y: f * 2, z: f * 2),
            tracking_state: .normal,
            calibration_context_hash: "ctx-\(seed)",
            provenance: "test-\(seed)"
        )
        // Build a pending envelope (placeholder hash) to derive the real hash
        let pending = OracleEventEnvelope(
            event_id: uuidForSeed(seed),
            event_type: .oracleGazeSample,
            timestamp_device_ns: UInt64(seed) * 1_000,
            timestamp_log_ns: UInt64(seed) * 1_001,
            source: .gaze,
            confidence: 1.0,
            frame_index: UInt64(seed),
            payload: payload,
            hash_prev_event: prevHash,
            hash_this_event: Hash32(bytes: Data(count: 32))
        )
        let realHash = ProjectionHasher.eventHash(pending)
        return OracleEventEnvelope(
            event_id: pending.event_id,
            event_type: pending.event_type,
            timestamp_device_ns: pending.timestamp_device_ns,
            timestamp_log_ns: pending.timestamp_log_ns,
            source: pending.source,
            confidence: pending.confidence,
            frame_index: pending.frame_index,
            payload: pending.payload,
            hash_prev_event: pending.hash_prev_event,
            hash_this_event: realHash
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

    // An event whose hash_prev_event doesn't match empty state (nil ≠ someHash).
    private func makeChainBrokenEvent() -> OracleEventEnvelope<GazeSamplePayload> {
        let fakeHash = Hash32(bytes: Data(repeating: 0xFF, count: 32))
        return makeSyntheticEvent(seed: 99, prevHash: fakeHash)
    }

    private func uuidForSeed(_ seed: Int) -> UUID {
        let hex = String(format: "%012x", seed)
        return UUID(uuidString: "00000000-0000-0000-0000-\(hex)")!
    }
}
