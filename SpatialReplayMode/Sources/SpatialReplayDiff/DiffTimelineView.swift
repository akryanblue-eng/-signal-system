import SwiftUI

/// Shared timeline strip across both traces.
/// Color encodes divergence severity — this is the causal ECG.
struct DiffTimelineView: View {
    let frames: [DiffFrame]
    let forkPoint: ForkPoint?
    @Binding var selectedFrame: UInt64

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 1) {
                ForEach(frames) { frame in
                    let isSelected = frame.frame_index == selectedFrame
                    let isFork = frame.frame_index == forkPoint?.frame_index

                    Rectangle()
                        .fill(color(for: frame))
                        .frame(width: isSelected ? 10 : 6, height: 48)
                        .overlay(
                            isFork
                                ? Rectangle().stroke(Color.white, lineWidth: 1.5)
                                : nil
                        )
                        .onTapGesture { selectedFrame = frame.frame_index }
                }
            }
            .padding(.horizontal, 8)
        }
        .background(Color(white: 0.06))
    }

    private func color(for frame: DiffFrame) -> Color {
        if frame.event_diverged && frame.projection_diverged { return .red }
        if frame.event_diverged { return Color(red: 1, green: 0.6, blue: 0) }   // amber
        if frame.projection_diverged { return .orange }
        return Color(white: 0.2)    // clean — dark but visible
    }
}
