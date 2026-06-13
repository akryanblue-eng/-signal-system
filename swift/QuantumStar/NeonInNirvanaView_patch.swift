// PATCH for NeonInNirvanaView.swift (Node A → Node B transition)
//
// 1. Change the struct signature:
//
//    BEFORE:
//    struct NeonInNirvanaView: View {
//        @State private var travelerState = TravelerState()
//
//    AFTER:
//    struct NeonInNirvanaView: View {
//        @Binding var travelerState: TravelerState
//        @EnvironmentObject var navigator: NodeNavigator
//
// 2. In your tap handler where the Portal entity is detected, add navigation:
//
//    guard tapped.name == "Portal" else { return }
//    navigator.navigateTo(.godlyDNA)
//
// No other changes needed. NodeNavigator is injected via .environmentObject
// from QuantumStarRootView and requires no explicit init parameter.
