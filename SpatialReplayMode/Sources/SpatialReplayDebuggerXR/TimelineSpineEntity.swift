#if canImport(RealityKit)
import RealityKit
import SpatialReplayDiff

#if os(iOS) || os(visionOS)
import UIKit

/// The Timeline Spine — time as a physical vertical axis.
/// Each DiffFrame becomes a node: green = match, amber = event fork,
/// orange = projection drift, red = both diverged.
/// The selected frame node is enlarged.
public final class TimelineSpineEntity: Entity {
    private let nodeSpacing: Float = 0.04    // metres between frames on the Y axis
    private let nodeRadius: Float = 0.007
    private let selectedScale: Float = 2.2

    public required init() { super.init() }

    public override init() {
        super.init()
        name = "TimelineSpine"
    }

    @MainActor
    public func updateNodes(frames: [DiffFrame], selectedFrame: UInt64) {
        children.forEach { $0.removeFromParent() }
        guard !frames.isEmpty else { return }

        let totalHeight = Float(frames.count - 1) * nodeSpacing
        let originY = -totalHeight / 2

        for (i, frame) in frames.enumerated() {
            let y = originY + Float(i) * nodeSpacing
            let isSelected = frame.frame_index == selectedFrame
            let radius = isSelected ? nodeRadius * selectedScale : nodeRadius

            let mesh = MeshResource.generateSphere(radius: radius)
            let mat = SimpleMaterial(color: nodeColor(frame), isMetallic: false)
            let node = ModelEntity(mesh: mesh, materials: [mat])
            node.position = SIMD3<Float>(0, y, 0)
            node.name = "spine_\(frame.frame_index)"
            addChild(node)
        }
    }

    private func nodeColor(_ frame: DiffFrame) -> UIColor {
        if frame.event_diverged && frame.projection_diverged { return .systemRed }
        if frame.event_diverged   { return UIColor(red: 1, green: 0.6, blue: 0, alpha: 1) }
        if frame.projection_diverged { return .systemOrange }
        return .systemGreen
    }
}
#endif
#endif
