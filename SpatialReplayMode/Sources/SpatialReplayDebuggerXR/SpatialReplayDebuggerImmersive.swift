#if canImport(RealityKit)
import SwiftUI
import RealityKit
import SpatialReplayDiff
import SpatialReplayDebugger

#if os(visionOS) || os(iOS)
import UIKit

/// The primary immersive instrument surface.
///
/// Four spatial anchors placed in front of the user:
///   Left  (−0.5m, 0, −1.5m) — Live gaze ribbon (cyan)
///   Right (+0.5m, 0, −1.5m) — Golden replay ribbon (purple)
///   Centre (0, 0, −1.5m)    — Timeline spine (vertical diff axis)
///   Above  (0, 0.3, −2.0m)  — Drift heat volume (volumetric mismatch field)
///
/// Debugger rule: this view never recomputes truth.
/// It only renders DiffFrames produced by DiffEngine.
public struct SpatialReplayDebuggerImmersive: View {
    public let left: [DebugSnapshot]
    public let right: [DebugSnapshot]

    @StateObject private var diffVM      = DiffStreamViewModel()
    @StateObject private var timelineVM  = TimelineViewModel()
    @StateObject private var inspectorVM = InspectorViewModel()

    // @State entity refs are allocated once and survive SwiftUI re-renders
    @State private var liveRibbon   = GazeRibbonEntity(tint: .cyan)
    @State private var goldenRibbon = GazeRibbonEntity(tint: .systemPurple)
    @State private var spine        = TimelineSpineEntity()
    @State private var heatVolume   = DriftHeatVolumeEntity()

    public init(left: [DebugSnapshot], right: [DebugSnapshot]) {
        self.left  = left
        self.right = right
    }

    public var body: some View {
        RealityView { content in
            liveRibbon.position   = SIMD3<Float>(-0.5,  0,   -1.5)
            goldenRibbon.position = SIMD3<Float>( 0.5,  0,   -1.5)
            spine.position        = SIMD3<Float>( 0,    0,   -1.5)
            heatVolume.position   = SIMD3<Float>( 0,    0.3, -2.0)

            content.add(liveRibbon)
            content.add(goldenRibbon)
            content.add(spine)
            content.add(heatVolume)
        } update: { _ in
            spine.updateNodes(
                frames: diffVM.allFrames,
                selectedFrame: timelineVM.selectedFrame
            )
            heatVolume.update(frames: diffVM.allFrames)
        }
        // Inspector card anchored 0.5m in front of user
        .overlay(alignment: .bottom) {
            if let frame = inspectorVM.inspectedFrame {
                InspectorCardView(frame: frame)
                    .padding(.bottom, 40)
            }
        }
        .task {
            let stream = DiffEngineBridge.makeStream(left: left, right: right)
            await diffVM.bind(stream: stream)
        }
        // Gaze-select: tap a spine node to inspect that frame
        .gesture(
            TapGesture().targetedToAnyEntity().onEnded { value in
                let name = value.entity.name
                if name.hasPrefix("spine_"),
                   let indexStr = name.split(separator: "_").last,
                   let index = UInt64(indexStr) {
                    timelineVM.select(index)
                    let frame = diffVM.allFrames.first { $0.frame_index == index }
                    inspectorVM.inspect(frame)
                }
            }
        )
    }
}

// MARK: - Inspector Card (anchored near user)

private struct InspectorCardView: View {
    let frame: DiffFrame

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Frame \(frame.frame_index)")
                .font(.headline).foregroundColor(.white)
            Divider()
            hashRow("Live event",   frame.left_event_hash,      ok: !frame.event_diverged)
            hashRow("Replay event", frame.right_event_hash,     ok: !frame.event_diverged)
            hashRow("Live proj",    frame.left_projection_hash, ok: !frame.projection_diverged)
            hashRow("Replay proj",  frame.right_projection_hash, ok: !frame.projection_diverged)
        }
        .padding(14)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .frame(maxWidth: 340)
    }

    private func hashRow(_ label: String, _ hash: String, ok: Bool) -> some View {
        HStack(spacing: 8) {
            Circle()
                .fill(ok ? Color.green : Color.red)
                .frame(width: 8, height: 8)
            Text(label)
                .foregroundColor(.gray)
                .frame(width: 90, alignment: .leading)
            Text(String(hash.prefix(16)) + "…")
                .font(.system(.caption2, design: .monospaced))
                .foregroundColor(.white.opacity(0.8))
        }
        .font(.caption)
    }
}
#endif  // os(visionOS) || os(iOS)
#endif  // canImport(RealityKit)
