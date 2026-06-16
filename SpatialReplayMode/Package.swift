// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SpatialReplayMode",
    platforms: [
        .iOS(.v17),
        .visionOS(.v1)
    ],
    products: [
        .library(
            name: "SpatialReplayCore",
            targets: ["SpatialReplayCore"]
        ),
        .library(
            name: "SpatialReplayVision",
            targets: ["SpatialReplayVision"]
        ),
        .library(
            name: "SpatialReplayDebugger",
            targets: ["SpatialReplayDebugger"]
        )
    ],
    dependencies: [
        .package(url: "https://github.com/krzyzanowskim/CryptoSwift", from: "1.8.0")
    ],
    targets: [
        .target(
            name: "SpatialReplayCore",
            dependencies: ["CryptoSwift"]
        ),
        .target(
            name: "SpatialReplayVision",
            dependencies: ["SpatialReplayCore"]
        ),
        .target(
            name: "SpatialReplayDebugger",
            dependencies: ["SpatialReplayCore"],
            swiftSettings: [.enableExperimentalFeature("StrictConcurrency")]
        ),
        .testTarget(
            name: "SpatialReplayCoreTests",
            dependencies: ["SpatialReplayCore"]
        )
    ]
)
