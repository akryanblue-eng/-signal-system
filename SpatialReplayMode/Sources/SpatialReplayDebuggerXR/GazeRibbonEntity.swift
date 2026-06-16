#if canImport(RealityKit)
import RealityKit
import SpatialReplayCore

#if os(iOS) || os(visionOS)
import UIKit

/// A RealityKit entity that renders a gaze trail as a spline of colored spheres.
/// Instantiate with a tint colour — cyan for Live, systemPurple for Golden.
public final class GazeRibbonEntity: Entity {
    private let tint: UIColor
    private let nodeRadius: Float = 0.008
    private let trailFadeSteps: Int = 30   // max visible nodes before oldest drops off

    public required init() {
        self.tint = .cyan
        super.init()
    }

    public init(tint: UIColor) {
        self.tint = tint
        super.init()
        name = "GazeRibbon_\(tint.description)"
    }

    /// Replace the entire trail with new Vec3 positions.
    @MainActor
    public func updateTrail(_ trail: [Vec3]) {
        children.forEach { $0.removeFromParent() }

        let visible = trail.suffix(trailFadeSteps)
        let count = visible.count
        for (i, point) in visible.enumerated() {
            let alpha = CGFloat(i + 1) / CGFloat(count)
            let radius = nodeRadius * Float(0.4 + 0.6 * alpha)
            let mesh = MeshResource.generateSphere(radius: radius)
            let mat = SimpleMaterial(
                color: tint.withAlphaComponent(alpha * 0.85),
                isMetallic: false
            )
            let node = ModelEntity(mesh: mesh, materials: [mat])
            node.position = SIMD3<Float>(point.x, point.y, point.z)
            addChild(node)
        }
    }
}
#endif  // os(iOS) || os(visionOS)
#endif  // canImport(RealityKit)
