# Bundling PyShader Shaders

[PyShader](https://nucleantui.github.io/PyShader/) writes shaders in Python syntax and compiles them to SPIR-V. NucleantUI runs SPIR-V: a `.spv` module goes into `SpirvFunction`, and from there into a `Shader` view or the `.shader(_:)` modifier.

So bundling PyShader into the app's Swift package means compiling the `.py` files to `.spv` **when the app builds** and shipping them as the target's resources. The app has no compiler in it at run time. PyShader's two SwiftPM plugins do the compiling. Both read a `pyshader.toml` at the package root:

| Plugin | When it runs | Where the `.spv` goes |
|---|---|---|
| `PyShaderBuildPlugin` | every build of the target it is applied to, again whenever a shader, a module it imports or `pyshader.toml` changes | into the build, as one of the target's resources (`Bundle.module`) |
| `PyShaderCommandPlugin` | `swift package pyshader-compile` | to each section's `output` path in the package, to commit |

The full reference is PyShader's [Package plugins](https://nucleantui.github.io/PyShader/compiler/plugins/) page.

---

## The files

```
MyApp/
├── nucleant.toml
├── Package.swift
├── pyshader.toml          # which shaders, compiled how
├── Shaders/
│   └── Glow.py            # the PyShader source
└── Sources/MyApp/
    ├── MyAppApp.swift
    └── ShaderModules.swift
```

The `.py` files stay outside `Sources/`. They are the plugin's input, not the target's sources or resources.

### The shader

```python title="Shaders/Glow.py"
from pyshader import *


class Glow:
    """The shader's input: how bright, and what color."""
    intensity: float
    tint: float4


def main(uv: float2, glow: Glow) -> float4:
    falloff = smoothstep(0.5, 0.0, distance(uv, float2(0.5)))
    return glow.tint * glow.intensity * falloff
```

`def main` is a compute shader, run over every pixel of the view. Its input is the `class` parameter, read whole: the app hands over its fields in order. See PyShader's [targets](https://nucleantui.github.io/PyShader/targets/) and its [standard library](https://nucleantui.github.io/PyShader/stdlib/) for what else a shader can do.

### pyshader.toml

```toml title="pyshader.toml"
[Glow]
source = "Shaders/Glow.py"
output = "Sources/MyApp/Shaders/Glow.spv"   # used by `pyshader-compile`; the build plugin uses only the file name
target = "compute"
```

Each `[section]` is one shader, and its name is the `.spv` file's name. Two keys matter most for NucleantUI:

| Key | Use |
|---|---|
| `target = "compute"` | What `Shader(...)` and `.shader(_:)` run. `"graphics"` is a vertex + fragment pair |
| `content-top-down = true` | For an effect applied with `.shader(_:)` that reads the view with `layer(uv)`. NucleantUI hands the view over top-down, and with this key `layer(uv)` reads it upright |

The other keys (`arguments`, `textures-top-down`, `optimize`, `site-packages` for imported shader libraries) are `pyshaderc`'s options. See [pyshader.toml](https://nucleantui.github.io/PyShader/compiler/plugins/#pyshadertoml).

---

## Package.swift: the build plugin

Add PyShader, and apply its build plugin to the app's target, on both sides of the Android switch:

```swift title="Package.swift" hl_lines="3 10 14 16"
let dependencies: [Package.Dependency] = [
    .package(url: "https://github.com/NucleantUI/NucleantUI.git", branch: "master"),
    .package(url: "https://github.com/NucleantUI/PyShader.git", .upToNextMinor(from: "0.0.8")),
]

let appDependencies: [Target.Dependency] = [
    .product(name: "NucleantUI", package: "NucleantUI"),
]

let shaderPlugins: [Target.PluginUsage] = [.plugin(name: "PyShaderBuildPlugin", package: "PyShader")]

let app: Target = isAndroid
    ? .target(name: "MyApp", dependencies: appDependencies, path: "Sources/MyApp",
              plugins: shaderPlugins)
    : .executableTarget(name: "MyApp", dependencies: appDependencies, path: "Sources/MyApp",
                        plugins: shaderPlugins)
```

The app links nothing from PyShader. The plugin's compiler, `pyshaderc`, is built for the build machine from source as part of the same build. Then each section of `pyshader.toml` becomes a `.spv` in the target's resource bundle.

- **macOS / Linux**: `swift run` compiles the shaders on every build.
- **Android**: the Gradle `swift build` builds the app's package, plugin included. The `.spv` files land in `MyApp_MyApp.resources`, which nucleant ships as assets and unpacks under `NUCLEANT_APP_PATH`.

A shader that doesn't compile fails the build with `Shaders/Glow.py:12: error: …`, which editors link to the line.

---

## iOS and the macOS .app: precompile

The Xcode project compiles `Sources/<target>` directly (see [iOS & macOS](../platforms/apple.md#the-generated-project)), so a plugin applied to the app target doesn't run there. For Xcode, compile the shaders ahead of time with the command plugin and commit the `.spv` files:

```bash
swift package --allow-writing-to-package-directory pyshader-compile          # every section
swift package --allow-writing-to-package-directory pyshader-compile Glow     # just these
```

To run it with the project's pinned Swift, use `swiftly run swift package --allow-writing-to-package-directory pyshader-compile +6.3.3`.

This writes each section's `output`, here `Sources/MyApp/Shaders/Glow.spv`. Files in `Sources/<target>` go into the Xcode app's bundle, and nucleant's `Bundle.module` for Xcode is `Bundle.main`, so the same lookup finds them.

The build plugin and the committed files mustn't both put a `Glow.spv` into the SwiftPM build. Exclude the committed folder where the plugin runs:

```swift title="Package.swift"
let app: Target = isAndroid
    ? .target(name: "MyApp", dependencies: appDependencies, path: "Sources/MyApp",
              exclude: ["Shaders"], plugins: shaderPlugins)
    : .executableTarget(name: "MyApp", dependencies: appDependencies, path: "Sources/MyApp",
                        exclude: ["Shaders"], plugins: shaderPlugins)
```

!!! tip "Only precompiled"
    If you would rather not compile shaders during builds at all, drop the plugin and declare the committed folder as resources: `resources: [.process("Shaders")]`. Every platform then ships the same `.spv` files, and you run `pyshader-compile` after changing a shader. NucleantTransitions does this for its WebAssembly build.

---

## Loading the module

On every platform except Android, `Bundle.module` finds the `.spv`. On Android, look it up under `NUCLEANT_APP_PATH`, in the target's `<Package>_<Target>.resources` (see [Resources](../configuration/package-swift.md#resources)):

```swift title="Sources/MyApp/ShaderModules.swift"
import Foundation

/// The app's compiled shaders, each read once.
@MainActor
enum ShaderModules {
    static let glow = load("Glow")

    /// `name`.spv from the target's resources, as SPIR-V words.
    private static func load(_ name: String) -> [UInt32] {
        guard let url = url(of: name), let data = try? Data(contentsOf: url) else {
            fatalError("\(name).spv is missing from the app's resources — is it in pyshader.toml?")
        }
        return data.withUnsafeBytes { Array($0.bindMemory(to: UInt32.self)) }
    }

    private static func url(of name: String) -> URL? {
        #if os(Android)
        // Not `Bundle.module`: on Android its accessor looks next to the
        // executable (the zygote's) and fatalErrors. nucleant unpacks the
        // resource bundles beside the app's files, at NUCLEANT_APP_PATH.
        guard let root = ProcessInfo.processInfo.environment["NUCLEANT_APP_PATH"] else { return nil }
        return URL(fileURLWithPath: "\(root)/MyApp_MyApp.resources/\(name).spv")
        #else
        return Bundle.module.url(forResource: name, withExtension: "spv")
        #endif
    }
}
```

## Using it

`SpirvFunction` runs the words. Its builder lists the input class's fields in order, here `intensity` (`float`) and `tint` (`float4`, which a `Color` fills):

```swift title="Sources/MyApp/GlowView.swift"
import NucleantUI

@View
struct GlowView {
    @State private var bright = false

    var body: some View {
        Shader(SpirvFunction(spirv: ShaderModules.glow, isAnimated: false) {
            Float(bright ? 1.5 : 0.8)
            Color.orange
        })
        .onTapGesture { bright.toggle() }
    }
}
```

`isAnimated: false` redraws only when the input changes. A shader that reads the clock or the pointer needs `true`. NucleantUI's `AnimatableShader` example drives a shader's input from an animation this way, and its DocC [documentation](https://nucleantui.github.io/NucleantUI/) covers `Shader`, `.shader(_:)` and the inputs.

---

## Shaders in a library package

A package that ships its own shaders works the same way: the plugin goes on the library target, and the `.spv` files go into the library's bundle. [NucleantTransitions](https://github.com/NucleantUI/NucleantTransitions) does this, with one `pyshader.toml` section per transition. An app that depends on such a package needs nothing extra: the package's plugin runs as part of building the package, in `swift run`, in Gradle and in Xcode.

## Shaders compiled at run time

For source the app only has while it runs (typed in, downloaded, generated), [NucleantUI_PyShader](https://github.com/NucleantUI/NucleantUI_PyShader)'s `PyShaderFunction` compiles PyShader inside the app. That puts the compiler in the app. Anything fixed at build time is better bundled as above.
