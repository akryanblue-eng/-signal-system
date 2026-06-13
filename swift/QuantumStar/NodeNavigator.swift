import SwiftUI

enum CurrentNode: String {
    case neonInNirvana = "neon-in-nirvana"
    case godlyDNA = "godly-dna"
    case skyHigh = "sky-high"
}

@MainActor
final class NodeNavigator: ObservableObject {
    @Published var currentNode: CurrentNode = .neonInNirvana

    func navigateTo(_ node: CurrentNode) {
        currentNode = node
    }
}
