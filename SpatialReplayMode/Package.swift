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
        .library(name: "SpatialReplayCore",          targets: ["SpatialReplayCore"]),
        .library(name: "SpatialReplayVision",        targets: ["SpatialReplayVision"]),
        .library(name: "SpatialReplayDebugger",      targets: ["SpatialReplayDebugger"]),
        .library(name: "SpatialReplayDiff",          targets: ["SpatialReplayDiff"]),
        .library(name: "SpatialReplayDebuggerXR",    targets: ["SpatialReplayDebuggerXR"])
    ],
    // No external dependencies — CryptoKit is bundled on all target platforms.
    targets: [
        // ─── Truth engine (no IO, no UI, no platform APIs beyond CryptoKit) ────
        .target(name: "SpatialReplayCore"),

        // ─── Adapter boundary ────────────────────────────────────────────────────
        .target(
            name: "SpatialReplayVision",
            dependencies: ["SpatialReplayCore"]
        ),

        // ─── 2D causality console ────────────────────────────────────────────────
        .target(
            name: "SpatialReplayDebugger",
            dependencies: ["SpatialReplayCore"]
        ),

        // ─── Causal comparison engine + diff UI ──────────────────────────────────
        .target(
            name: "SpatialReplayDiff",
            dependencies: ["SpatialReplayDebugger"]
        ),

        // ─── Spatial/XR instrument (visionOS/iOS RealityKit) ─────────────────────
        // Depends on SpatialReplayDiff (which transitively includes Debugger + Core).
        .target(
            name: "SpatialReplayDebuggerXR",
            dependencies: ["SpatialReplayDiff"]
        ),

        // ─── CI test targets ─────────────────────────────────────────────────────
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
