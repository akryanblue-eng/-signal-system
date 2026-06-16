import Foundation

// MARK: - CausalFingerprint

/// Compact identity vector for a complete replay run.
/// Two runs are causally identical iff all four fields are equal.
///
/// Layer semantics (mirrors the 4-axis CI contract):
///   eventChainHash      — encoding stability + chain integrity
///   projectionTraceHash — execution determinism + projection integrity
///   frameCount          — sequence completeness
///   finalStateDigest    — reducer convergence
public struct CausalFingerprint: Equatable, Codable {
    public let eventChainHash: Hash32
    public let projectionTraceHash: Hash32
    public let frameCount: Int
    public let finalStateDigest: Hash32

    public init(
        eventChainHash: Hash32,
        projectionTraceHash: Hash32,
        frameCount: Int,
        finalStateDigest: Hash32
    ) {
        self.eventChainHash      = eventChainHash
        self.projectionTraceHash = projectionTraceHash
        self.frameCount          = frameCount
        self.finalStateDigest    = finalStateDigest
    }
}

// MARK: - Computation

/// Pure function — collapses a ReplayResult into a single comparable identity.
public func computeFingerprint(from result: ReplayResult) -> CausalFingerprint {
    let eventChainData = result.eventHashes.reduce(into: Data()) { $0.append($1.bytes) }
    let projData       = result.projectionHashes.reduce(into: Data()) { $0.append($1.bytes) }
    let stateData      = CanonicalEncoder.encodeState(result.finalState)

    return CausalFingerprint(
        eventChainHash:      ProjectionHasher.hash(eventChainData),
        projectionTraceHash: ProjectionHasher.hash(projData),
        frameCount:          result.projectionHashes.count,
        finalStateDigest:    ProjectionHasher.hash(stateData)
    )
}

// MARK: - SnapshotDivergence

/// First axis of divergence between two fingerprints, or nil if identical.
public func firstDivergence(
    between lhs: CausalFingerprint,
    and rhs: CausalFingerprint
) -> String? {
    if lhs.frameCount          != rhs.frameCount          { return "frame count: \(lhs.frameCount) vs \(rhs.frameCount)" }
    if lhs.eventChainHash      != rhs.eventChainHash      { return "event chain hash mismatch" }
    if lhs.projectionTraceHash != rhs.projectionTraceHash { return "projection trace hash mismatch" }
    if lhs.finalStateDigest    != rhs.finalStateDigest    { return "final state digest mismatch" }
    return nil
}
