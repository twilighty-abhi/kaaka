// swift-tools-version:5.9
import PackageDescription
import Foundation

// Info.plist (NSBluetoothAlwaysUsageDescription) is embedded into the binary so TCC
// doesn't kill the process on first Bluetooth access. Absolute path so it works from any cwd.
let infoPlist = URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("Info.plist").path

let package = Package(
    name: "hfp-bridge",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "hfp-bridge",
            path: "Sources/hfp-bridge",
            linkerSettings: [
                .linkedFramework("IOBluetooth"),
                .unsafeFlags(["-Xlinker", "-sectcreate", "-Xlinker", "__TEXT",
                              "-Xlinker", "__info_plist", "-Xlinker", infoPlist]),
            ]
        )
    ]
)
