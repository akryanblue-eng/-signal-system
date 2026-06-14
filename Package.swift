// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SpatialVM",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "SpatialVM", targets: ["SpatialVM"]),
    ],
    targets: [
        .target(
            name: "SpatialVM",
            path: "Sources/SpatialVM"
        ),
        .testTarget(
            name: "SpatialVMTests",
            dependencies: ["SpatialVM"],
            path: "Tests/SpatialVMTests"
        ),
    ]
)
