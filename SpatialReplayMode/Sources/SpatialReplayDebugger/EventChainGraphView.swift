import SwiftUI

public struct EventChainGraphView: View {
    public let snapshots: [DebugSnapshot]

    public init(snapshots: [DebugSnapshot]) { self.snapshots = snapshots }

    public var body: some View {
        Canvas { context, size in
            guard !snapshots.isEmpty else { return }
            let spacing = size.width / CGFloat(snapshots.count)
            let centerY = size.height / 2
            let nodeSize: CGFloat = 6

            for (i, snap) in snapshots.enumerated() {
                let x = CGFloat(i) * spacing + spacing / 2

                // Edge to previous node
                if i > 0 {
                    let prevX = CGFloat(i - 1) * spacing + spacing / 2
                    var path = Path()
                    path.move(to: CGPoint(x: prevX, y: centerY))
                    path.addLine(to: CGPoint(x: x, y: centerY))
                    context.stroke(path, with: .color(.gray.opacity(0.4)), lineWidth: 1)
                }

                // Node — green = valid chain, red = broken
                let nodeRect = CGRect(
                    x: x - nodeSize / 2,
                    y: centerY - nodeSize / 2,
                    width: nodeSize,
                    height: nodeSize
                )
                context.fill(
                    Path(ellipseIn: nodeRect),
                    with: .color(snap.is_chain_valid ? .green : .red)
                )
            }
        }
        .background(Color.black.opacity(0.8))
    }
}
