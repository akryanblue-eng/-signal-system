import SwiftUI
import RealityKit
import RealityKitContent

struct NeonInNirvanaView: View {
	@Binding var travelerState: TravelerState
	@EnvironmentObject var navigator: NodeNavigator

	@State private var root: Entity?
	@State private var compass: Entity?
	@State private var portal: Entity?
	@State private var loreText: Entity?

	@State private var pendingSceneEffects = PendingSceneEffects()
	@State private var isProjecting = false

	// MARK: - VM Types (Node-local)

	enum QSEvent: Equatable {
		case onEnterNode(nodeId: String)
		case onArtifactDiscovered(nodeId: String, artifactId: String)
		case onPortalTapped(toNodeId: String)
	}

	enum Reaction: Equatable {
		case addArtifact(id: String)
		case revealLore(id: String)
		case addVisitedNode(id: String)
		case setFlag(String, Bool)
	}

	enum SceneEffect: Equatable {
		case flashEntity(name: String)
	}

	struct PendingSceneEffects: Equatable {
		var effects: [SceneEffect] = []
	}

	struct Rule: Equatable {
		let whenEvent: QSEvent
		let thenReactions: [Reaction]
		let thenSceneEffects: [SceneEffect]
		let isOneShot: Bool
		let label: String
	}

	func rules() -> [Rule] {
		[
			Rule(
				whenEvent: .onEnterNode(nodeId: "neon-in-nirvana"),
				thenReactions: [
					.addVisitedNode(id: "neon-in-nirvana")
				],
				thenSceneEffects: [],
				isOneShot: true,
				label: "NirvanaEnter"
			),

			Rule(
				whenEvent: .onArtifactDiscovered(nodeId: "neon-in-nirvana", artifactId: "broken-star-compass"),
				thenReactions: [
					.addArtifact(id: "broken-star-compass"),
					.revealLore(id: "map-remembers"),
					.setFlag("nirvana:portalUnlocked", true)
				],
				thenSceneEffects: [
					.flashEntity(name: "Portal")
				],
				isOneShot: true,
				label: "NirvanaCompassDiscovered"
			),

			// Portal tap has no meaning; it's routing only. No reactions needed.
			Rule(
				whenEvent: .onPortalTapped(toNodeId: "godly-dna"),
				thenReactions: [],
				thenSceneEffects: [],
				isOneShot: false,
				label: "NirvanaPortalTapped"
			)
		]
	}

	// MARK: - Evaluation / Reducer (pure)

	private func evaluate(_ event: QSEvent) -> (reactions: [Reaction], scene: [SceneEffect]) {
		let r = rules().first(where: { $0.whenEvent == event })
		return (r?.thenReactions ?? [], r?.thenSceneEffects ?? [])
	}

	private func apply(_ reactions: [Reaction]) {
		var next = travelerState
		for r in reactions {
			switch r {
			case .addVisitedNode(let id):
				next.visitedNodes.insert(id)
			case .addArtifact(let id):
				next.discoveredArtifacts.insert(id)
			case .revealLore(let id):
				next.revealedLore.insert(id)
			case .setFlag(let k, let v):
				next.flags[k] = v
			}
		}
		travelerState = next
	}

	// MARK: - Spine

	private func emit(_ event: QSEvent) {
		let (reactions, sceneDelta) = evaluate(event)

		// accumulate effects (never suppress)
		pendingSceneEffects.effects.append(contentsOf: sceneDelta)

		// reducer = truth authority
		apply(reactions)

		// routing decisions happen outside truth mutation
		if case .onPortalTapped(let toNodeId) = event, toNodeId == "godly-dna" {
			navigator.navigateTo(.godlyDNA)
		}
	}

	// MARK: - View

	var body: some View {
		RealityView { content in
			let scene = try await Entity(named: "NeonInNirvana", in: realityKitContentBundle)
			content.add(scene)

			self.root = scene.findEntity(named: "NirvanaRoot") ?? scene
			self.compass = scene.findEntity(named: "Compass")
			self.portal = scene.findEntity(named: "Portal")
			self.loreText = scene.findEntity(named: "LoreText")

			ensureInteractive(compass)

			emit(.onEnterNode(nodeId: "neon-in-nirvana"))
			projectWorld()
		} update: { _ in
			projectWorld()
		}
		.gesture(
			TapGesture()
				.targetedToAnyEntity()
				.onEnded { value in
					let tapped = value.entity
					switch tapped.name {
					case "Compass":
						emit(.onArtifactDiscovered(nodeId: "neon-in-nirvana", artifactId: "broken-star-compass"))

					case "Portal":
						// only allow if unlocked in truth
						guard travelerState.flags["nirvana:portalUnlocked"] == true else { return }
						emit(.onPortalTapped(toNodeId: "godly-dna"))

					default:
						break
					}
				}
		)
	}

	// MARK: - Projection (pure Σ -> Scene)

	private func projectWorld() {
		guard !isProjecting else { return }
		isProjecting = true
		defer { isProjecting = false }

		let portalUnlocked = travelerState.flags["nirvana:portalUnlocked"] == true

		portal?.isEnabled = portalUnlocked
		loreText?.isEnabled = travelerState.revealedLore.contains("map-remembers")

		consumePendingSceneEffects()
	}

	// MARK: - SceneEffects (epiphenomenal)

	private func consumePendingSceneEffects() {
		guard let root else { return }
		let effects = pendingSceneEffects.effects
		guard !effects.isEmpty else { return }
		pendingSceneEffects.effects = []

		for e in effects {
			switch e {
			case .flashEntity(let name):
				if let target = root.findEntity(named: name) {
					flash(target)
				}
			}
		}
	}

	private func flash(_ entity: Entity) {
		let wasEnabled = entity.isEnabled
		entity.isEnabled = true
		DispatchQueue.main.asyncAfter(deadline: .now() + 0.18) {
			entity.isEnabled = wasEnabled
		}
	}

	private func ensureInteractive(_ entity: Entity?) {
		guard let entity else { return }
		if entity.components[CollisionComponent.self] == nil {
			entity.components.set(CollisionComponent(shapes: [.generateBox(size: [0.2, 0.2, 0.2])]))
		}
		if entity.components[InputTargetComponent.self] == nil {
			entity.components.set(InputTargetComponent())
		}
	}
}
