// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "PIIGuardMac",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "PIIGuardMac", path: "Sources/PIIGuardMac")
    ]
)
