// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SpatialReplayMode",
    platforms: [
        .macOS(.v14),
        .iOS(.v17),
        .visionOS(.v1)
    ],
    products: [
        .library(name: "SpatialReplayCore",     targets: ["SpatialReplayCore"]),
        .library(name: "SpatialReplayVision",   targets: ["SpatialReplayVision"]),
        .library(name: "SpatialReplayDebugger", targets: ["SpatialReplayDebugger"]),
        .library(name: "SpatialReplayDiff",     targets: ["SpatialReplayDiff"])
    ],
    // No external dependencies — CryptoKit is bundled on iOS 13+ / visionOS 1+
    targets: [
        // Truth engine — no IO, no UI, no platform APIs beyond CryptoKit
        .target(name: "SpatialReplayCore"),
        // Adapter boundary — VisionPro gaze → Core event stream
        .target(
            name: "SpatialReplayVision",
            dependencies: ["SpatialReplayCore"]
        ),
        // 4-panel causality console
        .target(
            name: "SpatialReplayDebugger",
            dependencies: ["SpatialReplayCore"]
        ),
        // Causal comparison engine + diff UI
        .target(
            name: "SpatialReplayDiff",
            dependencies: ["SpatialReplayDebugger"]
        ),
        // Golden truth tests — Core only, no UI or Vision deps
        .testTarget(
            name: "SpatialReplayCoreTests",
            dependencies: ["SpatialReplayCore"]
        ),
        .testTarget(
            name: "SpatialReplayDiffTests",
            dependencies: ["SpatialReplayDiff"]
        )
    ]
)
