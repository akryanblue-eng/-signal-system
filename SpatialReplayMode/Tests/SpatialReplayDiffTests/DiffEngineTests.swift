import XCTest
@testable import SpatialReplayDiff
import SpatialReplayDebugger

final class DiffEngineTests: XCTestCase {

    // Identical traces produce zero divergence.
    func testIdenticalTracesNoDivergence() {
        let trace = makeTrace(count: 10, eventSeed: "abc", projSeed: "xyz", chainValid: true)
        let frames = DiffEngine.buildDiff(left: trace, right: trace)
        XCTAssertTrue(frames.allSatisfy { !$0.event_diverged && !$0.projection_diverged })
    }

    // Single event hash mutation at frame 5 → eventFork at frame 5.
    func testEventForkDetection() {
        let left = makeTrace(count: 10, eventSeed: "aaa", projSeed: "bbb", chainValid: true)
        var right = left
        right[5] = mutateEventHash(right[5])
        let frames = DiffEngine.buildDiff(left: left, right: right)
        let fork = DiffEngine.detectForkPoint(in: frames)
        XCTAssertNotNil(fork)
        XCTAssertEqual(fork?.frame_index, 5)
        XCTAssertEqual(fork?.type, .eventFork)
    }

    // Projection-only divergence (event hashes identical) → projectionFork.
    func testProjectionForkDetection() {
        let left = makeTrace(count: 8, eventSeed: "ccc", projSeed: "ddd", chainValid: true)
        var right = left
        right[3] = mutateProjHash(right[3])
        let frames = DiffEngine.buildDiff(left: left, right: right)
        let fork = DiffEngine.detectForkPoint(in: frames)
        XCTAssertEqual(fork?.type, .projectionFork)
        XCTAssertEqual(fork?.frame_index, 3)
    }

    // Fork at frame 2 + projection divergence across 3+ later frames → cascadingDrift.
    func testCascadingDriftClassification() {
        let left = makeTrace(count: 10, eventSeed: "eee", projSeed: "fff", chainValid: true)
        var right = left
        right[2] = mutateEventHash(right[2])
        right[4] = mutateProjHash(right[4])
        right[5] = mutateProjHash(right[5])
        right[6] = mutateProjHash(right[6])
        let frames = DiffEngine.buildDiff(left: left, right: right)
        let fork = DiffEngine.detectForkPoint(in: frames)
        XCTAssertEqual(fork?.type, .cascadingDrift)
    }

    // Shorter right trace — missing frames encoded as "nil" hashes → diverged.
    func testMissingFramesAreDivergence() {
        let left = makeTrace(count: 5, eventSeed: "ggg", projSeed: "hhh", chainValid: true)
        let right = Array(left.prefix(3))
        let frames = DiffEngine.buildDiff(left: left, right: right)
        XCTAssertEqual(frames.count, 5)
        XCTAssertTrue(frames[3].event_diverged)
        XCTAssertTrue(frames[4].event_diverged)
    }

    // MARK: - Helpers

    private func makeTrace(
        count: Int,
        eventSeed: String,
        projSeed: String,
        chainValid: Bool
    ) -> [DebugSnapshot] {
        (0..<count).map { i in
            DebugSnapshot(
                frame_index: UInt64(i),
                event_hash: "\(eventSeed)-\(i)",
                projection_hash: "\(projSeed)-\(i)",
                is_chain_valid: chainValid,
                is_projection_match: true
            )
        }
    }

    private func mutateEventHash(_ s: DebugSnapshot) -> DebugSnapshot {
        DebugSnapshot(
            frame_index: s.frame_index,
            event_hash: s.event_hash + "-mutated",
            projection_hash: s.projection_hash,
            is_chain_valid: s.is_chain_valid,
            is_projection_match: s.is_projection_match
        )
    }

    private func mutateProjHash(_ s: DebugSnapshot) -> DebugSnapshot {
        DebugSnapshot(
            frame_index: s.frame_index,
            event_hash: s.event_hash,
            projection_hash: s.projection_hash + "-mutated",
            is_chain_valid: s.is_chain_valid,
            is_projection_match: false
        )
    }
}
