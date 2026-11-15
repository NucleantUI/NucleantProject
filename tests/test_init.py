from __future__ import annotations

from pathlib import Path

from nucleant.nucleant_toml import NucleantToml
from nucleant.project_init import ProjectInit


def _init(root: Path, **kw) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0"\n')
    ProjectInit(root, **kw).run()


def test_init_writes_a_project(tmp_path: Path):
    root = tmp_path / "Hello World"
    _init(root, app_name="Hello World")

    config = NucleantToml.load(root)
    assert config.app_name == "Hello World"
    assert config.name == "hello_world"
    assert config.data["swift"]["target"] == "HelloWorld"
    assert config.data["swift"]["entry"] == "HelloWorldApp"

    app = root / "Sources" / "HelloWorld" / "HelloWorldApp.swift"
    assert "@main\npublic struct HelloWorldApp: NucleantApp {\n    public init() {}" in app.read_text()
    assert "@View\nstruct ContentView" in app.read_text()
    assert (root / ".swift-version").read_text().strip() == "6.3.3"
    assert (root / "build.tmpl.gradle.kts").read_text().startswith("// nucleant-template: 1")
    assert "nucleant-template: 1" in (root / "AndroidManifest.tmpl.xml").read_text()
    # The app's package is the project's own: no generated marker, the app a
    # library under ANDROID_BUILD and an executable otherwise.
    manifest = (root / "Package.swift").read_text()
    assert "nucleant:generated-swift-package" not in manifest
    assert 'environment["ANDROID_BUILD"] != nil' in manifest
    assert '? .target(name: "HelloWorld", dependencies: appDependencies, path: "Sources/HelloWorld")' in manifest
    assert ': .executableTarget(name: "HelloWorld"' in manifest
    assert '? .library(name: "HelloWorld", targets: ["HelloWorld"])' in manifest
    assert '.package(url: "https://github.com/NucleantUI/NucleantUI.git", branch: "master")' in manifest
    toml = (root / "nucleant.toml").read_text()
    assert "[nucleantui]" not in toml and "swift.dependencies" not in toml
    assert "project_dist/" in (root / ".gitignore").read_text()


def test_init_never_overwrites(tmp_path: Path):
    root = tmp_path / "App"
    root.mkdir()
    (root / "nucleant.toml").write_text('app_name = "Mine"\n[swift]\ntarget = "App"\n')
    (root / "Package.swift").write_text("// mine\n")
    (root / "Sources" / "App").mkdir(parents=True)
    (root / "Sources" / "App" / "Mine.swift").write_text("// mine\n")
    (root / ".gitignore").write_text("node_modules/\n.build/\n")
    _init(root)

    assert (root / "nucleant.toml").read_text().startswith('app_name = "Mine"')
    assert (root / "Sources" / "App" / "Mine.swift").read_text() == "// mine\n"
    assert not (root / "Sources" / "App" / "AppApp.swift").exists()
    assert (root / "Package.swift").read_text() == "// mine\n"
    gitignore = (root / ".gitignore").read_text()
    assert gitignore.startswith("node_modules/\n.build/\n")
    assert gitignore.count(".build/") == 1 and "project_dist/" in gitignore

