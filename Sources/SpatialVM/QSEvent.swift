// DSVM-0 GENERATED FILE — DO NOT EDIT
// source: EVENT_SCHEMAS.v1
// generator: dsvm-schema-compiler@v1.0

private enum CodingKeys: String, CodingKey {
    case eventType
    case artifactId
    case loreId
    case nodeId
    case portalId
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
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let type = try container.decode(String.self, forKey: .eventType)

        switch type {
        case "choose_ascension":
            self = .chooseAscension
        case "choose_creation":
            self = .chooseCreation
        case "discover_artifact":
            let artifactId = try container.decode(String.self, forKey: .artifactId)
            self = .discoverArtifact(artifactId: artifactId)
        case "enter_node":
            let nodeId = try container.decode(String.self, forKey: .nodeId)
            self = .enterNode(nodeId: nodeId)
        case "node_completed":
            let nodeId = try container.decode(String.self, forKey: .nodeId)
            self = .nodeCompleted(nodeId: nodeId)
        case "portal_unlocked":
            let portalId = try container.decode(String.self, forKey: .portalId)
            self = .portalUnlocked(portalId: portalId)
        case "reveal_lore":
            let loreId = try container.decode(String.self, forKey: .loreId)
            self = .revealLore(loreId: loreId)
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
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(eventType, forKey: .eventType)
        switch self {
        case .chooseAscension: break
        case .chooseCreation: break
        case .discoverArtifact(let artifactId):
            try container.encode(artifactId, forKey: .artifactId)
        case .enterNode(let nodeId):
            try container.encode(nodeId, forKey: .nodeId)
        case .nodeCompleted(let nodeId):
            try container.encode(nodeId, forKey: .nodeId)
        case .portalUnlocked(let portalId):
            try container.encode(portalId, forKey: .portalId)
        case .revealLore(let loreId):
            try container.encode(loreId, forKey: .loreId)
        }
    }
}
