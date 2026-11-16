# App Lifecycle (scenePhase)

From NucleantUI 0.3.2, every window has a phase, as in SwiftUI. A view reads it through the environment and acts when it changes:

```swift
@View
struct TimerScreen {
    let session: Session
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        Clock(session: session)
            .onChange(of: scenePhase) { old, new in
                if new == .active { session.resume() } else if old == .active { session.pause() }
            }
    }
}
```

| Phase | Meaning |
|---|---|
| `.active` | In the foreground and in use |
| `.inactive` | In the foreground but not in use. No input reaches it, and timers, animations and polling can pause |
| `.background` | Out of sight. The window draws nothing until it comes back, so save what has to be saved and stop the rest |

The phases are ordered: `background < inactive < active`. A view gets the phase of the window it is in.

The phase itself comes from the platform, through the app nucleant builds for it. The rest of this page covers what moves it on each one. It needs NucleantUI 0.3.2 in the app's `Package.swift`:

```swift title="Package.swift"
.package(url: "https://github.com/NucleantUI/NucleantUI.git", .upToNextMinor(from: "0.3.2")),
```

---

## On each platform

| Platform | `.active` | `.inactive` | `.background` |
|---|---|---|---|
| **macOS** (`swift run` and the `.app`) | Otherwise, including behind other windows or with another app in front | Minimized into the Dock | The app is hidden (++cmd+h++) |
| **iOS** | In use | The app switcher, Control Center, a call, and on the way to or from the background | Off screen: another app, the Home Screen, the device locked |
| **Android** | The Activity is resumed | Paused: a dialog or a permission request over it, another app in front in split screen, and on the way to the background | Stopped: another app, the Home screen, the screen off. Also while there is no surface to draw into |
| **Linux** | Always | — | — |

When the phase changes, NucleantUI runs one frame at once, so `onChange(of: scenePhase)` runs straight away. It doesn't wait for the next tick, which a window out of sight doesn't get.

### macOS

AppKit reports both: the window's delegate is told when it is minimized and restored, and the app when it is hidden and shown again. Under `swift run` and in the `.app` it is the same code, so the phases are the same. See [macOS: the window's phase](../platforms/macos.md#the-windows-phase).

### iOS

The window follows its scene's notifications: activate, deactivate, enter background, enter foreground. The scene comes from nucleant's Info.plist. It declares a `UIApplicationSceneManifest` without naming a delegate class, so UIKit asks NucleantUI's launch delegate for one, and NucleantUI answers with its own scene delegate. Your `@main` stays a plain `NucleantApp`.

!!! warning "Leave `UIApplicationSceneManifest` to nucleant"
    `[ios] info_plist` replaces top-level keys. A `UIApplicationSceneManifest` in it replaces nucleant's whole entry, including how the scene gets its delegate.

### Android

The window follows the Activity. `NucleantActivity`, which nucleant compiles in from NucleantApplication's `Android/java`, reports `onStart()`, `onResume()`, `onPause()` and `onStop()`, and the phase follows them. A permission request is a dialog over the Activity, so asking for one makes the window `.inactive` until it is answered.

Without a surface, the window is in the background as well. Coming back, Android resumes the Activity before its new surface exists, so the window goes from `.background` straight to `.active` once there is something to draw into. It enters `.background` before the old surface is destroyed. That way the frame a phase change runs never draws into a surface that is gone.

Rotating doesn't change the phase. The frames still stop in `onPause()` and start again in `onResume()`, so a paused app draws nothing.

Android phases come with NucleantApplication 0.1.3. NucleantUI takes NucleantApplication up to its next minor version, so a fresh resolve picks it up. An existing project's Android build keeps the version it pinned until you update it:

```bash
cd project_dist/gradle/swift
ANDROID_BUILD=1 swiftly run swift package --scratch-path ../app/build/swift update NucleantApplication +6.3.3
```

Add your `[swift.env]` variables in front of it, as described in [Updating dependencies](../configuration/package-swift.md#updating-dependencies).

### Linux

The window stays `.active`.

---

## Example: pause the player

The [NucleantVLC showcase](../showcases/nucleant-vlc.md) doesn't look at the phase. To pause the player when the window leaves `.active`, and play again once it is back, add this to `PlayerScreen` in `Sources/VlcPlayer/PlayerViews.swift`:

```swift title="Sources/VlcPlayer/PlayerViews.swift" hl_lines="4 5 10 11 12 13 14 15 16 17 18 19"
@View
struct PlayerScreen {
    @State private var player = Player()
    @Environment(\.scenePhase) private var scenePhase
    @State private var resumeOnActive = false
    // …

    var body: some View {
        ZStack { /* … */ }
            .onChange(of: scenePhase) { _, phase in
                if phase == .active {
                    if resumeOnActive { player.play() }
                    resumeOnActive = false
                } else if player.isPlaying {
                    // Leaving .active: pause, and remember to play on.
                    player.pause()
                    resumeOnActive = true
                }
            }
    }
}
```

`resumeOnActive` makes sure the window only plays again if the phase paused it. A video you paused yourself stays paused. Going to the background, the window passes `.inactive` first, so the first change away from `.active` pauses the player. Coming back plays it once, whether the window comes through `.inactive` (iOS) or straight to `.active` (Android).

The NucleantUI example [Pomodoro](https://nucleantui.github.io/NucleantUI/documentation/nucleantui/pomodoroexample/) does the same with a timer. It stops the tick while the window is out of use, then catches the session up on the time away once the window is active again.
