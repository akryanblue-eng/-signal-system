import SwiftUI

/// "Git blame for reality timelines."
/// Shows the exact frame where divergence started and how it propagated.
struct ForkTraceView: View {
    let frames: [DiffFrame]
    let forkPoint: ForkPoint?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 4) {
                header
                Divider().background(Color.gray.opacity(0.3))
                if let fork = forkPoint {
                    forkBadge(fork)
                    Divider().background(Color.gray.opacity(0.3))
                    traceRows(aroundFork: fork)
                } else {
                    Text("No divergence detected — traces are identical.")
                        .foregroundColor(.green)
                        .font(.caption)
                        .padding(.top, 4)
                }
            }
            .padding(12)
        }
        .background(Color.black.opacity(0.7))
    }

    // MARK: Sub-views

    private var header: some View {
        Text("Fork Trace")
            .font(.headline)
            .foregroundColor(.white)
    }

    private func forkBadge(_ fork: ForkPoint) -> some View {
        HStack(spacing: 8) {
            Text("Frame \(fork.frame_index)")
                .font(.system(.caption, design: .monospaced).bold())
                .foregroundColor(.white)
            Text(fork.type.rawValue.uppercased())
                .font(.system(size: 10, weight: .bold))
                .padding(.horizontal, 6).padding(.vertical, 2)
                .background(badgeColor(fork.type))
                .foregroundColor(.black)
                .clipShape(Capsule())
            Text("FIRST DIVERGENCE")
                .font(.caption2)
                .foregroundColor(.gray)
        }
        .padding(.vertical, 4)
    }

    private func traceRows(aroundFork fork: ForkPoint) -> some View {
        let forkIdx = Int(fork.frame_index)
        let windowStart = max(0, forkIdx - 3)
        let windowEnd = min(frames.count - 1, forkIdx + 6)
        let window = Array(frames[windowStart...windowEnd])

        return VStack(alignment: .leading, spacing: 2) {
            ForEach(window) { frame in
                traceRow(frame, isFork: frame.frame_index == fork.frame_index)
            }
        }
    }

    private func traceRow(_ frame: DiffFrame, isFork: Bool) -> some View {
        HStack(spacing: 8) {
            // Frame index
            Text(String(format: "%5d", frame.frame_index))
                .font(.system(.caption2, design: .monospaced))
                .foregroundColor(isFork ? .white : .gray)
                .frame(width: 40, alignment: .trailing)

            // Status indicator
            Circle()
                .fill(rowDotColor(frame))
                .frame(width: 7, height: 7)

            // Event hash delta
            Text(frame.event_diverged ? "event ≠" : "event ✓")
                .font(.system(.caption2, design: .monospaced))
                .foregroundColor(frame.event_diverged ? .red : Color(white: 0.4))
                .frame(width: 60, alignment: .leading)

            // Projection hash delta
            Text(frame.projection_diverged ? "proj ≠" : "proj ✓")
                .font(.system(.caption2, design: .monospaced))
                .foregroundColor(frame.projection_diverged ? .orange : Color(white: 0.4))

            if isFork {
                Text("← fork")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundColor(.white)
            }
        }
        .padding(.vertical, 1)
        .background(isFork ? Color.white.opacity(0.06) : Color.clear)
    }

    // MARK: Helpers

    private func rowDotColor(_ frame: DiffFrame) -> Color {
        if frame.event_diverged && frame.projection_diverged { return .red }
        if frame.event_diverged { return Color(red: 1, green: 0.6, blue: 0) }
        if frame.projection_diverged { return .orange }
        return Color(white: 0.3)
    }

    private func badgeColor(_ type: ForkType) -> Color {
        switch type {
        case .eventFork: return Color(red: 1, green: 0.6, blue: 0)
        case .projectionFork: return .orange
        case .cascadingDrift: return .red
        }
    }
}
