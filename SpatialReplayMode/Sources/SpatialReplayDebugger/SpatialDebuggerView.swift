import SwiftUI

public struct SpatialDebuggerView: View {
    @State private var snapshots: [DebugSnapshot] = []
    @State private var selectedFrame: UInt64 = 0

    public init() {}

    public var body: some View {
        HStack(spacing: 0) {
            // Left column: causal graph + hash timeline
            VStack(spacing: 0) {
                EventChainGraphView(snapshots: snapshots)
                    .frame(maxHeight: .infinity)
                HashTimelineView(snapshots: snapshots, selectedFrame: $selectedFrame)
                    .frame(height: 220)
            }
            .frame(width: 320)

            Divider()

            // Centre: frame viewer
            FrameViewerView(frame: currentFrame)
                .frame(maxWidth: .infinity)

            Divider()

            // Right column: divergence heatmap + event inspector
            VStack(spacing: 0) {
                DivergenceHeatmapView(snapshots: snapshots)
                    .frame(maxHeight: .infinity)
                EventInspectorView(frame: currentFrame)
                    .frame(height: 220)
            }
            .frame(width: 320)
        }
        .background(Color.black)
    }

    private var currentFrame: DebugSnapshot? {
        snapshots.first { $0.frame_index == selectedFrame }
    }

    // Entry point for live/replay data ingestion
    public mutating func ingest(_ snapshot: DebugSnapshot) {
        snapshots.append(snapshot)
    }
}
