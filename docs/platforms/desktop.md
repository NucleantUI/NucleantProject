# Desktop: swift run

On macOS and Linux a NucleantUI app is an ordinary executable Swift package. It needs no generated project and no extra tool, so `swift run` builds and runs it.

```bash
uv run nucleant apple macos run            # on a Mac
uv run nucleant linux run                  # on Linux
uv run nucleant linux run release          # a release build
uv run nucleant apple macos run -- --flag  # arguments after -- go to the app
```

Both commands do the same thing:

1. Resolve the [pinned Swift](../getting-started/toolchain.md) (installing it the first time).
2. Check that the project has its `Package.swift`.
3. Run `swift run -c <debug|release> <[swift] target> [app args…]` in it, with `[swift.env]` set.

That is `swift run` with the project's toolchain, so plain `swift run` works just as well, for example from your editor. To use the pinned toolchain yourself: `swiftly run swift run +6.3.3`.

!!! note "Desktop builds are not cross-compiled"
    `apple macos run` runs on macOS and `linux run` runs on Linux. Each builds for the machine it runs on. Without a `[linux]` table, `linux run` prints a note and runs anyway.

---

## Why use nucleant for a desktop app at all

For day-to-day work on the desktop, you don't need to: `swift run` is the whole loop. nucleant earns its place in three cases:

- **Setup.** `nucleant init` gives a desktop-only app the same layout as every other Nucleant app: a `Package.swift` that already switches its target for Android, a `nucleant.toml` with each platform's settings, and the Android templates. Adding Android or the App Store later means running a command, not restructuring the project.
- **The toolchain.** Everyone on the project builds with the same Swift, without changing anyone's global default.
- **A real Mac app.** `swift run` starts a bare executable. For a signed `.app` bundle, the Mac App Store, or entitlements, use the Xcode project:

    ```bash
    uv run nucleant apple macos run --xcode     # the .app, through Xcode
    uv run nucleant apple macos archive --upload
    ```

    See [iOS & macOS](apple.md).
