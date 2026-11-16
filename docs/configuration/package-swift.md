# The App's Package.swift

The app is the Swift package at the project root. `nucleant init` writes a starter `Package.swift` once and never rewrites it. Every dependency goes there, NucleantUI included, with whatever version rules and environment switches it needs. Every platform builds the app from that one manifest.

---

## How each platform builds it

| Platform | How the package is built |
|---|---|
| **macOS / Linux** | `swift run` in the package, which runs the executable target `[swift] target` |
| **Android** | The generated `project_dist/gradle/swift` package holds only swift-java and the JNI bridge. It depends on the app's package with `.package(path: "../../..")` and links `[swift] target` as a library into `libNucleantMain.so`. Gradle runs `swift build` with `ANDROID_BUILD=1`, and that is what makes the target a library |
| **iOS / the macOS .app** | An Xcode app target can't depend on an executable, so nucleant reads the manifest instead. `swift package dump-package` evaluates it as SwiftPM would, and the Xcode project then compiles `Sources/<target>` and depends on the packages that target uses |

So anything you write in `Package.swift` (a dependency, a version rule, a switch on the environment) applies on every platform as written.

---

## The starter

```swift title="Package.swift"
// swift-tools-version: 6.2

import Foundation
import PackageDescription

let environment = ProcessInfo.processInfo.environment

/// Android is a cross-compile, and Package.swift is evaluated on the host, so
/// `#if os(Android)` here would describe the build machine. Gradle sets
/// ANDROID_BUILD (and SWIFT_ANDROID_HOME) instead; every Nucleant package
/// reads the same signal.
let isAndroid = environment["ANDROID_BUILD"] != nil
    || environment["SWIFT_ANDROID_HOME"] != nil

let dependencies: [Package.Dependency] = [
    .package(url: "https://github.com/NucleantUI/NucleantUI.git", .upToNextMinor(from: "0.3.2")),
]

let appDependencies: [Target.Dependency] = [
    .product(name: "NucleantUI", package: "NucleantUI"),
]

/// On Android the app is a library linked into the Activity's native
/// library, so its entry type (`MyAppApp`) is public. Everywhere else
/// it is the executable `swift run` starts.
let app: Target = isAndroid
    ? .target(name: "MyApp", dependencies: appDependencies, path: "Sources/MyApp")
    : .executableTarget(name: "MyApp", dependencies: appDependencies, path: "Sources/MyApp")

let product: Product = isAndroid
    ? .library(name: "MyApp", targets: ["MyApp"])
    : .executable(name: "MyApp", targets: ["MyApp"])

let package = Package(
    name: "MyApp",
    platforms: [.macOS("14.0"), .iOS("17.0")],
    products: [product],
    dependencies: dependencies,
    targets: [app]
)
```

The `platforms:` versions come from `[macos]` / `[ios] minimum_deployment` at the time `init` runs.

!!! warning "`#if os(Android)` in Package.swift describes the host"
    The manifest is evaluated by the host toolchain even when cross-compiling, so `#if os(Android)` inside `Package.swift` is never true. Read the environment instead, as above. In your **sources**, `#if os(Android)` works as usual.

---

## Adding a dependency

Add the package to `dependencies` and its product to `appDependencies`:

```swift title="Package.swift"
let dependencies: [Package.Dependency] = [
    .package(url: "https://github.com/NucleantUI/NucleantUI.git", .upToNextMinor(from: "0.3.2")),
    .package(url: "https://github.com/NucleantUI/NucleantBluetooth", branch: "main"),
]

let appDependencies: [Target.Dependency] = [
    .product(name: "NucleantUI", package: "NucleantUI"),
    .product(name: "NucleantBluetooth", package: "NucleantBluetooth"),
]
```

A local checkout works the same: `.package(path: "../NucleantBluetooth")`. The Xcode project then gets it as a local package too.

!!! note "Only the app target's own sources reach Xcode"
    The Xcode project compiles `Sources/<target>` and the **packages** the target depends on. If the app target also depends on other targets of its own package, nucleant prints a note: those aren't in the Xcode project. Move shared code into a separate package, or into the app target.

---

## Updating dependencies

Each build resolves the app's packages itself, and pins what it resolved in a `Package.resolved` of its own:

| Build | Pins in |
|---|---|
| `swift run` (macOS, Linux) | `Package.resolved`, next to `Package.swift` |
| Android | `project_dist/gradle/swift/Package.resolved` |
| iOS and the macOS `.app` | `project_dist/xcode/<app_name>.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved` |

A new release that a version rule allows, such as a new 0.1.x under `.upToNextMinor(from: "0.1.0")`, reaches a build only once that build updates. This includes the packages your packages depend on. Updating one build doesn't update the others.

- **`swift run`**: `swift package update` in the project, with the [pinned toolchain](../getting-started/toolchain.md): `swiftly run swift package update +6.3.3`.
- **Android and the Xcode project**: delete their `Package.resolved`. The next `nucleant android run` or `nucleant apple … run` resolves again. Each resolves with the environment it builds with (`ANDROID_BUILD`, `[swift.env]`), which a `swift package update` run by hand wouldn't have.

---

## Packages that bring their own Android half

Some packages need Java on Android, for example a callback class Swift can't subclass. A package ships that Java in an `Android/java` folder at its root. The Gradle build compiles the `Android/java` of **every package in the Swift graph** together with the app, taken from the same checkouts SwiftPM resolved. Adding the package to `Package.swift` is all it takes.

- **NucleantApplication** ships `org.nucleantui.NucleantActivity` and `NucleantSurfaceView` this way. They are the Activity and surface every app starts in.
- **NucleantBluetooth** ships its `android.bluetooth` callback helpers (see the [showcase](../showcases/nucleant-bluetooth.md)).

The same class in two packages stops the build, so a duplicate is caught instead of being picked silently.

Prebuilt native libraries come along the same way. A package's `Dependencies/android/<abi>/lib/*.so` is copied into the APK's `jniLibs` next to `libNucleantMain.so`.

---

## Resources

Declare resources as in any package:

```swift title="Package.swift"
let app: Target = isAndroid
    ? .target(name: "MyApp", dependencies: appDependencies, path: "Sources/MyApp",
              resources: [.process("Resources")])
    : .executableTarget(name: "MyApp", dependencies: appDependencies, path: "Sources/MyApp",
                        resources: [.process("Resources")])
```

Where they are at run time depends on the platform:

| Platform | Where `MyApp`'s resources are |
|---|---|
| macOS / Linux (`swift run`) | `Bundle.module` |
| iOS / the macOS .app | the app's own bundle. nucleant generates `Bundle.module` as `Bundle.main` for the Xcode target, so the same code builds unchanged |
| Android | **not** `Bundle.module`. SwiftPM's accessor looks next to the executable, which on Android is the zygote's, and it `fatalError`s. nucleant ships each `<Package>_<Target>.resources` directory as assets and unpacks them into the app's files directory, whose path is in `NUCLEANT_APP_PATH` (it is also the working directory) |

So on Android, look resources up by path. NucleantVLC's demo loads its icons this way (see the [showcase](../showcases/nucleant-vlc.md)):

```swift title="Sources/MyApp/Resources.swift"
import Foundation

/// `name`.`ext` in the target's resources.
func resourceURL(_ name: String, _ ext: String) -> URL? {
    #if os(Android)
    // Not `Bundle.module`: on Android its accessor looks next to the
    // executable (the zygote's) and fatalErrors. nucleant unpacks the
    // resource bundles beside the app's files instead, at NUCLEANT_APP_PATH.
    guard let root = ProcessInfo.processInfo.environment["NUCLEANT_APP_PATH"] else { return nil }
    return URL(fileURLWithPath: "\(root)/MyApp_MyApp.resources/\(name).\(ext)")  // <Package>_<Target>
    #else
    return Bundle.module.url(forResource: name, withExtension: ext)
    #endif
}
```

`.process` puts a folder's files flat at the top of the bundle, so the same file name works on every platform.

NucleantUI finds its own fonts the same way, so a package that ships resources and should work on Android needs that `#if os(Android)` branch too.

---

## Environment switches

`Package.swift` can only see the environment, so nucleant gives every Swift build the variables in `[swift.env]`:

```toml title="nucleant.toml"
[swift.env]
NUCLEANT_VLC_ANDROID_SOFTWARE = "1"
```

They are set for `swift run`, for the Gradle `swift build`, and for the `dump-package` behind the Xcode project. This is how a dependency's build-time switches get turned on from the app.
