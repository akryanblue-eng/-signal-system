// DSVM-0 GENERATED FILE — DO NOT EDIT
// source: EVENT_SCHEMAS.v1
// generator: dsvm-schema-compiler@v1.0

private enum DiscriminatorKeys: String, CodingKey { case eventType }

public struct DiscoverArtifactPayload: Codable, Equatable {
    public let artifactId: String
}

public struct EnterNodePayload: Codable, Equatable {
    public let nodeId: String
}

public struct NodeCompletedPayload: Codable, Equatable {
    public let nodeId: String
}

public struct PortalUnlockedPayload: Codable, Equatable {
    public let portalId: String
}

public struct RevealLorePayload: Codable, Equatable {
    public let loreId: String
}

public enum QSEvent: Codable, Equatable {
    case chooseAscension
    case chooseCreation
    case discoverArtifact(artifactId: String)
    case enterNode(nodeId: String)
    case nodeCompleted(nodeId: String)
    case portalUnlocked(portalId: String)
    case revealLore(loreId: String)
}

extension QSEvent {
    public var eventType: String {
        switch self {
        case .chooseAscension: return "choose_ascension"
        case .chooseCreation: return "choose_creation"
        case .discoverArtifact: return "discover_artifact"
        case .enterNode: return "enter_node"
        case .nodeCompleted: return "node_completed"
        case .portalUnlocked: return "portal_unlocked"
        case .revealLore: return "reveal_lore"
        }
    }
}

extension QSEvent {
    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: DiscriminatorKeys.self)
        let type = try container.decode(String.self, forKey: .eventType)

        switch type {
        case "choose_ascension":
            self = .chooseAscension
        case "choose_creation":
            self = .chooseCreation
        case "discover_artifact":
            let payload = try DiscoverArtifactPayload(from: decoder)
            self = .discoverArtifact(artifactId: payload.artifactId)
        case "enter_node":
            let payload = try EnterNodePayload(from: decoder)
            self = .enterNode(nodeId: payload.nodeId)
        case "node_completed":
            let payload = try NodeCompletedPayload(from: decoder)
            self = .nodeCompleted(nodeId: payload.nodeId)
        case "portal_unlocked":
            let payload = try PortalUnlockedPayload(from: decoder)
            self = .portalUnlocked(portalId: payload.portalId)
        case "reveal_lore":
            let payload = try RevealLorePayload(from: decoder)
            self = .revealLore(loreId: payload.loreId)
        default:
            throw DecodingError.dataCorruptedError(
                forKey: .eventType,
                in: container,
                debugDescription: "Unknown eventType: \(type)"
            )
        }
    }
}

extension QSEvent {
    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: DiscriminatorKeys.self)
        try container.encode(eventType, forKey: .eventType)
        switch self {
        case .chooseAscension: break
        case .chooseCreation: break
        case .discoverArtifact(let artifactId):
            try DiscoverArtifactPayload(artifactId: artifactId).encode(to: encoder)
        case .enterNode(let nodeId):
            try EnterNodePayload(nodeId: nodeId).encode(to: encoder)
        case .nodeCompleted(let nodeId):
            try NodeCompletedPayload(nodeId: nodeId).encode(to: encoder)
        case .portalUnlocked(let portalId):
            try PortalUnlockedPayload(portalId: portalId).encode(to: encoder)
        case .revealLore(let loreId):
            try RevealLorePayload(loreId: loreId).encode(to: encoder)
        }
    }
}
