# macOS

A Mac runs a NucleantUI app in two ways, from the same sources and the same `@main`:

```bash
uv run nucleant apple macos run            # swift run: the executable
uv run nucleant apple macos run --xcode    # the .app, through the Xcode project
```

| | `swift run` | The `.app` |
|---|---|---|
| Built by | SwiftPM, from the app's `Package.swift` | Xcode, from the [generated project](apple.md#the-generated-project) |
| Needs | The [pinned Swift](../getting-started/toolchain.md) | Xcode and a `[macos]` table |
| Info.plist and entitlements | None | nucleant's, plus `[macos] info_plist` and `entitlements` |
| Signing | — | Signed to run locally. `developer_team` for the App Store |
| Resources | `Bundle.module` | The app bundle (`Bundle.module` is `Bundle.main`) |
| Build plugins on the app target | Run on every build | Don't run: [precompile](../guides/pyshader.md#ios-and-the-macos-app-precompile) |
| App arguments | After `--` | — |
| [Window phases](#the-windows-phase) | Yes | Yes, the same |

Use `swift run` from day to day. Switch to the `.app` when the app needs something only a bundle has: Info.plist keys such as usage strings, entitlements, its own signature, or the Mac App Store.

---

## `swift run`

`apple macos run` is `swift run -c <debug|release> <[swift] target>` with the pinned toolchain and `[swift.env]` set. Arguments after `--` go to the app:

```bash
uv run nucleant apple macos run release -- ~/Movies/clip.mkv
```

It doesn't need a `[macos]` table. The command, and the same thing on Linux, are on [Desktop: swift run](desktop.md).

---

## The `.app`

A `[macos]` table adds macOS to the Xcode project:

```toml title="nucleant.toml"
[macos]
bundle_id = "org.example.myapp"
minimum_deployment = "14.0"
info_plist = {}
entitlements = {}
# developer_team = "ABC123XYZ"
```

`run --xcode` builds the `.app` for this Mac's architecture. It then runs the executable inside the bundle (`<app_name>.app/Contents/MacOS/`) directly, rather than through `open`, so the app's output stays in your terminal. Every key of the table is in the [`[ios]` and `[macos]` reference](../configuration/nucleant-toml.md#ios-and-macos).

### One target for iOS and macOS

The Xcode project has one multi-platform app target. With both `[ios]` and `[macos]` it builds for both, and the two tables share it:

- **Info.plist**: nucleant's keys, then `[ios] info_plist`, then `[macos] info_plist`. On a key set in both, macOS wins. For macOS, nucleant writes `LSMinimumSystemVersion` (the deployment target) and `NSHighResolutionCapable`.
- **Entitlements**: `[ios] entitlements` and `[macos] entitlements` go into the one `Support/<target>.entitlements`. Here too, macOS wins.
- **Bundle id**: from `[ios]`, else `[macos]`. A different `[macos] bundle_id` becomes a `PRODUCT_BUNDLE_IDENTIFIER[sdk=macosx*]` override.
- **Version and build number**: from `[ios]`, else `[macos]`.
- **Team**: `developer_team` from `[ios]`, else `[macos]`.

### Signing

Signing is automatic. Without a team, the `.app` is signed to run locally, which is all `run --xcode` needs on your own Mac. An App Store archive needs `developer_team`.

### The Mac App Store

A Mac App Store app has to run in the App Sandbox. The sandbox is an entitlement, and so is every door out of it. For instance, a player that streams over the network needs `network.client`:

```toml title="nucleant.toml"
[macos]
bundle_id = "org.example.myapp"
developer_team = "ABC123XYZ"
entitlements = { "com.apple.security.app-sandbox" = true, "com.apple.security.network.client" = true }
```

Then archive it and upload it:

```bash
uv run nucleant apple macos archive release --upload
uv run nucleant apple macos create-action     # or: on every pushed tag, from GitHub Actions
```

The archive, the App Store Connect key and the workflow's secrets are on [iOS & macOS: App Store](apple.md#app-store).

---

## The window's phase

On macOS a window is in one of three phases, which its views read as `@Environment(\.scenePhase)` (from NucleantUI 0.3.2):

| Phase | When |
|---|---|
| `.active` | Neither of the two below. A window behind other windows, or with another app in front, is still active |
| `.inactive` | Minimized into the Dock |
| `.background` | The app is hidden (++cmd+h++) |

The phases are the same under `swift run` and in the `.app`, because both run the same AppKit code. When the phase changes, NucleantUI runs one frame at once. That way `onChange(of: scenePhase)` runs straight away, even though macOS stops a window's display link while it is minimized or the app is hidden. In the background the window draws nothing until it comes back.

How to act on the phase, and what it does on the other platforms: [App Lifecycle (scenePhase)](../guides/scene-phase.md).
