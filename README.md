# NucleantProject

`nucleant` builds and runs [NucleantUI](https://github.com/NucleantUI/NucleantUI)
apps on Android, iOS, macOS and Linux from one `nucleant.toml`. It is the
successor of ksproject: same pipeline, Swift instead of Python.

The wheel is `nucleant-project`; the module and command are `nucleant`.

## Start a project

```sh
uv init --bare MyApp && cd MyApp
uv add --dev nucleant-project          # or: uv add --dev ../NucleantProject
uv run nucleant init                   # --nucleantui ../NucleantUI for a local checkout
uv run nucleant toolchain install      # swiftly, Swift 6.3.3, Swift SDKs
```

`init` writes `nucleant.toml`, a starter app in `Sources/<App>/`,
`.swift-version`, the Android templates and the desktop `Package.swift`. It
never overwrites existing files.

## Run

Every platform has one `run`: build, install, launch.

```sh
uv run nucleant apple macos run          # swift run   (--xcode: the .app via Xcode)
uv run nucleant linux run                # swift run
uv run nucleant android run              # Gradle + Swift cross-compile, install, launch
uv run nucleant android run --name Pixel --logcat
uv run nucleant apple sim run --name "iPhone 17"
uv run nucleant apple ios run            # first connected device
```

Distribution: `nucleant android archive release --bundle`, `nucleant android
sign`, `nucleant android genkey`, `nucleant apple {ios,macos} archive
--upload`, and `create-action` for tag-triggered GitHub workflows.

## Configuration

Only `nucleant.toml` is read. Its root is what `[tool.nucleant]` in
pyproject.toml will be later; pyproject.toml is there for uv to track the
tool.

| table | |
| --- | --- |
| root | `app_name`, `bootstrap` (`nucleantui`), `command_plugins` |
| `[toolchain]` | `swift` (default `6.3.3`), `swiftly`, `android_sdk`, `wasm_sdk` |
| `[swift]` | `target`, `entry`, `sources`, `android_package`, `[swift.env]`, `[[swift.dependencies]]` |
| `[android]` | package name, archs, API levels, NDK, signing-free build settings, hooks |
| `[ios]`, `[macos]` | bundle id, deployment target, version, info_plist, entitlements, team |
| `[linux]`, `[wasm]` | platform switches (`[wasm]` makes `toolchain install` fetch the wasm SDK) |
| `[python]` | `enabled` — the Python layer, transferred but not enabled yet |

One `[[swift.dependencies]]` list feeds the desktop `Package.swift`, the
Android Main Swift Package and the Xcode project.

## Toolchain

- **swiftly** is installed if missing (user-level, no shell-profile edits).
- **Swift** `[toolchain] swift` is installed with swiftly and invoked by
  absolute path (`+6.3.3`), so the global default toolchain is untouched.
- **Swift SDKs** for Android and wasm are installed with `swift sdk install`,
  using the checksum swift.org publishes for that release. The Android one is
  installed on the first `android run`; both via `toolchain install`.
- **Android SDK/NDK/Java** are found or installed as ksproject did, under
  `~/.nucleant` (`global_tools = true`) or `./.nucleant`.

## The Python layer

ksproject's Python handling (site-packages per ABI/slice, CPython for Android,
Python.xcframework, `.python-version` pins) lives in `nucleant.python` and is
switched off (`PYTHON_SUPPORT_ENABLED = False`) until Python returns as a
layer on top of NucleantUI.
