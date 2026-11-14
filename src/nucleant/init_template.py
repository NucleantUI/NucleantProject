"""What ``nucleant init`` writes: nucleant.toml and a starter NucleantUI app."""

from __future__ import annotations

from .gradle.android_toolchain import DEFAULT_API_VERSION, DEFAULT_SDK_VERSION
from .nucleant_toml import DEFAULT_SWIFT_VERSION

def nucleant_toml(
    app_name: str,
    module_name: str,
    target: str,
    entry: str,
) -> str:
    return f"""\
#### NucleantProject configuration ####
#
# Read by `nucleant` (NucleantProject). The same keys will be accepted as
# [tool.nucleant] in pyproject.toml later; pyproject.toml itself is only for
# uv to track the nucleant tool.

app_name = "{app_name}"
bootstrap = "nucleantui"
# command_plugins = ["my_package.nucleant_plugin"]

[toolchain]
# Installed and selected with swiftly (`nucleant toolchain install`). Pinned
# per command with +{DEFAULT_SWIFT_VERSION}; your global default is left alone.
swift = "{DEFAULT_SWIFT_VERSION}"
swiftly = true # false: use `swift` from PATH — it must be this exact version
# Swift SDK ids, when not swift-<version>-RELEASE_<android|wasm>:
# android_sdk = "swift-{DEFAULT_SWIFT_VERSION}-RELEASE_android"
# wasm_sdk = "swift-{DEFAULT_SWIFT_VERSION}-RELEASE_wasm"

#### NucleantUI ####
# The nucleantui bootstrap always builds the app against NucleantUI; this
# picks which. One of branch / up_to_major / exact.

[nucleantui]
branch = "master"
# up_to_major = "0.1.0" # 0.1.0 or newer, below 1.0.0
# exact = "0.1.0"
# url = "https://github.com/<you>/NucleantUI.git" # a fork
# path = "../NucleantUI" # a local fork; takes no version

#### The app's Swift ####
# One list of sources and dependencies feeds every platform: the desktop
# Package.swift (`swift run`), the Android Main Swift Package and the Xcode
# project are all generated from it.

[swift]
target = "{target}" # the Swift target / module the sources compile into
entry = "{entry}" # the NucleantApp type the Android Activity starts
sources = ["Sources/{target}"]
# android_package = "project_dist/gradle/swift"   # the generated Android package
# unsafe_flags = []

[swift.env]
# Environment for every Swift build of the app.
# Emulator only: the virtual GPU has no VK_KHR_external_memory_fd.
# NUCLEANT_ANDROID_USE_AHARDWAREBUFFER = "1"

# More Swift packages, besides NucleantUI:
# [[swift.dependencies]]
# name = "Yams"
# url = "https://github.com/jpsim/Yams.git"
# up_to_major = "6.0.0" # or branch / exact; or path = "../Yams"
# products = ["Yams"]

#### Android ####

[android]
package_name = "org.example.{module_name}"

# version_name = "0.1" # change when you release a new version
version_code = 1 # increase for every upload of the same version_name

# icon = "relative to nucleant.toml (png)"
# presplash_color = "#FFFFFF"
# presplash = "relative to nucleant.toml (png,jpg,gif)"
# presplash_lottie = "relative to nucleant.toml (json)"

archs = [
    "arm64-v8a",
    # "x86_64", # emulators on Intel hosts; each ABI is a full Swift cross-compile
]
gradle_dependencies = [
    # "com.onesignal:OneSignal:[5.6.1, 5.9.99]"
]
gradle_plugins = [
    # 'id("com.google.gms.google-services") version "4.4.2" apply false'
]
permissions = [
    # "POST_NOTIFICATIONS", "INTERNET", "ACCESS_NETWORK_STATE", "WAKE_LOCK"
]

api = {DEFAULT_API_VERSION}
# 28 is the Swift Android SDK's floor: it has no triples below android28.
min_api = 28
sdk = "{DEFAULT_SDK_VERSION}"
ndk = "28c"
ndk_api = 28

# one universal APK for all archs, or one APK per arch
universal_apk = true

global_tools = true # false: project-local SDK/NDK in ./.nucleant; true: shared in ~/.nucleant (or global_tools_path)
# global_tools_path = "~/.nucleant"

# sdk_path = "/path/to/android-sdk"
# ndk_path = "/path/to/android-ndk"
# java_path = "/path/to/jdk"

# include_files = [
#     ["gradle/app", "./google-services.json"]
# ]

# pre_build = "path/to/android_prebuild.py"
# post_build = "path/to/android_postbuild.py"

# <meta-data> entries inside <application>
# [android.meta_data]
# "com.google.android.gms.ads.APPLICATION_ID" = "ca-app-pub-xxxxxxxx~xxxxxxxx"

#### Apple ####

[ios]
bundle_id = "org.example.{module_name}"
# 17.0: the Swift graph uses Observation (iOS 17 / macOS 14 floor).
minimum_deployment = "17.0"
version = "1.0"
build_number = "1"
info_plist = {{}}
entitlements = {{}}
# developer_team = "ABC123XYZ" # needed for a real device and the App Store
# pre_build = "path/to/ios_prebuild.py"
# post_build = "path/to/ios_postbuild.py"

[macos]
bundle_id = "org.example.{module_name}"
minimum_deployment = "14.0"
version = "1.0"
build_number = "1"
info_plist = {{}}
entitlements = {{}}
# developer_team = "ABC123XYZ"

#### Linux ####

[linux]

#### WebAssembly ####
# Uncomment to have `nucleant toolchain install` fetch the wasm Swift SDK.
# [wasm]

#### Python ####
# The Python layer (site-packages, embedded CPython) is carried over from
# ksproject but not enabled in this version of nucleant.

[python]
enabled = false
"""


def app_swift(app_name: str, entry: str) -> str:
    return f"""\
import NucleantUI

@main
struct {entry}: NucleantApp {{
    var body: some Scene {{
        WindowGroup("{app_name}") {{
            ContentView()
        }}
        .defaultSize(width: 480, height: 640)
    }}
}}

@View
struct ContentView {{
    @State private var taps = 0

    var body: some View {{
        VStack(spacing: 16) {{
            Text("Hello from {app_name}")
                .font(.system(size: 28, weight: .semibold))
            Text("Tapped \\(taps) times")
                .foregroundStyle(.secondary)
            Button("Tap") {{ taps += 1 }}
        }}
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }}
}}
"""


GITIGNORE_BLOCK = """\
# nucleant
project_dist/
.nucleant/
.build/
.swiftpm/
.env
*.jks
google-services.json
"""

ENV_TEMPLATE = """\
# Loaded by nucleant; real environment variables win.
# KEYSTORE=""
# KEYALIAS=""
# STOREPASS=""
# KEYPASS="defaults_to_storepass"
# ASC_KEY_ID=""
# ASC_ISSUER_ID=""
# ASC_KEY_PATH=""
"""
