import XCTest
import Foundation
@testable import SpatialReplayCore

/// Golden Replay Trace Snapshot (GRTS) test suite.
///
/// Each test produces a CausalFingerprint — the 4-field identity vector that
/// collapses a full ReplayResult into a comparable artifact.
///
/// CI contract:
///   golden fingerprint ← reference build, committed to repo
///   candidate fingerprint ← new commit
///   firstDivergence(between:and:) → nil means pass, non-nil is the regression trace
final class GoldenSnapshotTests: XCTestCase {

    // ── Test 1: Fingerprint determinism ──────────────────────────────────────
    // Same trace fed twice → identical CausalFingerprint on both runs.
    // This is the foundational GRTS invariant.
    func testFingerprintDeterminism() throws {
        let trace = makeTrace(seed: 42, count: 200)
        let r1 = try runReplay(trace)
        let r2 = try runReplay(trace)
        let f1 = computeFingerprint(from: r1)
        let f2 = computeFingerprint(from: r2)
        let divergence = firstDivergence(between: f1, and: f2)
        XCTAssertNil(divergence, "Fingerprints must be identical: \(divergence ?? "")")
    }

    // ── Test 2: Payload mutation → fingerprint divergence ────────────────────
    // Silently corrupted payload (chain hashes untouched) must produce a
    // different fingerprint. This is the GRTS sensitivity gate.
    func testMutationProducesDivergentFingerprint() throws {
        let trace = makeTrace(seed: 7, count: 100)
        var corrupted = trace
        corrupted[40] = rebuildWithMutatedOrigin(trace[40], origin: Vec3(x: 777, y: 777, z: 777))

        let clean     = computeFingerprint(from: try runReplay(trace))
        let dirty     = computeFingerprint(from: try runReplay(corrupted))
        XCTAssertNotNil(firstDivergence(between: clean, and: dirty),
                        "Payload mutation must produce fingerprint divergence")
    }

    // ── Test 3: Chain break → replay throws before fingerprint is produced ───
    func testBrokenChainPreventsFingerprint() {
        var trace = makeTrace(seed: 3, count: 20)
        trace[10] = rebuildWithBrokenPrev(trace[10])
        XCTAssertThrowsError(try runReplay(trace))
    }

    // ── Test 4: Truncated trace → frame count divergence ─────────────────────
    // Dropping the last 10 events produces a fingerprint with a different
    // frameCount and divergent projection trace hash.
    func testTruncatedTraceDiverges() throws {
        let full      = makeTrace(seed: 11, count: 50)
        let truncated = Array(full.prefix(40))
        let fFull     = computeFingerprint(from: try runReplay(full))
        let fShort    = computeFingerprint(from: try runReplay(truncated))
        let diverge   = firstDivergence(between: fFull, and: fShort)
        XCTAssertNotNil(diverge)
        XCTAssertTrue(diverge?.contains("frame count") == true,
                      "First divergence should be frame count mismatch, got: \(diverge ?? "nil")")
    }

    // ── Test 5: Cross-seed fingerprints are distinct ──────────────────────────
    // Traces from different seeds must produce distinct fingerprints.
    func testDifferentSeedsProduceDifferentFingerprints() throws {
        let fA = computeFingerprint(from: try runReplay(makeTrace(seed: 1, count: 100)))
        let fB = computeFingerprint(from: try runReplay(makeTrace(seed: 2, count: 100)))
        XCTAssertNotNil(firstDivergence(between: fA, and: fB),
                        "Different seeds must produce non-matching fingerprints")
    }

    // ── Test 6: Serialized fingerprint round-trips cleanly ───────────────────
    // The fingerprint must survive JSON encode → decode with bitwise equality.
    // This validates the GRTS storage format (the committed golden artifact).
    func testFingerprintJSONRoundTrip() throws {
        let trace       = makeTrace(seed: 42, count: 50)
        let result      = try runReplay(trace)
        let original    = computeFingerprint(from: result)

        let encoder     = JSONEncoder()
        encoder.outputFormatting = .sortedKeys
        let jsonData    = try encoder.encode(original)
        let decoded     = try JSONDecoder().decode(CausalFingerprint.self, from: jsonData)

        XCTAssertEqual(original, decoded,
                       "CausalFingerprint must survive JSON round-trip unchanged")
    }

    // ── Test 7: Golden artifact text format (smoke test) ─────────────────────
    // Writes a human-readable summary of the snapshot and verifies it's non-empty.
    // In a real GRTS, this output would be committed to Tests/Fixtures/ and
    // compared against on every subsequent CI run.
    func testGoldenArtifactSummary() throws {
        let trace   = makeTrace(seed: 42, count: 200)
        let result  = try runReplay(trace)
        let fp      = computeFingerprint(from: result)
        let summary = makeArtifactSummary(fingerprint: fp, seed: 42, count: 200)

        XCTAssertFalse(summary.isEmpty)
        XCTAssertTrue(summary.contains("frame_count: 200"))
        XCTAssertTrue(summary.contains("core_version: 0"))
        // In CI: compare this string to the committed golden file in Tests/Fixtures/
    }

    // MARK: - Trace generator (mirrors ReplayHarnessTests)

    private func makeTrace(
        seed: UInt64,
        count: Int
    ) -> [OracleEventEnvelope<GazeSamplePayload>] {
        var events: [OracleEventEnvelope<GazeSamplePayload>] = []
        var lastHash: Hash32? = nil
        for i in 0..<count {
            let dir = Vec3(x: Float(i % 3) * 0.1, y: 0, z: 1)
            let hit = Vec3(x: dir.x * 2, y: dir.y * 2, z: dir.z * 2)
            let payload = GazeSamplePayload(
                origin_m: Vec3(x: 0, y: 0, z: 0),
                direction_unit: dir,
                hit_point_m: hit,
                tracking_state: .normal,
                calibration_context_hash: "seed_\(seed)",
                provenance: "grts.v0"
            )
            let pending = OracleEventEnvelope(
                event_id: UUID(uuidString: String(format: "%08x-0000-4000-8000-%012x",
                                                  UInt32(seed & 0xFFFF_FFFF), i))!,
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

    // MARK: - Mutation helpers

    private func rebuildWithMutatedOrigin(
        _ e: OracleEventEnvelope<GazeSamplePayload>,
        origin: Vec3
    ) -> OracleEventEnvelope<GazeSamplePayload> {
        let mutated = GazeSamplePayload(
            origin_m: origin,
            direction_unit: e.payload.direction_unit,
            hit_point_m: e.payload.hit_point_m,
            tracking_state: e.payload.tracking_state,
            calibration_context_hash: e.payload.calibration_context_hash,
            provenance: e.payload.provenance
        )
        return OracleEventEnvelope(
            event_id: e.event_id, event_type: e.event_type,
            timestamp_device_ns: e.timestamp_device_ns, timestamp_log_ns: e.timestamp_log_ns,
            source: e.source, confidence: e.confidence, frame_index: e.frame_index,
            payload: mutated, hash_prev_event: e.hash_prev_event, hash_this_event: e.hash_this_event
        )
    }

    private func rebuildWithBrokenPrev(
        _ e: OracleEventEnvelope<GazeSamplePayload>
    ) -> OracleEventEnvelope<GazeSamplePayload> {
        OracleEventEnvelope(
            event_id: e.event_id, event_type: e.event_type,
            timestamp_device_ns: e.timestamp_device_ns, timestamp_log_ns: e.timestamp_log_ns,
            source: e.source, confidence: e.confidence, frame_index: e.frame_index,
            payload: e.payload,
            hash_prev_event: Hash32(bytes: Data(repeating: 0, count: 32)),
            hash_this_event: e.hash_this_event
        )
    }

    // MARK: - Artifact serializer (v0 — plain text; v1 would be JSONL)

    private func makeArtifactSummary(
        fingerprint fp: CausalFingerprint,
        seed: UInt64,
        count: Int
    ) -> String {
        let hexEvent = fp.eventChainHash.bytes.map { String(format: "%02x", $0) }.joined()
        let hexProj  = fp.projectionTraceHash.bytes.map { String(format: "%02x", $0) }.joined()
        let hexState = fp.finalStateDigest.bytes.map { String(format: "%02x", $0) }.joined()
        return """
        core_version: 0
        seed: \(seed)
        frame_count: \(fp.frameCount)
        event_chain_hash: \(hexEvent)
        projection_trace_hash: \(hexProj)
        final_state_digest: \(hexState)
        """
    }
}
