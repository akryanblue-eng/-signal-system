import Foundation

// UI-only contract. UI = pure function of DebugSnapshot.
// No hashing, no reduction, no event interpretation lives here.
public struct DebugSnapshot: Identifiable, Equatable {
    public let id: UUID
    public let frame_index: UInt64
    public let event_hash: String
    public let projection_hash: String
    public let is_chain_valid: Bool
    public let is_projection_match: Bool

    public init(
        frame_index: UInt64,
        event_hash: String,
        projection_hash: String,
        is_chain_valid: Bool,
        is_projection_match: Bool
    ) {
        self.id = UUID()
        self.frame_index = frame_index
        self.event_hash = event_hash
        self.projection_hash = projection_hash
        self.is_chain_valid = is_chain_valid
        self.is_projection_match = is_projection_match
    }
}
