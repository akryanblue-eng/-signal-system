import SwiftUI
import SpatialReplayDiff
import SpatialReplayDebugger

/// 2D fallback console — identical causal data, flat SwiftUI surface.
/// Use this on platforms without RealityKit / ImmersiveSpace support,
/// or as a companion window alongside the immersive layer.
public struct SplitViewRoot: View {
    public let left: [DebugSnapshot]
    public let right: [DebugSnapshot]

    public init(left: [DebugSnapshot], right: [DebugSnapshot]) {
        self.left  = left
        self.right = right
    }

    public var body: some View {
        SpatialDiffView(left: left, right: right)
    }
}
