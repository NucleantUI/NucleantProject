# Android (Gradle)

Android is where nucleant does the most work. A NucleantUI app on Android is an APK: a Java Activity, plus the app's Swift cross-compiled into a native library the Activity loads. nucleant generates that Gradle project from `nucleant.toml` and the app's `Package.swift`, and runs it.

```bash
uv run nucleant android run                      # first connected device, else boots an emulator
uv run nucleant android run --name Pixel_8       # boot this AVD
uv run nucleant android run --uuid emulator-5554 # this adb serial
uv run nucleant android run --logcat             # then follow the app's logcat
uv run nucleant android run release --clean      # a clean release build
```

---

## What `android run` does

1. **Picks the device first.** The `--uuid` serial, the `--name` AVD (booted), the first online device, or, with nothing connected, an AVD. If there is no AVD, nucleant creates `nucleant_default` with a `google_apis` image for the host's ABI.
2. **Checks the ABI.** If the device's ABI isn't in `[android] archs`, it stops before building, because a full Swift cross-compile is expensive to waste:

    ```text
    error: emulator-5554 runs x86_64, but [android] archs only builds arm64-v8a. Add "x86_64" to archs in nucleant.toml.
    ```

3. **Runs `pre_build`**, then **generates** `project_dist/gradle` and its Swift package.
4. **Runs Gradle.** For each ABI in `archs`, Gradle runs `swift build` for the Android triple with the Android Swift SDK and `ANDROID_BUILD=1`. It stages the `.so` files into `jniLibs`, the SwiftPM resource bundles into assets, and each package's `Android/java` into the Java sources. Then it assembles the APK.
5. **Installs** the APK that matches the device's ABI and **launches** it.

The SDK, NDK, Java, CMake, the emulator, swiftly, Swift and the Android Swift SDK are installed the first time they are needed (see [Toolchain](../getting-started/toolchain.md)).

---

## Commands

| Command | What it does |
|---|---|
| `android run [debug\|release]` | Build, install and launch. `--uuid`, `--name`, `--clean`, `--logcat` |
| `android archive [release\|debug]` | Build without launching: an APK, an AAB with `--bundle`, an AAR with `--aar` |
| `android generate` | Write `project_dist/gradle` and its Swift package, without building. Useful for opening the project in Android Studio |
| `android generate-templates [--force]` | Write `AndroidManifest.tmpl.xml` / `build.tmpl.gradle.kts` to the project root |
| `android devices` | List connected devices and AVDs |
| `android get-path sdk\|ndk\|emulator` | Print where a tool was found |
| `android genkey` | Make a release keystore |
| `android sign` | Sign the built release APK (or `--bundle` AAB) |
| `android create-action` | Write a tag-triggered Play Store workflow |

---

## The generated project

```
project_dist/gradle/
├── settings.gradle.kts
├── build.gradle.kts
├── gradlew
├── app/
│   ├── build.gradle.kts         # from build.tmpl.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml  # from AndroidManifest.tmpl.xml
│       └── java/…/MainActivity  # this app's NucleantActivity subclass
└── swift/                       # the Main Swift Package
    ├── Package.swift            # depends on the app's package: .package(path: "../../..")
    └── Sources/…                # the JNI entry point nucleantRunMain(appPath:)
```

Build outputs are where Gradle puts them:

| Kind | Path |
|---|---|
| APK | `project_dist/gradle/app/build/outputs/apk/` |
| AAB | `project_dist/gradle/app/build/outputs/bundle/` |
| AAR | `project_dist/gradle/app/build/outputs/aar/` |

All of `project_dist/` is regenerated on every build and is gitignored. Your changes belong in `nucleant.toml`, the two templates, or the app's `Package.swift`.

### How the app starts

The Activity, `org.nucleantui.NucleantActivity`, comes from **NucleantApplication**'s `Android/java`. It loads `libNucleantMain.so` and calls `nucleantRunMain(appPath:)`. That function:

- sends stdout and stderr to logcat,
- `chdir`s into the app's unpacked files and sets `NUCLEANT_APP_PATH` to it,
- constructs `[swift] entry` (the reason it must be `public` with a `public init()`) and starts it.

Resources are looked up under `NUCLEANT_APP_PATH`. See [Resources](../configuration/package-swift.md#resources).

`NucleantActivity` also stops the frames in `onPause()` and starts them again in `onResume()`, so an app that isn't shown draws nothing. The window's [`scenePhase`](../guides/scene-phase.md#android) stays `.active` on Android for now.

---

## Templates

`nucleant init` writes two templates to the project root. They are the starting point for the generated manifest and app module, so edit them freely:

=== "AndroidManifest.tmpl.xml"

    ```xml
    <manifest xmlns:android="http://schemas.android.com/apk/res/android">

    {{ permissions }}

        <!-- Vulkan 1.1 is the floor Nucleant renders against; below it the app has
             no rendering path at all, so keep it off those devices in the store. -->
        <uses-feature android:name="android.hardware.vulkan.version"
            android:version="0x401000"
            android:required="true" />

        <application
            android:label="{{ app_name }}"
            android:icon="@mipmap/ic_launcher"
            ...
            android:theme="@android:style/Theme.DeviceDefault.NoActionBar">{{ meta_data }}
    {{ services }}
            <activity
                android:name=".MainActivity"
                android:launchMode="singleTask"
                android:exported="true">{{ activity_meta_data }}
                ...
            </activity>
        </application>
    </manifest>
    ```

=== "build.tmpl.gradle.kts"

    ```kotlin
    plugins {
        id("{{ plugin_id }}")
    }

    {{ swift_config }}

    android {
        namespace = "{{ package_name }}"
        compileSdk = {{ compile_sdk }}
        ...
        defaultConfig {
    {{ app_id_lines }}        minSdk = {{ min_sdk }}
            targetSdk = {{ target_sdk }}
            ndk { abiFilters += setOf({{ abi_filters }}) }
        }
        ...
    }

    dependencies {
        // Drop extra .aar / .jar libraries into app/libs/.
        implementation(fileTree("libs") { include("*.aar", "*.jar") })
    {{ extra_deps }}
    }

    {{ build_tasks }}
    ```

The `{{ … }}` placeholders are filled from `nucleant.toml`. Anything else you add, such as a `<provider>`, an `<intent-filter>` or a Gradle block, is kept as written. The [NucleantBluetooth showcase](../showcases/nucleant-bluetooth.md) adds a `<provider>` this way.

!!! note "Template versions"
    Each template starts with a `nucleant-template: N` marker. Don't remove it. When nucleant's own default template gets newer, the generator replaces yours and keeps your copy as `AndroidManifest.tmpl.xml.vN.bak` (or `build.tmpl.gradle.kts.vN.bak`) so you can carry your changes over. `generate-templates --force` resets both to the current defaults.

---

## ABIs, devices and emulators

| ABI | For |
|---|---|
| `arm64-v8a` | Phones and tablets, and emulators on Apple Silicon |
| `x86_64` | Emulators on Intel hosts |

Every ABI is a full Swift cross-compile, so list only the ones you run. On the emulator, the virtual GPU has no `VK_KHR_external_memory_fd`. Set this so NucleantUI takes the AHardwareBuffer path:

```toml title="nucleant.toml"
[swift.env]
NUCLEANT_ANDROID_USE_AHARDWAREBUFFER = "1"
```

`min_api` can't go below **28**: the Swift Android SDK has no triples below `android28`.

---

## Releasing

```bash
# Once: a release keystore (or set KEYSTORE / STOREPASS / KEYALIAS / KEYPASS in .env)
uv run nucleant android genkey --out release.jks --storepass '…' --keyalias app

# Build and sign an App Bundle
uv run nucleant android archive release --bundle
uv run nucleant android sign --bundle --keystore release.jks --storepass '…' --keyalias app
```

- `genkey` makes an RSA 2048 key valid for 10000 days. `--dname` sets the subject, and the default is `CN=<app_name>, O=NucleantUI, C=US`. It won't overwrite an existing keystore.
- `sign` signs every unsigned release artifact it finds, APKs by default or AABs with `--bundle`. A signed copy is written next to each one, with `-unsigned` replaced by `-signed`.
- Every credential flag falls back to its environment variable, and `.env` is loaded first. The template `.gitignore` keeps `.env` and `*.jks` out of git.

### Play Store from GitHub Actions

```bash
uv run nucleant android create-action
```

This writes `.github/workflows/playstore-android.yml`. On every pushed tag, it builds and signs a release AAB on `ubuntu-latest` and uploads it to the Play Console. nucleant provisions Swift and the Android tools in CI the same way it does locally. The workflow needs these repository secrets:

| Secret | What |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | The release keystore, base64-encoded |
| `STOREPASS` | Keystore password |
| `KEYALIAS` | Key alias |
| `KEYPASS` | Key password (may be empty if it is the same as `STOREPASS`) |
| `PLAY_SERVICE_ACCOUNT_JSON` | A Google Cloud service-account JSON with access to the app in the Play Console |
