import XCTest
import CryptoKit
@testable import SpatialReplayCore

/// Six-test encoding purity suite.
/// These tests form a firewall against nondeterminism leaking into the hash path.
final class EncodingPurityTests: XCTestCase {

    // ── Test 1: Preimage purity ──────────────────────────────────────────────
    // Same semantic event (same seed) → identical canonical byte sequences.
    // This is the foundational property everything else depends on.
    func testHashPreimagePurity() {
        let e1 = makeEvent(seed: 42)
        let e2 = makeEvent(seed: 42)
        XCTAssertEqual(
            CanonicalEncoder.encodeEvent(e1),
            CanonicalEncoder.encodeEvent(e2),
            "Same-seed events must produce identical canonical bytes"
        )
    }

    // ── Test 2: hash_this_event excluded from preimage ────────────────────────
    // hash_this_event is stored on the envelope but is NOT part of the canonical
    // encoding — it's the output of encoding, not an input. This test proves the
    // boundary is respected: changing the stored hash doesn't change the preimage.
    func testHashThisEventExcludedFromPreimage() {
        let base = makeEvent(seed: 7)
        let differentStoredHash = OracleEventEnvelope(
            event_id: base.event_id,
            event_type: base.event_type,
            timestamp_device_ns: base.timestamp_device_ns,
            timestamp_log_ns: base.timestamp_log_ns,
            source: base.source,
            confidence: base.confidence,
            frame_index: base.frame_index,
            payload: base.payload,
            hash_prev_event: base.hash_prev_event,
            hash_this_event: Hash32(bytes: Data(repeating: 0xDE, count: 32))
        )
        XCTAssertEqual(
            CanonicalEncoder.encodeEvent(base),
            CanonicalEncoder.encodeEvent(differentStoredHash),
            "hash_this_event must not appear in the canonical preimage"
        )
    }

    // ── Test 3: Canonical ≠ Codable ───────────────────────────────────────────
    // The canonical hash must differ from a JSON-derived hash of the same event.
    // If this fails, canonical encoding has collapsed into Codable, which is not
    // bit-stable across Swift versions or field reorderings.
    func testNoCodableImplicitHashing() throws {
        let event = makeEvent(seed: 42)
        let jsonData = try JSONEncoder().encode(event)
        let jsonHash = Hash32(bytes: Data(SHA256.hash(data: jsonData)))
        let canonicalHash = ProjectionHasher.eventHash(event)
        XCTAssertNotEqual(
            jsonHash,
            canonicalHash,
            "Canonical hash must be independent of Codable/JSON serialization"
        )
    }

    // ── Test 4: Canonical hash stability ─────────────────────────────────────
    // Same event encoded three times → identical Hash32 every time.
    // Guards against any internal state or time-dependent path in the hasher.
    func testCanonicalHashStability() {
        let event = makeEvent(seed: 99)
        let h1 = ProjectionHasher.eventHash(event)
        let h2 = ProjectionHasher.eventHash(event)
        let h3 = ProjectionHasher.eventHash(event)
        XCTAssertEqual(h1, h2)
        XCTAssertEqual(h2, h3)
    }

    // ── Test 5: Different seeds → different preimages ─────────────────────────
    // Distinct semantic events must produce distinct canonical bytes.
    // Checks that the encoding is injective over the field values we actually use.
    func testDifferentSeedsProduceDifferentPreimages() {
        let e1 = makeEvent(seed: 1)
        let e2 = makeEvent(seed: 2)
        XCTAssertNotEqual(
            CanonicalEncoder.encodeEvent(e1),
            CanonicalEncoder.encodeEvent(e2),
            "Events from different seeds must produce distinct canonical bytes"
        )
    }

    // ── Test 6: State canonical encoding is deterministic ────────────────────
    // AppState with identical values must produce identical canonical bytes.
    // This guards the final-state digest used in CausalFingerprint.
    func testStateEncodingDeterminism() {
        let s1 = makeState()
        let s2 = makeState()
        XCTAssertEqual(CanonicalEncoder.encodeState(s1), CanonicalEncoder.encodeState(s2))
    }

    // MARK: - Helpers

    private func makeEvent(seed: Int) -> OracleEventEnvelope<GazeSamplePayload> {
        let f = Float(seed)
        let payload = GazeSamplePayload(
            origin_m: Vec3(x: f, y: f, z: f),
            direction_unit: Vec3(x: 0, y: 0, z: 1),
            hit_point_m: Vec3(x: f * 2, y: f * 2, z: f * 2),
            tracking_state: .normal,
            calibration_context_hash: "purity-ctx-\(seed)",
            provenance: "purity.test.v0"
        )
        let pending = OracleEventEnvelope(
            event_id: uuidForSeed(seed),
            event_type: .oracleGazeSample,
            timestamp_device_ns: UInt64(seed) * 1_000,
            timestamp_log_ns: UInt64(seed) * 1_001,
            source: .gaze,
            confidence: 1.0,
            frame_index: UInt64(seed),
            payload: payload,
            hash_prev_event: nil,
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
            hash_prev_event: nil,
            hash_this_event: realHash
        )
    }

    private func makeState() -> AppState {
        var s = AppState()
        s.frame_index         = 42
        s.gaze_origin_m       = Vec3(x: 1, y: 2, z: 3)
        s.gaze_direction_unit = Vec3(x: 0, y: 0, z: 1)
        s.last_hit_point_m    = Vec3(x: 2, y: 4, z: 6)
        s.trail               = [Vec3(x: 1, y: 1, z: 0), Vec3(x: 2, y: 2, z: 0)]
        s.last_event_hash     = Hash32(bytes: Data(repeating: 0xAB, count: 32))
        return s
    }

    private func uuidForSeed(_ seed: Int) -> UUID {
        UUID(uuidString: String(format: "00000000-0000-4000-8000-%012x", seed))!
    }
}
