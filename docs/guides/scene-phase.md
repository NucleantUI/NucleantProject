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
| **Android** | Always, for now | — | — |
| **Linux** | Always | — | — |

When the phase changes, NucleantUI runs one frame at once, so `onChange(of: scenePhase)` runs straight away. It doesn't wait for the next tick, which a window out of sight doesn't get.

### macOS

AppKit reports both: the window's delegate is told when it is minimized and restored, and the app when it is hidden and shown again. Under `swift run` and in the `.app` it is the same code, so the phases are the same. See [macOS: the window's phase](../platforms/macos.md#the-windows-phase).

### iOS

The window follows its scene's notifications: activate, deactivate, enter background, enter foreground. The scene comes from nucleant's Info.plist. It declares a `UIApplicationSceneManifest` without naming a delegate class, so UIKit asks NucleantUI's launch delegate for one, and NucleantUI answers with its own scene delegate. Your `@main` stays a plain `NucleantApp`.

!!! warning "Leave `UIApplicationSceneManifest` to nucleant"
    `[ios] info_plist` replaces top-level keys. A `UIApplicationSceneManifest` in it replaces nucleant's whole entry, including how the scene gets its delegate.

### Android

The window's phase doesn't change on Android yet. It stays `.active`, so `onChange(of: scenePhase)` doesn't run there.

The app does stop drawing when it isn't shown. `NucleantActivity`, which nucleant compiles in from NucleantApplication's `Android/java`, stops the frames in `onPause()` and starts them again in `onResume()`. So a paused app costs no frames. It just doesn't tell its views.

### Linux

The window stays `.active`.

---

## Example: pause the player

The [NucleantVLC showcase](../showcases/nucleant-vlc.md) plays on while the window is minimized or the app is hidden. To pause it when the window leaves `.active`, and play again once it is back, add this to `PlayerScreen` in `Sources/VlcPlayer/PlayerViews.swift`:

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

`resumeOnActive` makes sure the window only plays again if the phase paused it. A video you paused yourself stays paused. On iOS the window passes `.inactive` on its way to and from `.background`, so the first change away from `.active` pauses the player, and coming back plays it once.

The NucleantUI example [Pomodoro](https://nucleantui.github.io/NucleantUI/documentation/nucleantui/pomodoroexample/) does the same with a timer. It stops the tick while the window is out of use, then catches the session up on the time away once the window is active again.
