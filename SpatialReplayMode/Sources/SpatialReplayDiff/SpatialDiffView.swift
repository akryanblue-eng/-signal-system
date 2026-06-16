import SwiftUI
import SpatialReplayDebugger

/// Top-level diff console.
/// Takes two DebugSnapshot arrays (left = live, right = replay/alt) and renders
/// the complete split comparison surface. All truth computation happens in DiffEngine
/// before this view is constructed — this view is a pure function of its inputs.
public struct SpatialDiffView: View {
    public let left: [DebugSnapshot]
    public let right: [DebugSnapshot]

    @State private var selectedFrame: UInt64 = 0

    public init(left: [DebugSnapshot], right: [DebugSnapshot]) {
        self.left = left
        self.right = right
    }

    public var body: some View {
        let frames = DiffEngine.buildDiff(left: left, right: right)
        let fork = DiffEngine.detectForkPoint(in: frames)

        VStack(spacing: 0) {
            // Top row: left trace | right trace
            HStack(spacing: 0) {
                tracePanel(label: "LIVE", snapshots: left)
                    .frame(maxWidth: .infinity)
                Divider().background(Color.gray.opacity(0.4))
                tracePanel(label: "REPLAY", snapshots: right)
                    .frame(maxWidth: .infinity)
            }
            .frame(maxHeight: .infinity)

            Divider().background(Color.gray.opacity(0.4))

            // Shared diff timeline
            DiffTimelineView(
                frames: frames,
                forkPoint: fork,
                selectedFrame: $selectedFrame
            )
            .frame(height: 64)

            Divider().background(Color.gray.opacity(0.4))

            // Fork trace
            ForkTraceView(frames: frames, forkPoint: fork)
                .frame(height: 180)
        }
        .background(Color.black)
    }

    // MARK: - Side panel

    @ViewBuilder
    private func tracePanel(label: String, snapshots: [DebugSnapshot]) -> some View {
        let current = snapshots.first { $0.frame_index == selectedFrame }
        VStack(spacing: 0) {
            Text(label)
                .font(.caption.bold())
                .foregroundColor(.gray)
                .padding(.vertical, 6)
            Divider().background(Color.gray.opacity(0.3))
            EventChainGraphView(snapshots: snapshots)
                .frame(height: 80)
            Divider().background(Color.gray.opacity(0.3))
            FrameViewerView(frame: current)
                .frame(maxHeight: .infinity)
        }
    }
}
