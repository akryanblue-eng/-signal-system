import SwiftUI

struct EventInspectorView: View {
    let frame: DebugSnapshot?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Inspector")
                .font(.headline)
                .foregroundColor(.white)
            Divider()
                .background(Color.gray.opacity(0.4))

            if let frame {
                row("Frame",   "\(frame.frame_index)")
                monoRow("Event",  frame.event_hash)
                monoRow("Proj",   frame.projection_hash)
                statusRow("Chain",      frame.is_chain_valid,    ok: "OK",    fail: "BROKEN")
                statusRow("Projection", frame.is_projection_match, ok: "MATCH", fail: "DRIFT")
            } else {
                Text("Select a frame in the timeline")
                    .foregroundColor(.gray)
                    .font(.caption)
            }

            Spacer(minLength: 0)
        }
        .padding(12)
        .background(Color.black.opacity(0.6))
    }

    private func row(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label).foregroundColor(.gray).frame(width: 72, alignment: .leading)
            Text(value).foregroundColor(.white)
        }
        .font(.caption)
    }

    private func monoRow(_ label: String, _ value: String) -> some View {
        HStack(alignment: .top) {
            Text(label).foregroundColor(.gray).frame(width: 72, alignment: .leading)
            Text(value)
                .foregroundColor(.white.opacity(0.8))
                .font(.system(.caption, design: .monospaced))
                .lineLimit(2)
        }
        .font(.caption)
    }

    private func statusRow(
        _ label: String, _ ok: Bool, ok okLabel: String, fail failLabel: String
    ) -> some View {
        HStack {
            Text(label).foregroundColor(.gray).frame(width: 72, alignment: .leading)
            Text(ok ? okLabel : failLabel)
                .foregroundColor(ok ? .green : .red)
                .font(.caption.bold())
        }
    }
}
