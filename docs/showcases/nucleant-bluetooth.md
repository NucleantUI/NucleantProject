# Showcase: NucleantBluetooth

[NucleantBluetooth](https://github.com/NucleantUI/NucleantBluetooth) is Bluetooth Low Energy for NucleantUI apps, as a central: scan, connect, discover services and characteristics, read, write and get notified. Everything is an `@Observable` class, reached through `@Environment(\.bluetoothManager)`. It runs on iOS over CoreBluetooth, and on Android over `android.bluetooth` through swift-java.

Its repository has a demo package, **BluetoothScanner** (`Demo/`). It lists the devices around with their live signal strength, and has a screen per device for its advertising data, services and characteristics. As with [NucleantVLC](nucleant-vlc.md), turning the demo into a nucleant app means writing the demo's files into a project. On Android, the app also needs the permissions and one manifest entry.

---

## 1. A project

```bash
uv init --bare bluetooth-scanner && cd bluetooth-scanner
uv add --dev git+https://github.com/NucleantUI/NucleantProject
uv run nucleant init
```

The target is `BluetoothScanner`.

## 2. The demo's files

```bash
git clone https://github.com/NucleantUI/NucleantBluetooth ../NucleantBluetooth
cp ../NucleantBluetooth/Demo/Sources/BluetoothScanner/*.swift Sources/BluetoothScanner/
```

```
Sources/BluetoothScanner/
├── BluetoothScannerApp.swift   # @main: a NavigationStack around the scanner
├── ScannerScreen.swift         # the devices around, sorted and filtered
├── PeripheralScreen.swift      # one device: advertising, services, characteristics
└── Formatting.swift
```

The demo's `BluetoothScannerApp.swift` has the same name as the starter `nucleant init` wrote for this target, so the copy replaces it. For a project named differently, delete the starter `<Target>App.swift`: there can be only one `@main`.

Make the entry public, as Android needs:

```swift title="Sources/BluetoothScanner/BluetoothScannerApp.swift" hl_lines="5 6 8"
import NucleantBluetooth
import NucleantUI

@main
public struct BluetoothScannerApp: NucleantApp {
    public init() {}

    public var body: some Scene {
        WindowGroup("Bluetooth Scanner") {
            NavigationStack("Nearby") {
                ScannerScreen()
            }
            // The framework's surface color, so the page is drawn in the
            // same appearance as its text.
            .background(BackgroundStyle.background)
        }
        .defaultSize(width: 430, height: 860)
    }
}
```

## 3. Package.swift

Add NucleantBluetooth to the starter manifest:

```swift title="Package.swift"
let dependencies: [Package.Dependency] = [
    .package(url: "https://github.com/NucleantUI/NucleantUI.git", branch: "master"),
    .package(url: "https://github.com/NucleantUI/NucleantBluetooth", branch: "main"),
]

let appDependencies: [Target.Dependency] = [
    .product(name: "NucleantUI", package: "NucleantUI"),
    .product(name: "NucleantBluetooth", package: "NucleantBluetooth"),
]
```

That is all the Swift side needs. On Android, NucleantBluetooth brings swift-java and its own Java along with it:

- Android's Bluetooth callbacks are abstract Java classes, which Swift can't subclass. So the package ships a small Java helper for each one in its [`Android/java`](https://github.com/NucleantUI/NucleantBluetooth/tree/main/Android/java): `ScanCallbacks`, `GattCallbacks`, `AdapterStateReceiver` and `BluetoothAppContext`.
- nucleant compiles the `Android/java` of every package in the Swift graph together with the app (see [Packages that bring their own Android half](../configuration/package-swift.md#packages-that-bring-their-own-android-half)). You don't copy those files.
- PureSwift's Bluetooth names (`uuid.metadata?.name`, `companyIdentifier.name`) come from its resource bundle. The central points `Bundle.main` at `NUCLEANT_APP_PATH`, where nucleant unpacks the bundles, before anything reads them.

## 4. The permissions

```toml title="nucleant.toml"
[swift]
target = "BluetoothScanner"
entry = "BluetoothScannerApp"

[android]
package_name = "org.example.bluetooth_scanner"
permissions = [
    # NucleantBluetooth: Nearby devices from API 31, precise location and
    # the old install-time pair below it.
    "BLUETOOTH_SCAN", "BLUETOOTH_CONNECT",
    "ACCESS_FINE_LOCATION", "BLUETOOTH", "BLUETOOTH_ADMIN",
]
```

Android only hands scan results to an app with precise location. From Android 12 (API 31) that requirement is waived when `BLUETOOTH_SCAN` is declared with `android:usesPermissionFlags="neverForLocation"`. When the central starts, it checks how the app declared it and asks for what is needed: Nearby devices, plus location unless it is waived. Until they are granted, `state` is `.unauthorized`. When location is needed, the device's location setting has to be on as well.

!!! note "INTERNET"
    An empty `permissions` list declares `INTERNET` for you. A non-empty one declares only what it lists. Add `"INTERNET"` here if the app also needs the network.

## 5. The provider

Inside `<application>` in `AndroidManifest.tmpl.xml`, add NucleantBluetooth's provider. Android creates it together with the app, and it hands the central the app's `Context` and the Activity in front, which the permission requests are made on:

```xml title="AndroidManifest.tmpl.xml" hl_lines="9 10 11 12 13 14"
    <application
        android:label="{{ app_name }}"
        android:icon="@mipmap/ic_launcher"
        android:allowBackup="true"
        android:supportsRtl="true"
        android:hardwareAccelerated="true"
        android:theme="@android:style/Theme.DeviceDefault.NoActionBar">{{ meta_data }}
{{ services }}
        <!-- NucleantBluetooth: hands its Android central the app's Context
             and the Activity in front (Android/java). -->
        <provider
            android:name="org.nucleantui.bluetooth.BluetoothAppContext"
            android:authorities="${applicationId}.nucleantbluetooth"
            android:exported="false" />
        <activity
            android:name=".MainActivity"
            ...
```

The template is yours, and nucleant keeps whatever you add to it (see [Templates](../platforms/android.md#templates)).

## 6. Run it

```bash
uv run nucleant android run --logcat
```

### In the emulator

The Android emulator has Bluetooth: netsim, a virtual radio. NucleantBluetooth's [emulator-ble-server](https://github.com/NucleantUI/NucleantBluetooth/tree/main/tools/android_emulator/emulator-ble-server) uses [Bumble](https://github.com/google/bumble) to put fake peripherals on it, and the scanner finds and connects to them like real ones. They include a heart-rate strap, a thermometer that indicates, beacons, a UART console, a test bench of refused reads and writes, and devices that drop the connection or leave range. With the emulator running:

```bash
cd ../NucleantBluetooth/tools/android_emulator/emulator-ble-server
uv run emulator-ble-server
```

### On iOS

The same sources build for iOS through the Xcode project. CoreBluetooth needs a usage string, which goes into `info_plist`:

```toml title="nucleant.toml"
[ios]
bundle_id = "org.example.bluetooth_scanner"
developer_team = "ABC123XYZ"   # a device: the Simulator has no Bluetooth
info_plist = { NSBluetoothAlwaysUsageDescription = "The scanner lists the Bluetooth devices around you and connects to the ones you pick." }
```

```bash
uv run nucleant apple ios run
```

macOS and Linux are still to come in NucleantBluetooth, so `swift run` builds the app on a Mac, but there is no central behind it yet.

---

## What carried over

| From the demo | In the app |
|---|---|
| `Demo/Sources/BluetoothScanner/*.swift` | `Sources/BluetoothScanner/*.swift`, with `public` on the entry |
| The demo's dependencies | The app's `Package.swift` |
| NucleantBluetooth's `Android/java` | Nothing to do: compiled in from the package |
| — | The `permissions`, the `<provider>`, and `NSBluetoothAlwaysUsageDescription` for iOS |
