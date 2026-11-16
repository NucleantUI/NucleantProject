# nucleant.toml Reference

`nucleant.toml` is the only file `nucleant` reads settings from. `nucleant init` writes it with every key commented, as in the examples below.

!!! info "pyproject.toml is uv's"
    `pyproject.toml` is only there so uv can track the `nucleant` dev tool. Later, the same keys will be accepted as `[tool.nucleant]` in `pyproject.toml`. The root table of `nucleant.toml` is what `[tool.nucleant]` will be.

!!! info "Packages go in Package.swift"
    `nucleant.toml` lists no Swift packages. NucleantUI and every other dependency are declared in the app's own [Package.swift](package-swift.md). `[swift]` here only says which part of that package the platforms start. Old keys that listed packages (a `[nucleantui]` table, package lists under `[swift]`) are rejected with an error that says to move them.

---

## Root

```toml
app_name = "MyApp"
bootstrap = "nucleantui"
# command_plugins = ["my_package.nucleant_plugin"]
```

| Key | Default | Description |
|---|---|---|
| `app_name` | directory name | Display name, `PRODUCT_NAME`, the Xcode target's name, and the root of the derived Swift names |
| `bootstrap` | `"nucleantui"` | The project generator from [nucleant-bootstraps](https://github.com/NucleantUI/nucleant-bootstraps). Only `nucleantui` exists for now |
| `command_plugins` | `[]` | Python modules that add `nucleant` subcommands (see [Command plugins](#command-plugins)) |

---

## `[toolchain]`

```toml
[toolchain]
swift = "6.3.3"
swiftly = true
# android_sdk = "swift-6.3.3-RELEASE_android"
# wasm_sdk = "swift-6.3.3-RELEASE_wasm"
```

| Key | Default | Description |
|---|---|---|
| `swift` | `"6.3.3"` | The Swift toolchain version, installed and selected with swiftly |
| `swiftly` | `true` | `false`: use `swift` from PATH, which must be this exact version |
| `android_sdk` | `swift-<swift>-RELEASE_android` | Android Swift SDK id to build with |
| `wasm_sdk` | `swift-<swift>-RELEASE_wasm` | wasm Swift SDK id to build with |

See [Toolchain](../getting-started/toolchain.md).

---

## `[swift]`

```toml
[swift]
target = "MyApp"     # the app's target in Package.swift (a library under ANDROID_BUILD)
entry = "MyAppApp"   # the public NucleantApp type the Android Activity starts
# package = "."
# android_package = "project_dist/gradle/swift"

[swift.env]
# NUCLEANT_ANDROID_USE_AHARDWAREBUFFER = "1"
```

| Key | Default | Description |
|---|---|---|
| `target` | `app_name` as a Swift identifier | The app's target in `Package.swift`. `swift run` runs it, the Android package links it, the Xcode project compiles its sources |
| `entry` | — | The `NucleantApp` type the Android Activity constructs. It must be `public` with a `public init()` |
| `package` | `"."` | Where the app's `Package.swift` is, relative to `nucleant.toml` |
| `android_package` | `"project_dist/gradle/swift"` | Where the generated Android Swift package goes |
| `[swift.env]` | `{}` | Environment variables for **every** Swift build of the app: `swift run`, the Gradle `swift build`, and the `dump-package` the Xcode generator runs |

`[swift.env]` is how a package's build switches are turned on. `Package.swift` files can only read the environment, so a switch set here applies to the whole graph. Examples:

| Variable | Read by | Effect |
|---|---|---|
| `NUCLEANT_ANDROID_USE_AHARDWAREBUFFER = "1"` | NucleantUI | Emulator only: the emulator's virtual GPU has no `VK_KHR_external_memory_fd` |
| `NUCLEANT_VLC_ANDROID_SOFTWARE = "1"` | NucleantVLC | Android's software video path (see the [NucleantVLC showcase](../showcases/nucleant-vlc.md)) |
| `NUCLEANT_LOCAL_DEV = "1"` | most Nucleant packages | Take sibling checkouts (`../NucleantUI`, …) instead of releases |

---

## `[android]`

Its presence enables Android. `package_name` is required.

```toml
[android]
package_name = "org.example.myapp"
# version_name = "0.1"
version_code = 1

archs = ["arm64-v8a"]   # "x86_64" for emulators on Intel hosts
gradle_dependencies = []
gradle_plugins = []
permissions = []

api = 36
min_api = 28
sdk = "36"
ndk = "28c"
ndk_api = 28

global_tools = true
```

### Identity and versions

| Key | Default | Description |
|---|---|---|
| `package_name` | **required** | Application id and Gradle namespace |
| `version_name` | `"1.0"` | `versionName`: change it for each release |
| `version_code` | `1` | `versionCode`: increase it for every upload of the same `version_name` |

### Build

| Key | Default | Description |
|---|---|---|
| `archs` | `["arm64-v8a"]` | ABIs to build: `arm64-v8a`, `x86_64`. Each one is a full Swift cross-compile. `run` checks the device's ABI before building |
| `api` | `36` | `compileSdk` / `targetSdk` |
| `min_api` | `28` | `minSdk`. **28 is the floor**: the Swift Android SDK has no triples below `android28` |
| `sdk` | `"36"` | SDK platform to install |
| `ndk` | `"28c"` | NDK release (`28c`, `27d`, … or a full version like `28.2.13676358`) |
| `ndk_api` | `28` | NDK API level |
| `universal_apk` | `true` | One APK for all ABIs, or one per ABI. Read from the config, but the nucleantui bootstrap doesn't act on it yet |

### Gradle and the manifest

| Key | Default | Description |
|---|---|---|
| `gradle_dependencies` | `[]` | Extra `implementation(...)` coordinates, e.g. `"com.onesignal:OneSignal:[5.6.1, 5.9.99]"` |
| `gradle_plugins` | `[]` | Plugin lines for the root build, e.g. `'id("com.google.gms.google-services") version "4.4.2" apply false'` |
| `permissions` | `[]` | `android.permission.*` names to declare, e.g. `"INTERNET"`, `"BLUETOOTH_SCAN"`. An empty list declares `INTERNET`. **Once you list any permission, list `INTERNET` too if the app needs the network** |
| `[android.meta_data]` | `{}` | `<meta-data>` entries inside `<application>` |
| `include_files` | `[]` | `[destination, source, ...]` entries. The sources (globs allowed) are copied into `project_dist/<destination>`, e.g. `["gradle/app", "./google-services.json"]` |

### Launcher and splash

| Key | Description |
|---|---|
| `icon` | Launcher icon, a PNG relative to `nucleant.toml` |
| `presplash` | Splash image (png, jpg, gif) |
| `presplash_color` | Splash background, default `"#FFFFFF"` |
| `presplash_lottie` | Lottie JSON splash animation |

### Tools

| Key | Default | Description |
|---|---|---|
| `global_tools` | `false` (`true` in the template) | `true`: the managed SDK/NDK in `~/.nucleant`, shared by every project. `false`: in `./.nucleant` |
| `global_tools_path` | `~/.nucleant` | Root for the shared tools |
| `sdk_path` / `ndk_path` / `java_path` | — | Use these instead of a managed install (the environment still wins: `ANDROID_HOME`, `ANDROID_NDK_ROOT`, `JAVA_HOME`) |

### Hooks

| Key | When |
|---|---|
| `pre_build` | Before the Gradle project is generated, from the `nucleant` command. Gets `NUCLEANT_PROJECT_DIR` |
| `post_build` | Inside the Gradle build, as the `nucleantPostBuild` task. It runs after the app's content is staged and before AGP packages it, the last point where that content can change. Gets `APP_MAIN` (the app module's `src/main`) |

A `.py` hook runs with `uv run`. Any other file is executed directly. Paths are relative to the project.

!!! note "`[[android.services]]`"
    Background services are part of the Python layer (they start Python entry points). They are parsed, but ignored with a warning while the Python layer is off.

---

## `[ios]` and `[macos]`

Each table's presence enables that platform in the Xcode project. `bundle_id` is required.

```toml
[ios]
bundle_id = "org.example.myapp"
minimum_deployment = "17.0"
version = "1.0"
build_number = "1"
info_plist = {}
entitlements = {}
# developer_team = "ABC123XYZ"

[macos]
bundle_id = "org.example.myapp"
minimum_deployment = "14.0"
version = "1.0"
build_number = "1"
info_plist = {}
entitlements = {}
```

| Key | Default | Description |
|---|---|---|
| `bundle_id` | **required** | `PRODUCT_BUNDLE_IDENTIFIER`. A different macOS id becomes a `[sdk=macosx*]` override |
| `minimum_deployment` | iOS `17.0`, macOS `14.0` | Deployment target. These are the floors: the Swift graph uses Observation |
| `version` | `"1.0"` | `MARKETING_VERSION` (`CFBundleShortVersionString`) |
| `build_number` | `"1"` | `CURRENT_PROJECT_VERSION` (`CFBundleVersion`) |
| `info_plist` | `{}` | Extra Info.plist keys, merged over nucleant's own. macOS keys win over iOS keys |
| `entitlements` | `{}` | Entitlements, written to `Support/<target>.entitlements` |
| `developer_team` | — | `DEVELOPMENT_TEAM`. Needed for a real iOS device and for the App Store |
| `pre_build` | — | Hook run before the Xcode project is generated |
| `post_build` | — | Hook added to the Xcode target as a post-build script phase |

`version` and `build_number` come from `[ios]` when it exists, else `[macos]`. For an App Store archive, `--app-version` and `--build-number` override them (see [iOS & macOS](../platforms/apple.md#app-store)).

For Info.plist usage strings (camera, Bluetooth, …), put the keys in `info_plist`:

```toml
[ios]
info_plist = { NSBluetoothAlwaysUsageDescription = "Finds the devices around you." }
```

---

## `[linux]` and `[wasm]`

```toml
[linux]

# [wasm]
```

| Table | Effect |
|---|---|
| `[linux]` | Marks Linux as a target. `nucleant linux run` prints a note without it, then runs anyway |
| `[wasm]` | `nucleant toolchain install` also fetches the wasm Swift SDK |

---

## `[python]`

```toml
[python]
enabled = false
```

ksproject's Python handling (site-packages per ABI and slice, CPython for Android, Python.xcframework, `.python-version` pins) is carried over in `nucleant.python`, but this version of nucleant ships with it switched off. `enabled = true` prints a note and builds without Python. It will come back as a layer on top of NucleantUI.

---

## `.env`

`nucleant` loads `.env` from the project root at startup. Real environment variables win. `init` writes one with the signing placeholders:

```bash title=".env"
# KEYSTORE=""
# KEYALIAS=""
# STOREPASS=""
# KEYPASS="defaults_to_storepass"
# ASC_KEY_ID=""
# ASC_ISSUER_ID=""
# ASC_KEY_PATH=""
```

`NUCLEANT_DEBUG=1` shows the full traceback for errors that are normally printed as one `error:` line.

---

## Command plugins

A command plugin is a Python module, importable in the project's environment, that exposes `plugin` with a `register(subparsers)` method:

```python title="my_package/nucleant_plugin.py"
import argparse


class Plugin:
    def register(self, subparsers: argparse._SubParsersAction) -> None:
        p = subparsers.add_parser("hello", help="Say hello")
        p.set_defaults(func=lambda args: print("hello") or 0)


plugin = Plugin()
```

```toml title="nucleant.toml"
command_plugins = ["my_package.nucleant_plugin"]
```

```bash
uv run nucleant hello
```
