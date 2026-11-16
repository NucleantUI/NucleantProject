# iOS & macOS (Xcode)

Xcode is only needed where `swift run` can't go:

- **iOS**: devices and the Simulator.
- **macOS as a real `.app`**: signed, with entitlements, for the Mac App Store.

For those, nucleant generates an Xcode project from `nucleant.toml` and the app's `Package.swift` with [XcodeGen](https://github.com/yonaskolb/XcodeGen), then drives `xcodebuild`, `simctl` and `devicectl`. Your app's sources don't change: the same `@main …: NucleantApp` is the entry point on every platform.

```bash
uv run nucleant apple sim run                     # first available simulator
uv run nucleant apple sim run --name "iPhone 17"
uv run nucleant apple ios run                     # first connected device
uv run nucleant apple macos run --xcode           # the macOS .app, output in this terminal
uv run nucleant apple xcode open                  # generate, then open in Xcode
```

---

## Commands

| Command | What it does |
|---|---|
| `apple sim run [debug\|release]` | Build for the Simulator, boot it, install and launch with the console attached. `--name` / `--uuid` |
| `apple sim devices` | List available simulators |
| `apple ios run [debug\|release]` | Build for a device, install and launch with `devicectl`. `--name` / `--uuid` |
| `apple ios devices` | List connected iOS devices |
| `apple macos run --xcode` | Build the `.app` through Xcode and run its executable here. Without `--xcode` it is [`swift run`](desktop.md) |
| `apple {ios,macos} archive [release]` | `xcodebuild archive`. `--upload` sends it to App Store Connect |
| `apple {ios,macos} create-action` | Write a tag-triggered App Store workflow |
| `apple xcode generate [--force]` | Write `project_dist/xcode` and run XcodeGen. `--force` runs XcodeGen even when `project.yml` is unchanged |
| `apple xcode open` | Open the generated project in Xcode |

Every build runs the `[ios]`/`[macos]` `pre_build` hook, then regenerates the project.

---

## The generated project

```
project_dist/xcode/
├── project.yml              # the XcodeGen spec nucleant writes
├── <app_name>.xcodeproj
├── Support/
│   ├── Info.plist
│   ├── BundleModule.swift   # Bundle.module → Bundle.main
│   └── <target>.entitlements
├── build/                   # -derivedDataPath
└── archives/                # <app_name>-ios.xcarchive, <app_name>-macos.xcarchive
```

It has **one multi-platform app target**, named after `app_name`:

- **Sources**: `Sources/<target>`, compiled where it is (not copied), plus `Support/BundleModule.swift`.
- **Packages**: the packages `[swift] target` uses in `Package.swift`, read with `swift package dump-package` and `[swift.env]` set. URL packages keep their version rule (`from:`, `branch:`, …), and path packages stay path packages.
- **Destinations**: iOS if `[ios]` exists, macOS if `[macos]` exists.
- **Info.plist**: what every NucleantUI app needs (a scene manifest NucleantUI's launch delegate answers, the system launch screen, all orientations), then `info_plist` from `[ios]` and `[macos]`.
- **Signing**: automatic. The Simulator and macOS sign to run locally. A device and the App Store need `developer_team`.

`xcodebuild` runs with `-skipMacroValidation` and `-skipPackagePluginValidation`, which stand in for Xcode's *Trust & Enable* prompts for NucleantUI's macros and for packages' build plugins. If you open the project in Xcode, the first build stops on those prompts until you accept them.

!!! warning "Build plugins on the app target don't reach Xcode"
    The Xcode target compiles `Sources/<target>` directly. A build-tool plugin you apply to the app target in `Package.swift` doesn't run there. Plugins inside the packages you depend on run as usual. For PyShader shaders in the app itself, compile them ahead of time. See [Bundling PyShader Shaders](../guides/pyshader.md).

### Adding to the spec: `xcode.yaml`

To add something nucleant doesn't generate, such as a system framework, a build setting or another package, put an `xcode.yaml` (or `xcode.yml`) next to `nucleant.toml`. It is merged into `project.yml`:

- dictionaries merge recursively,
- lists are appended (nucleant's entries first),
- a scalar set on both sides takes your value.

```yaml title="xcode.yaml"
targets:
  MyApp:                       # the target is named after app_name
    settings:
      base:
        SWIFT_STRICT_CONCURRENCY: complete
    dependencies:
      - sdk: GameController.framework
```

---

## Simulator and devices

**Simulator.** `sim run` picks the `--name`/`--uuid` simulator, or the first available one, and builds for it. It boots it, installs the app with `simctl install` and launches it with `simctl launch --console-pty`, so the app's output streams in your terminal.

**Device.** `ios run` builds for `iphoneos`, installs with `devicectl device install app` and launches with `devicectl device process launch --console`. A device needs a team:

```toml title="nucleant.toml"
[ios]
developer_team = "ABC123XYZ"
```

!!! note "The iOS Simulator and GPU families"
    The Simulator's Metal device reports GPU Family Apple 2. MoltenVK allows draws with a base vertex or base instance only from Apple 3, and Skia's Vulkan backend uses both. So in the Simulator, what Skia draws may not show. Real iPhones and iPads from the A9 on are Apple 3 or newer. See NucleantVLC's README for the details.

---

## App Store

```bash
uv run nucleant apple ios archive release --upload
uv run nucleant apple macos archive release --upload --build-number 42 --app-version 1.2.0
```

- The archive goes to `project_dist/xcode/archives/<app_name>-<ios|macos>.xcarchive`.
- `--upload` exports it straight to App Store Connect with an API key, and needs `developer_team` in the platform's table.
- `--build-number` and `--app-version` override `CURRENT_PROJECT_VERSION` and `MARKETING_VERSION` on the command line, so nothing in the project is rewritten.

| Flag | Fallback | What |
|---|---|---|
| `--asc-key-id` | `ASC_KEY_ID` | App Store Connect API key ID |
| `--asc-issuer-id` | `ASC_ISSUER_ID` | Issuer ID |
| `--asc-key-path` | `ASC_KEY_PATH` | Path to the `.p8` key |

### From GitHub Actions

```bash
uv run nucleant apple ios create-action     # .github/workflows/appstore-ios.yml
uv run nucleant apple macos create-action   # .github/workflows/appstore-macos.yml
```

On every pushed tag, the workflow imports the signing certificate on `macos-latest` and runs `nucleant apple <platform> archive release --upload`. The workflow run number is the build number. A tag that looks like `1.2.3` (a leading `v` is stripped) becomes the app version. It needs these secrets:

| Secret | What |
|---|---|
| `APPLE_CERT_P12_BASE64` | The distribution certificate (`.p12`), base64-encoded |
| `APPLE_CERT_PASSWORD` | Its password |
| `ASC_KEY_P8` | The App Store Connect API key (`.p8` contents) |
| `ASC_KEY_ID` | Its key ID |
| `ASC_ISSUER_ID` | Its issuer ID |
