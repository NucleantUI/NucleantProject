"""The nucleantui bootstrap's three generators, driven with fake delegates."""

from __future__ import annotations

from pathlib import Path

import re
import shutil
import subprocess

import pytest
import yaml

from conftest import app_dump, fake_swift
from nucleant.nucleant_toml import NucleantToml
from nucleant_bootstraps import get_bootstrap
from nucleant_bootstraps.bootstraps.nucleantui.root_package import (
    PackageDependency,
    root_package_swift,
)
from nucleant_bootstraps.bootstraps.nucleantui.swift_config import (
    SwiftConfigError,
    load_swift_config,
    portable_relpath,
)


class FakeGradleDelegate:
    def __init__(self, root: Path, swift: str = "/opt/swift-6.3.3/usr/bin/swift") -> None:
        self.working_dir = root
        self.swift_executable = swift
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
    def __init__(self, root: Path, swift: str = "swift") -> None:
        self.working_dir = root
        self.swift_executable = swift
        self.swift_env = {}
        self.py_version = "3.13"
        self.uv_py_version = "3.13.11"
        self.generated: list[Path] = []

    def xcode_generate(self, *, spec_path: Path, project_dir: Path) -> None:
        self.generated.append(spec_path)
        (project_dir / "MyApp.xcodeproj").mkdir(exist_ok=True)

    def install_cpython(self) -> None:
        raise AssertionError("Python layer must stay off")


def _seed_wrapper(project: Path) -> Path:
    """Pre-seed the Gradle wrapper so the generator does not download it."""
    dist = project / "project_dist" / "gradle"
    (dist / "gradle" / "wrapper").mkdir(parents=True, exist_ok=True)
    (dist / "gradle" / "wrapper" / "gradle-wrapper.jar").write_bytes(b"")
    (dist / "gradlew").write_text("")
    return dist


def _android(project: Path, tmp_path: Path, **dump) -> Path:
    swift = fake_swift(
        tmp_path / "bin",
        android=app_dump(library=True, **dump),
        apple=app_dump(library=False, **dump),
    )
    dist = _seed_wrapper(project)
    config = NucleantToml.load(project)
    get_bootstrap("nucleantui", config, FakeGradleDelegate(project, swift)).generate(
        platform="android", sdk_path="/opt/android-sdk"
    )
    return dist


def test_android_project(project: Path, tmp_path: Path):
    swift = fake_swift(
        tmp_path / "bin", android=app_dump(library=True), apple=app_dump(library=False)
    )
    config = NucleantToml.load(project)
    delegate = FakeGradleDelegate(project, swift)
    dist = _seed_wrapper(project)

    out = get_bootstrap("nucleantui", config, delegate).generate(platform="android", sdk_path="/opt/android-sdk")
    assert out == dist

    props = (dist / "gradle.properties").read_text()
    assert f"swift.path={swift}" in props
    assert "swift.sdk=swift-6.3.3-RELEASE_android" in props

    build = (dist / "app" / "build.gradle.kts").read_text()
    assert 'applicationId = "org.example.myapp"' in build
    assert '"arm64-v8a" to "aarch64-unknown-linux-android28"' in build
    assert "swiftExecutable, \"build\"" in build
    assert 'environment("ANDROID_BUILD", "1")' in build
    assert "java.srcDir(nucleantJavaDir)" in build
    assert 'environment("NUCLEANT_ANDROID_USE_AHARDWAREBUFFER"' not in build  # only from [swift.env]
    assert "zipPythonAssets" not in build  # Python layer off
    # Empty when nothing is a path dependency: Kotlin can't infer `listOf()`.
    assert "val vendoredNativeRoots = listOf<String>(\n\n)" in build
    assert "val swiftRuntimeLibs = listOf<String>(" in build

    activity = (dist / "app/src/main/java/org/example/myapp/MainActivity.java").read_text()
    assert "extends NucleantActivity" in activity
    assert "AppMain.nucleantRunMain(appPath)" in activity

    # The Android package is swift-java plus the project's own package, by
    # path: no dependency of the app is repeated in it, no source copied.
    swift_pkg = dist / "swift"
    manifest = (swift_pkg / "Package.swift").read_text()
    assert '.package(path: "../../..")' in manifest
    assert '.product(name: "MyApp", package: "myapp")' in manifest
    assert "NucleantUI.git" not in manifest
    assert not (swift_pkg / "Sources/AppMain/App").exists()
    entry = (swift_pkg / "Sources/AppMain/AppMain.swift").read_text()
    assert "import NucleantUI\nimport MyApp\n" in entry
    assert "AppRuntime(app: MyAppApp())" in entry
    assert '"javaPackage": "org.nucleantui"' in (swift_pkg / "Sources/AppMain/swift-java.config").read_text()


def test_android_removes_copied_app_sources(project: Path, tmp_path: Path):
    """Earlier versions copied the app's Swift into AppMain/App; a leftover
    copy would define every type twice next to the root package's."""
    stale = project / "project_dist/gradle/swift/Sources/AppMain/App"
    stale.mkdir(parents=True)
    (stale / "MyAppApp.swift").write_text("// old copy\n")
    _android(project, tmp_path)
    assert not stale.exists()


def test_android_needs_the_app_as_a_library(project: Path, tmp_path: Path):
    swift = fake_swift(
        tmp_path / "bin", android=app_dump(library=False), apple=app_dump(library=False)
    )
    _seed_wrapper(project)
    config = NucleantToml.load(project)
    with pytest.raises(SwiftConfigError, match="executable product named 'MyApp' when ANDROID_BUILD"):
        get_bootstrap("nucleantui", config, FakeGradleDelegate(project, swift)).generate(
            platform="android", sdk_path="/opt/android-sdk"
        )


def test_android_env_reaches_swift_build(project: Path, tmp_path: Path):
    toml = project / "nucleant.toml"
    toml.write_text(toml.read_text().replace(
        '# NUCLEANT_ANDROID_USE_AHARDWAREBUFFER = "1"', 'NUCLEANT_ANDROID_USE_AHARDWAREBUFFER = "1"'
    ))
    dist = _android(project, tmp_path)
    build = (dist / "app" / "build.gradle.kts").read_text()
    assert 'environment("NUCLEANT_ANDROID_USE_AHARDWAREBUFFER", "1")' in build


def test_android_vendored_roots_from_path_dependency(project: Path, tmp_path: Path):
    """A path dependency's siblings with Android artifacts are listed as paths."""
    vendored = tmp_path / "deps" / "NucleantThing" / "Dependencies" / "android"
    (vendored / "x86_64" / "lib").mkdir(parents=True)
    fork = tmp_path / "deps" / "NucleantUI"
    fork.mkdir(parents=True)
    local_ui = {"fileSystem": [{"identity": "nucleantui", "path": str(fork), "productFilter": None}]}
    dist = _android(project, tmp_path, dependencies=[local_ui])
    build = (dist / "app" / "build.gradle.kts").read_text()
    assert f'val vendoredNativeRoots = listOf<String>(\n    "{vendored}",\n)' in build


def test_xcode_spec(project: Path, tmp_path: Path):
    floor = {"sourceControl": [{
        "identity": "nucleantvlc",
        "location": {"remote": [{"urlString": "https://github.com/NucleantUI/NucleantVLC"}]},
        "requirement": {"range": [{"lowerBound": "0.3.1", "upperBound": "0.4.0"}]},
    }]}
    from conftest import NUCLEANTUI

    dump = app_dump(
        library=False,
        dependencies=[NUCLEANTUI, floor],
        products=(("NucleantUI", "NucleantUI"), ("NucleantVLC", "NucleantVLC")),
    )
    swift = fake_swift(tmp_path / "bin", android=app_dump(library=True), apple=dump)
    config = NucleantToml.load(project)
    delegate = FakeXcodeDelegate(project, swift)
    bootstrap = get_bootstrap("nucleantui", config, delegate)
    xcodeproj = bootstrap.generate(platform="apple")
    assert xcodeproj == project / "project_dist/xcode/MyApp.xcodeproj"

    spec = yaml.safe_load((project / "project_dist/xcode/project.yml").read_text())
    target = spec["targets"]["MyApp"]
    assert target["supportedDestinations"] == ["iOS", "macOS"]
    assert {"path": "../../Sources/MyApp"} in target["sources"]
    assert target["dependencies"] == [
        {"package": "NucleantUI", "product": "NucleantUI"},
        {"package": "NucleantVLC", "product": "NucleantVLC"},
    ]
    assert spec["packages"] == {
        "NucleantUI": {"url": "https://github.com/NucleantUI/NucleantUI.git", "branch": "master"},
        "NucleantVLC": {"url": "https://github.com/NucleantUI/NucleantVLC", "minorVersion": "0.3.1"},
    }
    assert spec["options"]["deploymentTarget"] == {"iOS": "17.0", "macOS": "14.0"}
    assert target["settings"]["base"]["PRODUCT_BUNDLE_IDENTIFIER"] == "org.example.myapp"
    assert target["info"]["properties"]["CFBundleVersion"] == "$(CURRENT_PROJECT_VERSION)"

    # Unchanged spec: xcodegen is not re-run.
    bootstrap.generate(platform="apple")
    assert len(delegate.generated) == 1


@pytest.mark.parametrize(
    ("requirement", "spec"),
    [
        ({"branch": ["master"]}, {"branch": "master"}),
        ({"exact": ["1.2.3"]}, {"exactVersion": "1.2.3"}),
        ({"revision": ["abc"]}, {"revision": "abc"}),
        ({"range": [{"lowerBound": "1.2.0", "upperBound": "2.0.0"}]}, {"from": "1.2.0"}),
        ({"range": [{"lowerBound": "0.3.1", "upperBound": "0.4.0"}]}, {"minorVersion": "0.3.1"}),
        ({"range": [{"lowerBound": "1.0.0", "upperBound": "1.5.0"}]},
         {"minVersion": "1.0.0", "maxVersion": "1.5.0"}),
    ],
)
def test_xcodegen_requirements(requirement: dict, spec: dict):
    dep = PackageDependency("x", None, None, "https://x/X.git", requirement)
    assert dep.as_xcodegen_package(Path("/p")) == {"url": "https://x/X.git", **spec}


def test_desktop_package_is_never_rewritten(project: Path):
    config = NucleantToml.load(project)
    out = get_bootstrap("nucleantui", config, FakeXcodeDelegate(project)).generate(
        platform="desktop", init=True
    )
    assert out == project
    assert (project / "Package.swift").read_text().endswith("// the app's own\n")


def test_desktop_needs_a_package(project: Path):
    (project / "Package.swift").unlink()
    config = NucleantToml.load(project)
    with pytest.raises(SwiftConfigError, match="nucleant init"):
        get_bootstrap("nucleantui", config, FakeXcodeDelegate(project)).generate(platform="desktop")


@pytest.mark.parametrize(
    ("data", "match"),
    [
        ({"nucleantui": {"branch": "master"}}, r"\[nucleantui\] is gone"),
        ({"swift": {"dependencies": []}}, r"\[\[swift.dependencies\]\] is gone"),
        ({"swift": {"sources": ["Sources/App"], "unsafe_flags": []}},
         r"\[swift\] sources, \[swift\] unsafe_flags are gone"),
    ],
)
def test_package_keys_moved_to_package_swift(tmp_path: Path, data: dict, match: str):
    with pytest.raises(SwiftConfigError, match=match):
        load_swift_config(tmp_path, data, "App")


def test_portable_relpath():
    assert portable_relpath(Path("/a/b/c"), Path("/a/d")) == "../b/c"
    assert portable_relpath(Path("/Users/x/ui"), Path("/private/tmp/app")) == "/Users/x/ui"


def _real_swift() -> str | None:
    swift = shutil.which("swift")
    if swift is None:
        return None
    out = subprocess.run([swift, "--version"], capture_output=True, text=True).stdout
    match = re.search(r"Swift version (\d+)\.(\d+)", out)
    return swift if match and (int(match[1]), int(match[2])) >= (6, 2) else None


@pytest.mark.skipif(_real_swift() is None, reason="needs swift 6.2+")
def test_starter_package_is_a_library_only_under_android_build(tmp_path: Path):
    """The Package.swift `nucleant init` writes, evaluated by SwiftPM itself."""
    from nucleant_bootstraps.bootstraps.nucleantui.root_package import dump_root_package

    root = tmp_path / "my-app"
    (root / "Sources" / "MyApp").mkdir(parents=True)
    swift = load_swift_config(root, {"swift": {"entry": "MyAppApp"}}, "MyApp")
    (root / "Package.swift").write_text(root_package_swift(swift))
    real = _real_swift()
    assert real is not None

    android = dump_root_package(swift, real, {"ANDROID_BUILD": "1"})
    assert android.products == {"MyApp": "library"}
    assert android.targets["MyApp"].type == "regular"
    assert swift.root_identity == "my-app"

    desktop = dump_root_package(swift, real)
    assert desktop.products == {"MyApp": "executable"}
    assert desktop.targets["MyApp"].products == (("NucleantUI", "NucleantUI"),)
    assert desktop.dependency("NucleantUI").as_xcodegen_package(root) == {
        "url": "https://github.com/NucleantUI/NucleantUI.git",
        "branch": "master",
    }
