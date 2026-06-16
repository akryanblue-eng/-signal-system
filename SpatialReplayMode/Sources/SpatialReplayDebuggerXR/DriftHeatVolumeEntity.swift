#if canImport(RealityKit)
import RealityKit
import SpatialReplayDiff

#if os(iOS) || os(visionOS)
import UIKit

/// Mismatch Heat Cloud — projects diff divergence into a volumetric point field.
///
/// X = angular position (frame index → spiral angle)
/// Y = frame index scaled to metres
/// Z = depth proportional to divergence severity
///
/// Clean frames render no geometry. Only divergent frames emit heat nodes,
/// so the cloud's density and colour directly encode drift severity.
public final class DriftHeatVolumeEntity: Entity {
    private let spiralRadius: Float = 0.25
    private let frameStep: Float = 0.025     // metres per frame on Y axis

    public required init() { super.init() }

    public override init() {
        super.init()
        name = "DriftHeatVolume"
    }

    @MainActor
    public func update(frames: [DiffFrame]) {
        children.forEach { $0.removeFromParent() }

        for frame in frames {
            let heat = heatValue(frame)
            guard heat > 0 else { continue }

            let angle = Float(frame.frame_index) * 0.18    // spiral turns
            let x = cos(angle) * spiralRadius
            let z = sin(angle) * spiralRadius * 0.5
            let y = Float(frame.frame_index) * frameStep

            let radius = 0.012 + 0.018 * heat
            let mesh = MeshResource.generateSphere(radius: radius)
            let mat = SimpleMaterial(color: heatColor(heat), isMetallic: false)
            let node = ModelEntity(mesh: mesh, materials: [mat])
            node.position = SIMD3<Float>(x, y, z)
            addChild(node)
        }
    }

    /// 0 = clean, 0.5 = single divergence, 1.0 = both event + projection diverged
    private func heatValue(_ frame: DiffFrame) -> Float {
        if frame.event_diverged && frame.projection_diverged { return 1.0 }
        if frame.event_diverged || frame.projection_diverged { return 0.5 }
        return 0.0
    }

    private func heatColor(_ heat: Float) -> UIColor {
        let red   = CGFloat(min(1, heat * 1.6))
        let green = CGFloat(max(0, 1 - heat * 1.4))
        return UIColor(red: red, green: green, blue: 0, alpha: CGFloat(0.5 + heat * 0.4))
    }
}
#endif
#endif
