# New Project

This guide makes a NucleantUI app from an empty folder. Installing `nucleant` and creating the project happen together. `nucleant` is a dev dependency of the project and is not installed globally.

---

## Prerequisites

You need **[uv](https://docs.astral.sh/uv/)**. Everything else (swiftly, Swift, the Swift SDKs, the Android SDK/NDK and Java) is installed by `nucleant` when a command first needs it.

=== "macOS"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

    For iOS and the macOS `.app`, install **Xcode** from the App Store as well. `swift run` and Android don't need it.

=== "Linux"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

    Linux builds the desktop app and Android. iOS and the macOS `.app` need a Mac.

---

## Create a New Project

```bash
uv init --bare MyApp && cd MyApp
uv add --dev git+https://github.com/NucleantUI/NucleantProject
uv run nucleant init
uv run nucleant toolchain install
```

1. **`uv init --bare`** writes a minimal `pyproject.toml`. Its only job is to let uv track the `nucleant` tool. `nucleant` reads no settings from it.
2. **`uv add --dev …`** adds NucleantProject as a dev dependency. The wheel is `nucleant-project`, and the command and module are `nucleant`.
3. **`nucleant init`** writes `nucleant.toml`, a starter app, its `Package.swift` and the Android templates (see below).
4. **`nucleant toolchain install`** installs swiftly, the pinned Swift (6.3.3), and a Swift SDK for every cross-compiled platform `nucleant.toml` has. See [Toolchain](toolchain.md).

### Options

| Flag | Description |
|------|-------------|
| `path` | Project directory (default: current directory) |
| `--name NAME` | The app name (default: the directory name) |

### How names are derived

`app_name` is the directory name, or `--name`. The Swift names come from it:

| `app_name` | `[swift] target` | `[swift] entry` | `package_name` / `bundle_id` |
|---|---|---|---|
| `MyApp` | `MyApp` | `MyAppApp` | `org.example.myapp` |
| `np-demo` | `NpDemo` | `NpDemoApp` | `org.example.np_demo` |
| `bluetooth-android-test` | `BluetoothAndroidTest` | `BluetoothAndroidTestApp` | `org.example.bluetooth_android_test` |

The entry type gets an `App` suffix because a `struct MyApp` inside a module named `MyApp` would make the type and the module ambiguous to Swift.

---

## What Gets Created

```
MyApp/
├── pyproject.toml            # uv's: tracks the nucleant dev tool
├── nucleant.toml             # the project's settings: what nucleant reads
├── Package.swift             # the app's Swift package: yours, never rewritten
├── .swift-version            # 6.3.3
├── AndroidManifest.tmpl.xml  # Android manifest template (editable)
├── build.tmpl.gradle.kts     # app-module Gradle template (editable)
├── .env                      # signing / App Store Connect placeholders (gitignored)
├── .gitignore                # + project_dist/ .nucleant/ .build/ .swiftpm/ .env *.jks
└── Sources/
    └── MyApp/
        └── MyAppApp.swift    # the starter NucleantUI app
```

Later, the platform commands add generated folders. All of them are gitignored and can be deleted at any time:

| Folder | Written by | What |
|---|---|---|
| `.build/` | `swift run` | SwiftPM's build of the app's package |
| `project_dist/gradle/` | `nucleant android …` | the Gradle project, with its Swift package in `project_dist/gradle/swift` |
| `project_dist/xcode/` | `nucleant apple …` | the XcodeGen spec and the generated `.xcodeproj` |
| `.nucleant/` | `nucleant android …` | a project-local Android SDK/NDK, when `global_tools = false` |

!!! note "init never overwrites"
    Every file is written only if it is missing. `Sources/<Target>` is left alone if it has any `.swift` file. `.gitignore` only gets the lines it lacks. So `nucleant init` is safe to run again, and safe to run in an existing package.

### The starter app

```swift title="Sources/MyApp/MyAppApp.swift"
import NucleantUI

/// Public, with a public init: on Android this module is a library, and the
/// Activity's native side constructs the app from outside it.
@main
public struct MyAppApp: NucleantApp {
    public init() {}

    public var body: some Scene {
        WindowGroup("MyApp") {
            ContentView()
        }
        .defaultSize(width: 480, height: 640)
    }
}

@View
struct ContentView {
    @State private var name = ""
    @State private var taps = 0

    var body: some View {
        VStack(spacing: 16) {
            Text(name.isEmpty ? "Hello from MyApp" : "Hello, \(name)!")
                .font(.system(size: 28, weight: .semibold))
            TextField("Your name", text: $name)
                .frame(maxWidth: 280)
            Text("Tapped \(taps) times")
                .foregroundStyle(.secondary)
            Button("Tap") { taps += 1 }
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
```

The entry type is `public` with a `public init()` because on Android the target is compiled as a library and the Activity's native side constructs the app from outside the module. Keep that when you replace the starter with your own app.

For everything about views, state and layout, see the **[NucleantUI documentation](https://nucleantui.github.io/NucleantUI/)**.

### The starter Package.swift

`init` writes a `Package.swift` that depends on NucleantUI and switches its one target between an executable (desktop, Xcode) and a library (Android). From then on it belongs to the project: add dependencies, resources and plugins there as in any Swift package. [The App's Package.swift](../configuration/package-swift.md) explains how each platform builds from it.

---

## Run It

```bash
uv run nucleant apple macos run                   # macOS: swift run
uv run nucleant linux run                         # Linux: swift run
uv run nucleant android run                       # first device, else boots an emulator
uv run nucleant apple sim run --name "iPhone 17"  # iOS Simulator
```

---

## Initializing Into an Existing Directory

`nucleant init` works the same in a folder that already has a `pyproject.toml`, a `Package.swift` or sources:

```bash
cd existing-app
uv init --bare        # only if there is no pyproject.toml yet
uv add --dev git+https://github.com/NucleantUI/NucleantProject
uv run nucleant init
```

- An existing **`pyproject.toml`** is kept (`uv init` is skipped).
- An existing **`Package.swift`** is kept. Check that `[swift] target` in the new `nucleant.toml` names its app target, and `[swift] entry` its `NucleantApp` type.
- Existing **sources** in `Sources/<Target>` are kept. No starter file is added.

If your app's package is not at the project root, point `[swift] package` at it (see the [nucleant.toml reference](../configuration/nucleant-toml.md#swift)).

---

## Next Steps

- **[Toolchain](toolchain.md)**: swiftly, the pinned Swift and the Swift SDKs
- **[nucleant.toml Reference](../configuration/nucleant-toml.md)**: every key
- **[The App's Package.swift](../configuration/package-swift.md)**: how each platform builds the app
- **[Android](../platforms/android.md)** and **[iOS & macOS](../platforms/apple.md)**: the native projects
