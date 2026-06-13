import SwiftUI
import RealityKit
import RealityKitContent

struct SkyHighView: View {
	@Binding var travelerState: TravelerState

	@State private var root: Entity?
	@State private var realityBaseline: Entity?
	@State private var realityAscended: Entity?
	@State private var inversionFlash: Entity?

	@State private var pendingSceneEffects = PendingSceneEffects()

	// MARK: - Node-local VM

	enum QSEvent: Equatable { case onEnterNode(nodeId: String) }

	enum Reaction: Equatable { case setFlag(String, Bool) }

	enum SceneEffect: Equatable { case flashEntity(name: String) }

	struct PendingSceneEffects: Equatable { var effects: [SceneEffect] = [] }

	struct Rule: Equatable {
		let whenEvent: QSEvent
		let condition: (TravelerState) -> Bool
		let thenReactions: [Reaction]
		let thenSceneEffects: [SceneEffect]
		let isOneShot: Bool
		let label: String
	}

	func rules() -> [Rule] {
		[
			Rule(
				whenEvent: .onEnterNode(nodeId: "sky-high"),
				condition: { $0.ascension >= 1 },
				thenReactions: [.setFlag("skyHighVariant:ascended", true)],
				thenSceneEffects: [.flashEntity(name: "InversionFlash")],
				isOneShot: true,
				label: "SkyHighEnterAscended"
			),
			Rule(
				whenEvent: .onEnterNode(nodeId: "sky-high"),
				condition: { $0.ascension < 1 },
				thenReactions: [.setFlag("skyHighVariant:baseline", true)],
				thenSceneEffects: [.flashEntity(name: "InversionFlash")],
				isOneShot: true,
				label: "SkyHighEnterBaseline"
			)
		]
	}

	private func evaluate(_ event: QSEvent) -> (reactions: [Reaction], scene: [SceneEffect]) {
		for r in rules() where r.whenEvent == event && r.condition(travelerState) {
			return (r.thenReactions, r.thenSceneEffects)
		}
		return ([], [])
	}

	private func apply(_ reactions: [Reaction]) {
		var next = travelerState
		for r in reactions {
			switch r {
			case .setFlag(let k, let v): next.flags[k] = v
			}
		}
		travelerState = next
	}

	private func emit(_ event: QSEvent) {
		let (reactions, sceneDelta) = evaluate(event)
		pendingSceneEffects.effects.append(contentsOf: sceneDelta)
		apply(reactions)
	}

	// MARK: - View

	var body: some View {
		RealityView { content in
			let scene = try await Entity(named: "SkyHigh", in: realityKitContentBundle)
			content.add(scene)

			self.root = scene.findEntity(named: "SkyHighRoot") ?? scene
			self.realityBaseline = scene.findEntity(named: "Reality_Baseline")
			self.realityAscended = scene.findEntity(named: "Reality_Ascended")
			self.inversionFlash = scene.findEntity(named: "InversionFlash")

			emit(.onEnterNode(nodeId: "sky-high"))
			projectWorld()
		} update: { _ in
			projectWorld()
		}
	}

	// MARK: - Projection (dual-reality toggle)

	private func projectWorld() {
		let ascended = travelerState.ascension >= 1
		realityAscended?.isEnabled = ascended
		realityBaseline?.isEnabled = !ascended
		consumePendingSceneEffects()
	}

	// MARK: - SceneEffects

	private func consumePendingSceneEffects() {
		guard let root else { return }
		let effects = pendingSceneEffects.effects
		guard !effects.isEmpty else { return }
		pendingSceneEffects.effects = []

		for e in effects {
			switch e {
			case .flashEntity(let name):
				if let target = root.findEntity(named: name) { flash(target) }
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
}
