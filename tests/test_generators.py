"""The nucleantui bootstrap's three generators, driven with fake delegates."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nucleant.nucleant_toml import NucleantToml
from nucleant_bootstraps import get_bootstrap
from nucleant_bootstraps.bootstraps.nucleantui.swift_config import (
    SwiftConfigError,
    load_swift_config,
    portable_relpath,
)


class FakeGradleDelegate:
    def __init__(self, root: Path) -> None:
        self.working_dir = root
        self.swift_executable = "/opt/swift-6.3.3/usr/bin/swift"
        self.swift_env = {}
        self.swift_android_sdk = "swift-6.3.3-RELEASE_android"
        self.default_api_version = 36
        self.sdk_path = "/opt/android-sdk"
        self.ndk_version = "28.2.13676358"
        self.ndk_path = "/opt/android-sdk/ndk/28.2.13676358"
        self.java_path = "/opt/jdk"
        self.py_version = "3.13"
        self.android_py_version = "3.13.8"
        self.uv_py_version = "3.13.8"

    def install_cpython(self) -> None:
        raise AssertionError("Python layer must stay off")

    def android_prefix(self, root, arch, version):
        raise AssertionError("Python layer must stay off")


class FakeXcodeDelegate:
    def __init__(self, root: Path) -> None:
        self.working_dir = root
        self.swift_executable = "swift"
        self.swift_env = {}
        self.py_version = "3.13"
        self.uv_py_version = "3.13.11"
        self.generated: list[Path] = []

    def xcode_generate(self, *, spec_path: Path, project_dir: Path) -> None:
        self.generated.append(spec_path)
        (project_dir / "MyApp.xcodeproj").mkdir(exist_ok=True)

    def install_cpython(self) -> None:
        raise AssertionError("Python layer must stay off")


def test_android_project(project: Path):
    config = NucleantToml.load(project)
    delegate = FakeGradleDelegate(project)
    dist = project / "project_dist" / "gradle"
    # Pre-seed the wrapper so the generator does not download it.
    (dist / "gradle" / "wrapper").mkdir(parents=True)
    (dist / "gradle" / "wrapper" / "gradle-wrapper.jar").write_bytes(b"")
    (dist / "gradlew").write_text("")

    out = get_bootstrap("nucleantui", config, delegate).generate(platform="android", sdk_path="/opt/android-sdk")
    assert out == dist

    props = (dist / "gradle.properties").read_text()
    assert "swift.path=/opt/swift-6.3.3/usr/bin/swift" in props
    assert "swift.sdk=swift-6.3.3-RELEASE_android" in props

    build = (dist / "app" / "build.gradle.kts").read_text()
    assert 'applicationId = "org.example.myapp"' in build
    assert '"arm64-v8a" to "aarch64-unknown-linux-android28"' in build
    assert "swiftExecutable, \"build\"" in build
    assert "java.srcDir(nucleantJavaDir)" in build
    assert 'environment("NUCLEANT_ANDROID_USE_AHARDWAREBUFFER"' not in build  # only from [swift.env]
    assert "zipPythonAssets" not in build  # Python layer off
    # Empty when nothing is a path dependency: Kotlin can't infer `listOf()`.
    assert "val vendoredNativeRoots = listOf<String>(\n\n)" in build
    assert "val swiftRuntimeLibs = listOf<String>(" in build

    activity = (dist / "app/src/main/java/org/example/myapp/MainActivity.java").read_text()
    assert "extends NucleantActivity" in activity
    assert "AppMain.nucleantRunMain(appPath)" in activity

    swift_pkg = dist / "swift"
    manifest = (swift_pkg / "Package.swift").read_text()
    assert 'package(url: "https://github.com/NucleantUI/NucleantUI.git", branch: "master")' in manifest
    assert (swift_pkg / "Sources/AppMain/App/MyAppApp.swift").read_text() == "// app\n"
    entry = (swift_pkg / "Sources/AppMain/AppMain.swift").read_text()
    assert "AppRuntime(app: MyAppApp())" in entry
    assert '"javaPackage": "org.nucleantui"' in (swift_pkg / "Sources/AppMain/swift-java.config").read_text()


def test_android_env_reaches_swift_build(project: Path):
    toml = project / "nucleant.toml"
    toml.write_text(toml.read_text().replace(
        '# NUCLEANT_ANDROID_USE_AHARDWAREBUFFER = "1"', 'NUCLEANT_ANDROID_USE_AHARDWAREBUFFER = "1"'
    ))
    dist = project / "project_dist" / "gradle"
    (dist / "gradle" / "wrapper").mkdir(parents=True)
    (dist / "gradle" / "wrapper" / "gradle-wrapper.jar").write_bytes(b"")
    (dist / "gradlew").write_text("")
    config = NucleantToml.load(project)
    get_bootstrap("nucleantui", config, FakeGradleDelegate(project)).generate(
        platform="android", sdk_path="/opt/android-sdk"
    )
    build = (dist / "app" / "build.gradle.kts").read_text()
    assert 'environment("NUCLEANT_ANDROID_USE_AHARDWAREBUFFER", "1")' in build


def test_xcode_spec(project: Path):
    config = NucleantToml.load(project)
    delegate = FakeXcodeDelegate(project)
    bootstrap = get_bootstrap("nucleantui", config, delegate)
    xcodeproj = bootstrap.generate(platform="apple")
    assert xcodeproj == project / "project_dist/xcode/MyApp.xcodeproj"

    spec = yaml.safe_load((project / "project_dist/xcode/project.yml").read_text())
    target = spec["targets"]["MyApp"]
    assert target["supportedDestinations"] == ["iOS", "macOS"]
    assert {"path": "../../Sources/MyApp"} in target["sources"]
    assert target["dependencies"] == [{"package": "NucleantUI", "product": "NucleantUI"}]
    assert spec["packages"]["NucleantUI"] == {
        "url": "https://github.com/NucleantUI/NucleantUI.git",
        "branch": "master",
    }
    assert spec["options"]["deploymentTarget"] == {"iOS": "17.0", "macOS": "14.0"}
    assert target["settings"]["base"]["PRODUCT_BUNDLE_IDENTIFIER"] == "org.example.myapp"
    assert target["info"]["properties"]["CFBundleVersion"] == "$(CURRENT_PROJECT_VERSION)"

    # Unchanged spec: xcodegen is not re-run.
    bootstrap.generate(platform="apple")
    assert len(delegate.generated) == 1


def test_desktop_package_left_alone_when_foreign(project: Path):
    (project / "Package.swift").write_text("// swift-tools-version: 6.2\n// mine\n")
    config = NucleantToml.load(project)
    get_bootstrap("nucleantui", config, FakeXcodeDelegate(project)).generate(platform="desktop")
    assert (project / "Package.swift").read_text().endswith("// mine\n")


def test_desktop_rejects_sources_outside_package(tmp_path: Path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    root = tmp_path / "App"
    root.mkdir()
    (root / "nucleant.toml").write_text(f'app_name = "App"\n[swift]\nsources = ["{outside}"]\n')
    config = NucleantToml.load(root)
    with pytest.raises(SwiftConfigError, match="outside"):
        get_bootstrap("nucleantui", config, FakeXcodeDelegate(root)).generate(platform="desktop")


def test_dependency_rendering(tmp_path: Path):
    dep_dir = tmp_path / "pkgs" / "Thing"
    dep_dir.mkdir(parents=True)
    root = tmp_path / "pkgs" / "App"
    (root / "Sources" / "App").mkdir(parents=True)
    data = {
        "swift": {
            "dependencies": [
                {"name": "Thing", "path": "../Thing"},
                {"name": "Pinned", "url": "https://x/Pinned.git", "exact": "1.2.3", "products": ["A", "B"]},
                {"name": "Floor", "url": "https://x/Floor.git", "up_to_major": "0.1.0"},
            ]
        }
    }
    swift = load_swift_config(root, data, "App")
    ui, thing, pinned, floor = swift.dependencies
    assert ui.as_package_dependency() == (
        '.package(url: "https://github.com/NucleantUI/NucleantUI.git", branch: "master")'
    )
    assert thing.as_package_dependency(root) == '.package(path: "../Thing")'
    assert pinned.as_package_dependency() == '.package(url: "https://x/Pinned.git", exact: "1.2.3")'
    assert pinned.as_target_dependencies() == [
        '.product(name: "A", package: "Pinned")',
        '.product(name: "B", package: "Pinned")',
    ]
    assert floor.as_package_dependency() == '.package(url: "https://x/Floor.git", from: "0.1.0")'
    assert floor.as_xcodegen_package(root) == {"url": "https://x/Floor.git", "from": "0.1.0"}
    assert swift.sources == (root / "Sources" / "App",)  # default when it exists


@pytest.mark.parametrize(
    ("table", "package", "target"),
    [
        ({}, '.package(url: "https://github.com/NucleantUI/NucleantUI.git", branch: "master")',
         '.product(name: "NucleantUI", package: "NucleantUI")'),
        ({"up_to_major": "0.2.0"}, '.package(url: "https://github.com/NucleantUI/NucleantUI.git", from: "0.2.0")',
         '.product(name: "NucleantUI", package: "NucleantUI")'),
        ({"exact": "0.2.1"}, '.package(url: "https://github.com/NucleantUI/NucleantUI.git", exact: "0.2.1")',
         '.product(name: "NucleantUI", package: "NucleantUI")'),
        ({"url": "https://github.com/me/MyUI.git", "branch": "fix"},
         '.package(url: "https://github.com/me/MyUI.git", branch: "fix")',
         '.product(name: "NucleantUI", package: "MyUI")'),
    ],
)
def test_nucleantui_table(tmp_path: Path, table: dict, package: str, target: str):
    ui = load_swift_config(tmp_path, {"nucleantui": table}, "App").dependencies[0]
    assert ui.as_package_dependency() == package
    assert ui.as_target_dependencies() == [target]


def test_nucleantui_local_fork(tmp_path: Path):
    fork = tmp_path / "forks" / "NucleantUI"
    fork.mkdir(parents=True)
    root = tmp_path / "App"
    root.mkdir()
    ui = load_swift_config(root, {"nucleantui": {"path": "../forks/NucleantUI"}}, "App").dependencies[0]
    assert ui.as_package_dependency(root) == '.package(path: "../forks/NucleantUI")'
    assert ui.as_xcodegen_package(root) == {"path": "../forks/NucleantUI"}


@pytest.mark.parametrize(
    ("data", "match"),
    [
        ({"nucleantui": {"branch": "master", "exact": "0.1.0"}}, "not branch and exact"),
        ({"nucleantui": {"from": "0.1.0"}}, "spelled 'up_to_major'"),
        ({"nucleantui": {"version": "0.1.0"}}, "unknown key"),
        ({"nucleantui": {"path": ".", "branch": "master"}}, "takes no url or version"),
        ({"swift": {"dependencies": [{"name": "NucleantUI", "url": "https://x/NucleantUI.git",
                                      "branch": "master"}]}}, r"\[nucleantui\] instead"),
    ],
)
def test_nucleantui_table_errors(tmp_path: Path, data: dict, match: str):
    with pytest.raises(SwiftConfigError, match=match):
        load_swift_config(tmp_path, data, "App")


def test_portable_relpath():
    assert portable_relpath(Path("/a/b/c"), Path("/a/d")) == "../b/c"
    assert portable_relpath(Path("/Users/x/ui"), Path("/private/tmp/app")) == "/Users/x/ui"


def test_android_vendored_roots_from_path_dependency(project: Path, tmp_path: Path):
    """A path dependency's siblings with Android artifacts are listed as paths."""
    vendored = tmp_path / "deps" / "NucleantThing" / "Dependencies" / "android"
    (vendored / "x86_64" / "lib").mkdir(parents=True)
    fork = tmp_path / "deps" / "NucleantUI"
    fork.mkdir(parents=True)
    toml = project / "nucleant.toml"
    toml.write_text(toml.read_text().replace(
        '[nucleantui]\nbranch = "master"\n', f'[nucleantui]\npath = "{fork}"\n'
    ))
    dist = project / "project_dist" / "gradle"
    (dist / "gradle" / "wrapper").mkdir(parents=True)
    (dist / "gradle" / "wrapper" / "gradle-wrapper.jar").write_bytes(b"")
    (dist / "gradlew").write_text("")
    config = NucleantToml.load(project)
    get_bootstrap("nucleantui", config, FakeGradleDelegate(project)).generate(
        platform="android", sdk_path="/opt/android-sdk"
    )
    build = (dist / "app" / "build.gradle.kts").read_text()
    assert f'val vendoredNativeRoots = listOf<String>(\n    "{vendored}",\n)' in build
