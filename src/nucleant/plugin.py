"""Third-party command groups, listed in nucleant.toml::

    command_plugins = ["my_package.nucleant_plugin"]

Each module exposes ``plugin`` with a ``register(subparsers)`` method.
"""

from __future__ import annotations

import argparse
import importlib
import tomllib
from pathlib import Path
from typing import Protocol

from .nucleant_toml import NUCLEANT_TOML


class CommandPlugin(Protocol):
    def register(self, subparsers: argparse._SubParsersAction) -> None: ...


def load_plugins(project_path: Path | None = None) -> list[CommandPlugin]:
    toml_path = (project_path or Path.cwd()) / NUCLEANT_TOML
    if not toml_path.is_file():
        return []
    try:
        with toml_path.open("rb") as f:
            names = tomllib.load(f).get("command_plugins", [])
    except tomllib.TOMLDecodeError:
        return []  # reported properly by the command that loads the project
    return [importlib.import_module(name).plugin for name in names]
