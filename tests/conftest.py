from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from nucleant import init_template


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A minimal NucleantProject: nucleant.toml + one Swift source dir."""
    root = tmp_path / "MyApp"
    (root / "Sources" / "MyApp").mkdir(parents=True)
    (root / "Sources" / "MyApp" / "MyAppApp.swift").write_text("// app\n")
    (root / "pyproject.toml").write_text('[project]\nname = "my-app"\nversion = "0.1.0"\n')
    (root / "nucleant.toml").write_text(
        init_template.nucleant_toml("MyApp", "myapp", "MyApp", "MyAppApp")
    )
    (root / "Package.swift").write_text("// swift-tools-version: 6.2\n// the app's own\n")
    return root


# ---------------------------------------------------------------------------
# `swift package dump-package`, faked: the generators read the project's own
# Package.swift through it, and these tests should not need a toolchain.
# ---------------------------------------------------------------------------

NUCLEANTUI = {
    "sourceControl": [{
        "identity": "nucleantui",
        "location": {"remote": [{"urlString": "https://github.com/NucleantUI/NucleantUI.git"}]},
        "productFilter": None,
        "requirement": {"branch": ["master"]},
    }]
}


def app_dump(
    target: str = "MyApp",
    *,
    library: bool,
    dependencies: list | None = None,
    products: tuple = (("NucleantUI", "NucleantUI"),),
) -> dict:
    """dump-package's JSON for a package shaped like the `nucleant init` one."""
    return {
        "name": target,
        "dependencies": [NUCLEANTUI] if dependencies is None else dependencies,
        "products": [{
            "name": target,
            "targets": [target],
            "settings": [],
            "type": {"library": ["automatic"]} if library else {"executable": None},
        }],
        "targets": [{
            "name": target,
            "type": "regular" if library else "executable",
            "path": f"Sources/{target}",
            "dependencies": [{"product": [p, pkg, None, None]} for p, pkg in products],
            "settings": [],
        }],
    }


def fake_swift(directory: Path, *, android: dict, apple: dict) -> str:
    """A `swift` that answers dump-package with ``android`` when ANDROID_BUILD
    is set and ``apple`` otherwise."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "dump-android.json").write_text(json.dumps(android))
    (directory / "dump-apple.json").write_text(json.dumps(apple))
    script = directory / "swift"
    script.write_text(
        f"#!{sys.executable}\n"
        "import os, pathlib, sys\n"
        "assert sys.argv[1:3] == ['package', 'dump-package'], sys.argv\n"
        "name = 'dump-android.json' if os.environ.get('ANDROID_BUILD') else 'dump-apple.json'\n"
        "sys.stdout.write((pathlib.Path(__file__).parent / name).read_text())\n"
    )
    script.chmod(0o755)
    return str(script)
