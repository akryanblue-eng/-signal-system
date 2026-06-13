import SwiftUI

// MARK: - Shared truth (single source of truth)

struct TravelerState: Equatable, Codable {
	var visitedNodes: Set<String> = []
	var discoveredArtifacts: Set<String> = []
	var revealedLore: Set<String> = []
	var ascension: Int = 0

	// Node B
	var geneChoice: GeneChoice? = nil

	// Observability / future gates without engineization
	var flags: [String: Bool] = [:]
}

enum GeneChoice: String, Equatable, Codable {
	case ascension
	case creation
}

// MARK: - Navigation (pure routing, no meaning)

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

// MARK: - App entry

@main
struct QuantumStarApp: App {
	@StateObject private var navigator = NodeNavigator()
	@State private var travelerState = TravelerState()

	var body: some Scene {
		WindowGroup {
			QuantumStarRootView(travelerState: $travelerState)
				.environmentObject(navigator)
		}
	}
}

struct QuantumStarRootView: View {
	@Binding var travelerState: TravelerState
	@EnvironmentObject var navigator: NodeNavigator

	var body: some View {
		switch navigator.currentNode {
		case .neonInNirvana:
			NeonInNirvanaView(travelerState: $travelerState)

		case .godlyDNA:
			GodlyDNAView(travelerState: $travelerState)

		case .skyHigh:
			SkyHighView(travelerState: $travelerState)
		}
	}
}
