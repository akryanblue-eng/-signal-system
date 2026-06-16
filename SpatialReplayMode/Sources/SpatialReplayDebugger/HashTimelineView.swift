import SwiftUI

struct HashTimelineView: View {
    let snapshots: [DebugSnapshot]
    @Binding var selectedFrame: UInt64

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 2) {
                ForEach(snapshots) { snap in
                    let isSelected = snap.frame_index == selectedFrame
                    Rectangle()
                        .fill(color(for: snap))
                        .frame(width: isSelected ? 10 : 6, height: 40)
                        .overlay(
                            isSelected
                                ? RoundedRectangle(cornerRadius: 1)
                                    .stroke(Color.white, lineWidth: 1)
                                : nil
                        )
                        .onTapGesture { selectedFrame = snap.frame_index }
                }
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
        }
        .background(Color.black.opacity(0.2))
    }

    private func color(for snap: DebugSnapshot) -> Color {
        if !snap.is_chain_valid { return .red }
        if !snap.is_projection_match { return .orange }
        return .green
    }
}
