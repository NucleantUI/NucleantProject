from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from nucleant import init_template, nucleant_toml
from nucleant.nucleant_toml import NucleantToml, NucleantTomlError


def test_init_template_is_valid_toml_and_loads(project: Path):
    config = NucleantToml.load(project)
    assert config.app_name == "MyApp"
    assert config.name == "myapp"
    assert config.bootstrap == "nucleantui"
    assert config.toolchain.swift == "6.3.3"
    assert config.toolchain.swiftly is True
    assert config.android is not None
    assert config.android.package_name == "org.example.myapp"
    assert [a.value for a in config.android.archs] == ["arm64-v8a"]
    assert config.android.min_api == 28
    assert config.apple is not None and config.apple.ios and config.apple.macos
    assert config.apple.ios.minimum_deployment == "17.0"
    assert config.has_linux and not config.has_wasm
    assert config.python_enabled is False


def test_template_uses_nucleantui_from_github():
    text = init_template.nucleant_toml("A", "a", "A", "AApp")
    data = tomllib.loads(text)
    assert data["swift"]["env"] == {}
    assert data["swift"]["dependencies"] == [{
        "name": "NucleantUI",
        "url": "https://github.com/NucleantUI/NucleantUI.git",
        "branch": "master",
        "products": ["NucleantUI"],
    }]
    assert "LOCAL_DEV" not in text


def test_missing_file_is_a_clear_error(tmp_path: Path):
    with pytest.raises(NucleantTomlError, match="nucleant init"):
        NucleantToml.load(tmp_path)


def test_bad_arch_is_rejected(tmp_path: Path):
    (tmp_path / "nucleant.toml").write_text('[android]\npackage_name = "a.b"\narchs = ["armeabi-v7a"]\n')
    with pytest.raises(NucleantTomlError, match="archs"):
        NucleantToml.load(tmp_path)


def test_tools_root(tmp_path: Path):
    from nucleant.nucleant_toml import AndroidData

    assert AndroidData({"package_name": "a.b"}).tools_root(tmp_path) == tmp_path / ".nucleant"
    assert AndroidData({"package_name": "a.b", "global_tools": True}).tools_root(tmp_path) == Path.home() / ".nucleant"
    custom = AndroidData({"package_name": "a.b", "global_tools": True, "global_tools_path": "~/x"})
    assert custom.tools_root(tmp_path) == Path.home() / "x"


def test_python_layer_needs_the_cli_switch(tmp_path: Path, monkeypatch, capsys):
    (tmp_path / "nucleant.toml").write_text('app_name = "A"\n[python]\nenabled = true\n')
    config = NucleantToml.load(tmp_path)
    assert config.python.enabled is True
    assert config.python_enabled is False  # PYTHON_SUPPORT_ENABLED is off
    assert "switched off" in capsys.readouterr().out

    monkeypatch.setattr(nucleant_toml, "PYTHON_SUPPORT_ENABLED", True)
    assert config.python_enabled is True
