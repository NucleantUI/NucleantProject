# Showcase: NucleantVLC

[NucleantVLC](https://github.com/NucleantUI/NucleantVLC) is libvlc as a NucleantUI view: a Swift wrapper for libvlc 3 and `VlcView`, which shows a player's video. Its repository has a demo, **NucleantVLCDemo**, a media player with a transport bar, a playlist, and track and subtitle menus.

Making a nucleant app out of it means writing the demo's files into a nucleant project. The demo's sources don't change, apart from two small Android details. This page walks through that, with Android as the target.

---

## 1. A project

```bash
uv init --bare vlc-player && cd vlc-player
uv add --dev git+https://github.com/NucleantUI/NucleantProject
uv run nucleant init
```

`vlc-player` gives the target `VlcPlayer`. The names below follow from it.

## 2. The demo's files

Copy `Sources/NucleantVLCDemo/` from NucleantVLC's `main` into the app's target, and delete the starter app. A target can have only one `@main`.

```bash
git clone https://github.com/NucleantUI/NucleantVLC ../NucleantVLC
cp -R ../NucleantVLC/Sources/NucleantVLCDemo/. Sources/VlcPlayer/
rm Sources/VlcPlayer/VlcPlayerApp.swift
```

```
Sources/VlcPlayer/
├── NucleantVLCDemo.swift   # @main: the window
├── Player.swift            # the VlcRemote model
├── PlayerViews.swift       # the video, transport bar, playlist
├── Icons.swift             # the SVG icons
├── Verifier.swift          # NUCLEANT_VLC_DEMO_VERIFY self-check
└── Resources/Icons/        # Material Icons SVGs (Apache 2.0) + LICENSE
```

## 3. Two Android details

**The entry is public.** On Android the target is a library, and the Activity constructs the app from outside it:

```swift title="Sources/VlcPlayer/NucleantVLCDemo.swift" hl_lines="2 3 5"
@main
public struct NucleantVLCDemo: NucleantApp {
    public init() {}

    public var body: some Scene {
        WindowGroup("NucleantVLC Player") {
            PlayerScreen()
        }
        .defaultSize(width: 1200, height: 720)
    }
}
```

**The icons' bundle has the app's name.** The demo loads its icons by URL from the target's resources (`.process("Resources/Icons")`). On Android, `Bundle.module` can't find resources (see [Resources](../configuration/package-swift.md#resources)), so `Icons.swift` already has an `#if os(Android)` branch that looks under `NUCLEANT_APP_PATH`. That branch names the demo's own bundle, `NucleantVLC_NucleantVLCDemo.resources`. In the app the bundle is `<Package>_<Target>`:

```swift title="Sources/VlcPlayer/Icons.swift" hl_lines="9"
    /// `name`.svg in the target's resources (`.process("Resources/Icons")`).
    private static func url(of name: String) -> URL? {
        #if os(Android)
        // Not `Bundle.module`: on Android its accessor looks next to the
        // executable (the zygote's) and fatalErrors. nucleant unpacks the
        // resource bundles beside the app's files instead, at
        // NUCLEANT_APP_PATH — as NucleantUI's own FontRegistry finds them.
        guard let root = ProcessInfo.processInfo.environment["NUCLEANT_APP_PATH"] else { return nil }
        return URL(fileURLWithPath: "\(root)/VlcPlayer_VlcPlayer.resources/\(name).svg")
        #else
        return Bundle.module.url(forResource: name, withExtension: "svg")
        #endif
    }
```

That one string is the only change in `Icons.swift`. Every other platform goes through `Bundle.module`, which nucleant maps to the app bundle in the Xcode project.

## 4. Package.swift

Add NucleantVLC and the icons to the starter manifest:

```swift title="Package.swift" hl_lines="11 16 21 25 27"
// swift-tools-version: 6.2
import Foundation
import PackageDescription

let environment = ProcessInfo.processInfo.environment
let isAndroid = environment["ANDROID_BUILD"] != nil
    || environment["SWIFT_ANDROID_HOME"] != nil

let dependencies: [Package.Dependency] = [
    .package(url: "https://github.com/NucleantUI/NucleantUI.git", .upToNextMinor(from: "0.3.2")),
    .package(url: "https://github.com/NucleantUI/NucleantVLC", .upToNextMinor(from: "0.0.3")),
]

let appDependencies: [Target.Dependency] = [
    .product(name: "NucleantUI", package: "NucleantUI"),
    .product(name: "NucleantVLC", package: "NucleantVLC"),
]

/// The player's icons: Material Icons SVGs (Apache 2.0), loaded by URL
/// (Icons.swift), as the demo's own target declares them.
let appResources: [Resource] = [.process("Resources/Icons")]

let app: Target = isAndroid
    ? .target(name: "VlcPlayer", dependencies: appDependencies, path: "Sources/VlcPlayer",
              resources: appResources)
    : .executableTarget(name: "VlcPlayer", dependencies: appDependencies, path: "Sources/VlcPlayer",
                        resources: appResources)

let product: Product = isAndroid
    ? .library(name: "VlcPlayer", targets: ["VlcPlayer"])
    : .executable(name: "VlcPlayer", targets: ["VlcPlayer"])

let package = Package(
    name: "VlcPlayer",
    platforms: [.macOS("14.0"), .iOS("17.0")],
    products: [product],
    dependencies: dependencies,
    targets: [app]
)
```

To work on NucleantVLC itself at the same time, take it from the checkout instead: `.package(path: "../NucleantVLC")`.

libvlc comes prebuilt from NucleantVLC's release assets, and SwiftPM downloads the archive for the platform it builds for. On Android that is `LibVLC-android-<abi>.artifactbundle.zip`, one per ABI. Each one is a `libvlc.so` with every plugin built in. It needs `libc++_shared.so`, which every Swift Android app ships already.

## 5. nucleant.toml

Point `[swift] entry` at the demo's app type, and turn on Android's video path:

```toml title="nucleant.toml" hl_lines="3 6"
[swift]
target = "VlcPlayer"
entry = "NucleantVLCDemo"

[swift.env]
NUCLEANT_VLC_ANDROID_SOFTWARE = "1" # NucleantVLC: the software video path (the GPU one is not written yet)
# NUCLEANT_ANDROID_USE_AHARDWAREBUFFER = "1"   # on the emulator

[android]
package_name = "org.example.vlc_player"
archs = ["arm64-v8a"]   # "x86_64" for an emulator on an Intel Mac
```

`NUCLEANT_VLC_ANDROID_SOFTWARE` is read by NucleantVLC's own `Package.swift`. An Android build has to ask for the software path explicitly, because the GPU path (frames in AHardwareBuffers) isn't written yet. `[swift.env]` is how an app sets a dependency's switch: the variable reaches every Swift build, so NucleantVLC's manifest sees it too.

The default `permissions = []` declares `INTERNET`, which the demo needs. With nothing on the command line, it streams Blender's open movies from `download.blender.org`.

## 6. Run it

```bash
uv run nucleant android run --logcat
```

On the desktop, the same project is `swift run`, with files, folders or URLs to play:

```bash
uv run nucleant apple macos run -- ~/Movies/clip.mkv
```

The demo doesn't look at the window's phase. To pause the player when the app leaves the foreground and play again on return, see [App Lifecycle: pause the player](../guides/scene-phase.md#example-pause-the-player).

On iOS, `uv run nucleant apple sim run` builds the same sources through the Xcode project. In the iOS Simulator the video plays, but the controls drawn by Skia don't show, because of a Simulator GPU limitation ([details](../platforms/apple.md#simulator-and-devices)). A real device doesn't have it.

---

## What carried over

| From the demo | In the app |
|---|---|
| `Sources/NucleantVLCDemo/*` | `Sources/VlcPlayer/*`, unchanged apart from `public` on the entry and the bundle name in `Icons.swift` |
| The demo target's `resources: [.process("Resources/Icons")]` | The same declaration on the app target |
| Its dependencies (`NucleantVLC`, `NucleantUI`) | The app's `Package.swift` |
| — | `[swift] entry = "NucleantVLCDemo"` and `NUCLEANT_VLC_ANDROID_SOFTWARE` |

Any NucleantUI demo moves into a nucleant project the same way: its files, its dependencies, its resources, and a public entry.
