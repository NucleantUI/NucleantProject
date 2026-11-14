from __future__ import annotations

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
    return root
