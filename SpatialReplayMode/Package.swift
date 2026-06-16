// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SpatialReplayMode",
    platforms: [
        .iOS(.v17),
        .visionOS(.v1)
    ],
    products: [
        .library(name: "SpatialReplayCore",     targets: ["SpatialReplayCore"]),
        .library(name: "SpatialReplayVision",   targets: ["SpatialReplayVision"]),
        .library(name: "SpatialReplayDebugger", targets: ["SpatialReplayDebugger"]),
        .library(name: "SpatialReplayDiff",     targets: ["SpatialReplayDiff"])
    ],
    dependencies: [
        .package(url: "https://github.com/krzyzanowskim/CryptoSwift", from: "1.8.0")
    ],
    targets: [
        // Truth engine — no IO, no UI, no platform APIs
        .target(
            name: "SpatialReplayCore",
            dependencies: ["CryptoSwift"]
        ),
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
