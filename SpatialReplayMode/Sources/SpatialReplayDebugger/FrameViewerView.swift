import SwiftUI

struct FrameViewerView: View {
    let frame: DebugSnapshot?

    var body: some View {
        ZStack {
            Color.black.opacity(0.9)

            if let frame {
                VStack(spacing: 16) {
                    Text("Frame \(frame.frame_index)")
                        .font(.title2.monospacedDigit())
                        .foregroundColor(.white)

                    Circle()
                        .fill(frame.is_projection_match ? Color.green : Color.red)
                        .frame(width: 80, height: 80)
                        .overlay(
                            Text(frame.is_projection_match ? "MATCH" : "DRIFT")
                                .font(.caption2.bold())
                                .foregroundColor(.black)
                        )

                    VStack(alignment: .leading, spacing: 4) {
                        hashLine("Event", frame.event_hash)
                        hashLine("Proj ", frame.projection_hash)
                    }
                }
            } else {
                Text("No frame selected")
                    .foregroundColor(.gray)
            }
        }
    }

    private func hashLine(_ label: String, _ hash: String) -> some View {
        HStack(spacing: 6) {
            Text(label)
                .foregroundColor(.gray)
                .font(.system(.caption, design: .monospaced))
            Text(String(hash.prefix(16)) + "…")
                .foregroundColor(.white.opacity(0.7))
                .font(.system(.caption, design: .monospaced))
        }
    }
}
