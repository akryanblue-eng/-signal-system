import Foundation

struct TravelerState: Equatable, Codable {
    var visitedNodes: Set<String> = []
    var discoveredArtifacts: Set<String> = []
    var revealedLore: Set<String> = []
    var ascension: Int = 0

    var geneChoice: GeneChoice? = nil
    var flags: [String: Bool] = [:]
}

enum GeneChoice: String, Equatable, Codable {
    case ascension
    case creation
}
