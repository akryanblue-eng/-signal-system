import SwiftUI
import RealityKit
import RealityKitContent

struct SkyHighView: View {
	@Binding var travelerState: TravelerState

	@State private var root: Entity?
	@State private var landmark: Entity?
	@State private var inversionFlash: Entity?

	@State private var pendingSceneEffects = PendingSceneEffects()
	@State private var isProjecting = false

	// MARK: - Node-local VM

	enum QSEvent: Equatable {
		case onEnterNode(nodeId: String)
	}

	enum Reaction: Equatable {
		case setFlag(String, Bool)
	}

	enum SceneEffect: Equatable {
		case flashEntity(name: String)
	}

	struct PendingSceneEffects: Equatable {
		var effects: [SceneEffect] = []
	}

	// Rule omits Equatable: condition is a closure and cannot synthesize it.
	struct Rule {
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

	// MARK: - Drift model (state-only causal memory field)

	// ascension = semantic depth; visitedNodes = experiential saturation.
	// Returns a value in [0, 1] representing accumulated narrative weight.
	private func driftFactor(from state: TravelerState) -> CGFloat {
		let ascensionWeight = CGFloat(state.ascension) * 0.7
		let visitWeight = CGFloat(state.visitedNodes.count) * 0.08
		return min(ascensionWeight + visitWeight, 1.0)
	}

	// Quantized decoder: three perceptual bands, not a continuous blend.
	// RealityKit materials are value snapshots — discrete bands give
	// XR-legible transitions instead of sub-perceptual drift.
	private func material(for drift: CGFloat) -> SimpleMaterial {
		switch drift {
		case 0.0..<0.33:
			return Self.vinedStoneMaterial
		case 0.33..<0.66:
			return Self.midMaterial
		default:
			return Self.goldMaterial
		}
	}

	// MARK: - Material lattice (static, constructed once)

	private static let vinedStoneMaterial =
		SimpleMaterial(color: .gray, roughness: 0.95, isMetallic: false)

	private static let midMaterial =
		SimpleMaterial(color: .green, roughness: 0.45, isMetallic: true)

	private static let goldMaterial =
		SimpleMaterial(color: .yellow, roughness: 0.15, isMetallic: true)

	// MARK: - Evaluation

	private func evaluate(_ event: QSEvent) -> (reactions: [Reaction], scene: [SceneEffect]) {
		guard let rule = rules().first(where: {
			$0.whenEvent == event && $0.condition(travelerState)
		}) else {
			return ([], [])
		}
		return (rule.thenReactions, rule.thenSceneEffects)
	}

	// MARK: - Reducer (state truth)

	private func apply(_ reactions: [Reaction]) {
		var next = travelerState
		for r in reactions {
			switch r {
			case .setFlag(let k, let v):
				next.flags[k] = v
			}
		}
		travelerState = next
	}

	// MARK: - Event spine

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

			self.root = scene.findEntity(named: "SkyHighRoot")
			self.landmark = scene.findEntity(named: "TheLandmark")
			self.inversionFlash = scene.findEntity(named: "InversionFlash")

			emit(.onEnterNode(nodeId: "sky-high"))
			projectWorld()
		} update: { _ in
			projectWorld()
		}
	}

	// MARK: - Projection (f(StateHistory) → Material Identity)

	private func projectWorld() {
		guard !isProjecting else { return }
		isProjecting = true
		defer { isProjecting = false }

		if let landmark,
		   var model = landmark.components[ModelComponent.self] {
			model.materials = [material(for: driftFactor(from: travelerState))]
			landmark.components.set(model)
		}

		consumePendingSceneEffects()
	}

	// MARK: - Scene effects (ephemeral)

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
