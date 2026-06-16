import SwiftUI

struct DivergenceHeatmapView: View {
    let snapshots: [DebugSnapshot]

    var body: some View {
        Canvas { context, size in
            guard !snapshots.isEmpty else { return }
            let w = size.width / CGFloat(snapshots.count)

            for (i, snap) in snapshots.enumerated() {
                let x = CGFloat(i) * w
                let rect = CGRect(x: x, y: 0, width: w, height: size.height)

                let fill: Color
                if !snap.is_chain_valid && !snap.is_projection_match {
                    fill = .red
                } else if !snap.is_chain_valid {
                    fill = .red.opacity(0.6)
                } else if !snap.is_projection_match {
                    fill = .orange
                } else {
                    fill = .clear
                }

                if fill != .clear {
                    context.fill(Path(rect), with: .color(fill))
                }
            }
        }
        .background(Color(white: 0.06))
    }
}
