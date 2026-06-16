import XCTest
@testable import SpatialReplayCore

final class ReplayHarnessTests: XCTestCase {

    // Same event log fed to runReplay twice must produce bit-identical hash traces.
    func testReplayDeterminism() throws {
        let events = makeDeterministicTrace(seed: 42, count: 200)
        let run1 = try runReplay(events)
        let run2 = try runReplay(events)
        XCTAssertEqual(run1.projectionHashes, run2.projectionHashes)
        XCTAssertEqual(run1.eventHashes, run2.eventHashes)
    }

    // Same event encoded twice must produce the same hash.
    func testCanonicalEncodingStability() {
        let event = makeDeterministicTrace(seed: 1, count: 1)[0]
        let h1 = ProjectionHasher.eventHash(event)
        let h2 = ProjectionHasher.eventHash(event)
        XCTAssertEqual(h1, h2)
    }

    // Corrupting a payload field must produce a different projection hash trace
    // from the uncorrupted run — even if only one event is changed.
    func testMutationBreaksProjectionHashes() throws {
        let events = makeDeterministicTrace(seed: 7, count: 50)
        var corrupted = events
        corrupted[25] = mutatePayloadOrigin(events[25], newOrigin: Vec3(x: 999, y: 999, z: 999))

        let clean = try runReplay(events)
        let dirty = try runReplay(corrupted)
        XCTAssertNotEqual(clean.projectionHashes, dirty.projectionHashes)
    }

    // Breaking hash_prev_event on any event mid-chain must cause runReplay to throw.
    func testBrokenChainThrows() {
        var events = makeDeterministicTrace(seed: 3, count: 10)
        events[5] = rebuildWithBrokenPrev(events[5])
        XCTAssertThrowsError(try runReplay(events)) { error in
            XCTAssertEqual(error as? ReducerError, .hashChainBroken)
        }
    }

    // MARK: - Deterministic trace generator

    /// Produces a hash-chained event log with no randomness.
    /// direction cycles through 3 patterns; UUIDs are derived from seed + index.
    func makeDeterministicTrace(
        seed: UInt64,
        count: Int
    ) -> [OracleEventEnvelope<GazeSamplePayload>] {
        var events: [OracleEventEnvelope<GazeSamplePayload>] = []
        var lastHash: Hash32? = nil

        for i in 0..<count {
            let direction = Vec3(
                x: Float(i % 3) * 0.1,
                y: 0.0,
                z: 1.0
            )
            let hit = Vec3(
                x: direction.x * 2,
                y: direction.y * 2,
                z: direction.z * 2
            )
            let payload = GazeSamplePayload(
                origin_m: Vec3(x: 0, y: 0, z: 0),
                direction_unit: direction,
                hit_point_m: hit,
                tracking_state: .normal,
                calibration_context_hash: "seed_\(seed)",
                provenance: "ci.generator.v1"
            )

            // Two-step construction: placeholder hash → real hash → final envelope
            let pending = OracleEventEnvelope(
                event_id: deterministicUUID(seed: seed, index: i),
                event_type: .oracleGazeSample,
                timestamp_device_ns: UInt64(i),
                timestamp_log_ns: UInt64(i),
                source: .gaze,
                confidence: 1.0,
                frame_index: UInt64(i),
                payload: payload,
                hash_prev_event: lastHash,
                hash_this_event: Hash32(bytes: Data(count: 32))
            )
            let realHash = ProjectionHasher.eventHash(pending)
            let final = OracleEventEnvelope(
                event_id: pending.event_id,
                event_type: pending.event_type,
                timestamp_device_ns: pending.timestamp_device_ns,
                timestamp_log_ns: pending.timestamp_log_ns,
                source: pending.source,
                confidence: pending.confidence,
                frame_index: pending.frame_index,
                payload: pending.payload,
                hash_prev_event: lastHash,
                hash_this_event: realHash
            )
            lastHash = realHash
            events.append(final)
        }
        return events
    }

    // MARK: - Helpers

    private func deterministicUUID(seed: UInt64, index: Int) -> UUID {
        let s = UInt32(seed & 0xFFFF_FFFF)
        let uuidStr = String(format: "%08x-0000-4000-8000-%012x", s, index)
        return UUID(uuidString: uuidStr)!
    }

    /// Replaces payload.origin_m; keeps all other fields and hashes unchanged.
    /// The unchanged hash_this_event is intentional — this simulates data tampering
    /// where the chain passes but payload content was silently corrupted.
    private func mutatePayloadOrigin(
        _ event: OracleEventEnvelope<GazeSamplePayload>,
        newOrigin: Vec3
    ) -> OracleEventEnvelope<GazeSamplePayload> {
        let mutated = GazeSamplePayload(
            origin_m: newOrigin,
            direction_unit: event.payload.direction_unit,
            hit_point_m: event.payload.hit_point_m,
            tracking_state: event.payload.tracking_state,
            calibration_context_hash: event.payload.calibration_context_hash,
            provenance: event.payload.provenance
        )
        return OracleEventEnvelope(
            event_id: event.event_id,
            event_type: event.event_type,
            timestamp_device_ns: event.timestamp_device_ns,
            timestamp_log_ns: event.timestamp_log_ns,
            source: event.source,
            confidence: event.confidence,
            frame_index: event.frame_index,
            payload: mutated,
            hash_prev_event: event.hash_prev_event,
            hash_this_event: event.hash_this_event
        )
    }

    /// Replaces hash_prev_event with all-zeros, breaking the chain at this event.
    private func rebuildWithBrokenPrev(
        _ event: OracleEventEnvelope<GazeSamplePayload>
    ) -> OracleEventEnvelope<GazeSamplePayload> {
        OracleEventEnvelope(
            event_id: event.event_id,
            event_type: event.event_type,
            timestamp_device_ns: event.timestamp_device_ns,
            timestamp_log_ns: event.timestamp_log_ns,
            source: event.source,
            confidence: event.confidence,
            frame_index: event.frame_index,
            payload: event.payload,
            hash_prev_event: Hash32(bytes: Data(repeating: 0, count: 32)),
            hash_this_event: event.hash_this_event
        )
    }
}
