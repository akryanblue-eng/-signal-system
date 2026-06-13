// PATCH for GodlyDNAView.swift (Node B → Node C transition)
//
// 1. Add to the struct properties:
//
//    @EnvironmentObject var navigator: NodeNavigator
//
// 2. In handleTap (or your portal switch), navigate immediately after emitting:
//
//    case "Portal_Ascension":
//        emit(.onChoiceAscension)
//        navigator.navigateTo(.skyHigh)
//
//    case "Portal_Creation":
//        emit(.onChoiceCreation)
//        navigator.navigateTo(.skyHigh)
//
// The reducer locks geneChoice on first write, so double-taps are safe —
// navigation fires again but state is already committed and unchanged.
