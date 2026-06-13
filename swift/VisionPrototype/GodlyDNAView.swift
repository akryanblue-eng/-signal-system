import SwiftUI
import RealityKit
import RealityKitContent

struct GodlyDNAView: View {
	@Binding var travelerState: TravelerState
	@EnvironmentObject var navigator: NodeNavigator

	@State private var root: Entity?

	@State private var portalAscension: Entity?
	@State private var portalCreation: Entity?

	@State private var choiceLockGlow: Entity?
	@State private var choiceTextAscension: Entity?
	@State private var choiceTextCreation: Entity?

	@State private var blockerAscension: Entity?
	@State private var blockerCreation: Entity?

	@State private var pendingSceneEffects = PendingSceneEffects()

	// MARK: - Node-local VM

	enum QSEvent: Equatable {
		case onEnterNode(nodeId: String)
		case onChoiceAscension
		case onChoiceCreation
	}

	enum Reaction: Equatable {
		case setFlag(String, Bool)
		case lockGeneChoice(GeneChoice)
		case addAscension(Int)
	}

	enum SceneEffect: Equatable {
		case pulseEntity(name: String)
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
				whenEvent: .onChoiceAscension,
				thenReactions: [
					.lockGeneChoice(.ascension),
					.addAscension(1),
					.setFlag("geneChoiceLocked", true),
					.setFlag("choseAscension", true)
				],
				thenSceneEffects: [
					.pulseEntity(name: "Portal_Ascension"),
					.flashEntity(name: "ChoiceLockGlow")
				],
				isOneShot: true,
				label: "GodlyDNAChoiceAscension"
			),
			Rule(
				whenEvent: .onChoiceCreation,
				thenReactions: [
					.lockGeneChoice(.creation),
					.setFlag("geneChoiceLocked", true),
					.setFlag("choseCreation", true)
				],
				thenSceneEffects: [
					.pulseEntity(name: "Portal_Creation"),
					.flashEntity(name: "ChoiceLockGlow")
				],
				isOneShot: true,
				label: "GodlyDNAChoiceCreation"
			)
		]
	}

	private func evaluate(_ event: QSEvent) -> (reactions: [Reaction], scene: [SceneEffect]) {
		let r = rules().first(where: { $0.whenEvent == event })
		return (r?.thenReactions ?? [], r?.thenSceneEffects ?? [])
	}

	private func apply(_ reactions: [Reaction]) {
		var next = travelerState

		for r in reactions {
			switch r {
			case .setFlag(let key, let value):
				next.flags[key] = value

			case .addAscension(let delta):
				next.ascension += delta

			case .lockGeneChoice(let choice):
				// write-once firewall
				guard next.geneChoice == nil else {
					next.flags["illegalChoiceAttemptIgnored"] = true
					break
				}
				next.geneChoice = choice
			}
		}

		travelerState = next
	}

	private func emit(_ event: QSEvent) {
		let (reactions, sceneDelta) = evaluate(event)

		// accumulate (never suppress)
		pendingSceneEffects.effects.append(contentsOf: sceneDelta)

		apply(reactions)
	}

	// MARK: - View

	var body: some View {
		RealityView { content in
			let scene = try await Entity(named: "GodlyDNA", in: realityKitContentBundle)
			content.add(scene)

			self.root = scene.findEntity(named: "GodlyDNARoot") ?? scene

			self.portalAscension = scene.findEntity(named: "Portal_Ascension")
			self.portalCreation = scene.findEntity(named: "Portal_Creation")

			self.choiceLockGlow = scene.findEntity(named: "ChoiceLockGlow")
			self.choiceTextAscension = scene.findEntity(named: "ChoiceText_Ascension")
			self.choiceTextCreation = scene.findEntity(named: "ChoiceText_Creation")

			self.blockerAscension = scene.findEntity(named: "PortalBlocker_Ascension")
			self.blockerCreation = scene.findEntity(named: "PortalBlocker_Creation")

			ensureInteractive(portalAscension)
			ensureInteractive(portalCreation)

			emit(.onEnterNode(nodeId: "godly-dna"))
			projectWorld()
		} update: { _ in
			projectWorld()
		}
		.gesture(
			TapGesture()
				.targetedToAnyEntity()
				.onEnded { value in
					handleTap(on: value.entity)
				}
		)
	}

	private func handleTap(on entity: Entity) {
		switch entity.name {
		case "Portal_Ascension":
			emit(.onChoiceAscension)
			navigator.navigateTo(.skyHigh)

		case "Portal_Creation":
			emit(.onChoiceCreation)
			navigator.navigateTo(.skyHigh)

		default:
			return
		}
	}

	// MARK: - Projection

	private func projectWorld() {
		switch travelerState.geneChoice {
		case nil:
			setEnabled(choiceLockGlow, false)
			setEnabled(choiceTextAscension, false)
			setEnabled(choiceTextCreation, false)
			setEnabled(blockerAscension, false)
			setEnabled(blockerCreation, false)

		case .some(.ascension):
			setEnabled(choiceLockGlow, true)
			setEnabled(choiceTextAscension, true)
			setEnabled(choiceTextCreation, false)
			setEnabled(blockerCreation, true)
			setEnabled(blockerAscension, false)

		case .some(.creation):
			setEnabled(choiceLockGlow, true)
			setEnabled(choiceTextAscension, false)
			setEnabled(choiceTextCreation, true)
			setEnabled(blockerAscension, true)
			setEnabled(blockerCreation, false)
		}

		consumePendingSceneEffects()
	}

	private func consumePendingSceneEffects() {
		guard let root else { return }
		let effects = pendingSceneEffects.effects
		guard !effects.isEmpty else { return }
		pendingSceneEffects.effects = []

		for e in effects {
			switch e {
			case .pulseEntity(let name):
				if let target = root.findEntity(named: name) { pulse(target) }
			case .flashEntity(let name):
				if let target = root.findEntity(named: name) { flash(target) }
			}
		}
	}

	// MARK: - Helpers

	private func ensureInteractive(_ entity: Entity?) {
		guard let entity else { return }
		if entity.components[CollisionComponent.self] == nil {
			entity.components.set(CollisionComponent(shapes: [.generateBox(size: [0.3, 0.3, 0.3])]))
		}
		if entity.components[InputTargetComponent.self] == nil {
			entity.components.set(InputTargetComponent())
		}
	}

	private func setEnabled(_ entity: Entity?, _ enabled: Bool) {
		entity?.isEnabled = enabled
	}

	private func pulse(_ entity: Entity) {
		let original = entity.transform
		var up = original
		up.scale *= SIMD3<Float>(repeating: 1.08)

		entity.move(to: up, relativeTo: entity.parent, duration: 0.12, timingFunction: .easeInOut)
		DispatchQueue.main.asyncAfter(deadline: .now() + 0.12) {
			entity.move(to: original, relativeTo: entity.parent, duration: 0.12, timingFunction: .easeInOut)
		}
	}

	private func flash(_ entity: Entity) {
		let wasEnabled = entity.isEnabled
		entity.isEnabled = true
		DispatchQueue.main.asyncAfter(deadline: .now() + 0.18) {
			entity.isEnabled = wasEnabled
		}
	}
}
