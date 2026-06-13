import SwiftUI

@main
struct QuantumStarApp: App {
    @StateObject private var navigator = NodeNavigator()
    @State private var travelerState = TravelerState()

    var body: some Scene {
        WindowGroup {
            QuantumStarRootView(travelerState: $travelerState)
                .environmentObject(navigator)
        }
    }
}

struct QuantumStarRootView: View {
    @Binding var travelerState: TravelerState
    @EnvironmentObject var navigator: NodeNavigator

    var body: some View {
        switch navigator.currentNode {
        case .neonInNirvana:
            NeonInNirvanaView(travelerState: $travelerState)
        case .godlyDNA:
            GodlyDNAView(travelerState: $travelerState)
        case .skyHigh:
            SkyHighView(travelerState: $travelerState)
        }
    }
}
