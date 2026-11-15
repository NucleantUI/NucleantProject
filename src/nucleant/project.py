"""What every platform command starts from: the project, its config, its Swift.

``NucleantProject`` loads ``nucleant.toml`` and resolves the Swift toolchain on
first use (so commands that never compile Swift never install it). The
platform projects — desktop here, Gradle and Xcode in their packages — add
their own delegate for the bootstrap.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from nucleant_bootstraps import get_bootstrap
from nucleant_bootstraps.bootstrap import BootstrapProtocol

from .nucleant_toml import NucleantToml
from .swift import SwiftToolchain, resolve_swift_toolchain


class NucleantProjectError(Exception):
    pass


class NucleantProject:

    config: NucleantToml

    def __init__(self, project_path: Path | None = None) -> None:
        self.project_path = Path(project_path or Path.cwd()).resolve()
        self.config = NucleantToml.load(self.project_path)
        self._swift: SwiftToolchain | None = None

    @property
    def swift(self) -> SwiftToolchain:
        """The pinned Swift toolchain (installed with swiftly if missing)."""
        if self._swift is None:
            self._swift = resolve_swift_toolchain(self.config.toolchain)
            print(f"[nucleant] {self._swift.describe()}")
        return self._swift

    def make_bootstrap(self, delegate) -> BootstrapProtocol:
        return get_bootstrap(self.config.bootstrap, self.config, delegate)


class SwiftDelegate:
    """The delegate shape every bootstrap needs: where, and which ``swift``."""

    def __init__(self, project: NucleantProject) -> None:
        self._project = project

    @property
    def working_dir(self) -> Path:
        return self._project.project_path

    @property
    def swift_executable(self) -> str:
        return self._project.swift.swift

    @property
    def swift_env(self) -> dict[str, str]:
        return {}


class DesktopProject(NucleantProject):
    """macOS and Linux through SwiftPM: ``swift run`` builds and runs."""

    def __init__(self, project_path: Path | None = None) -> None:
        super().__init__(project_path)
        self.bootstrap = self.make_bootstrap(SwiftDelegate(self))

    def generate(self, init: bool = False) -> Path:
        """The app's own package. ``init``: write the starter Package.swift
        when the project has none; otherwise one has to be there."""
        package = self.bootstrap.generate(platform="desktop", init=init)
        assert package is not None
        return package

    def run(
        self,
        host: str,
        configuration: str = "debug",
        app_args: list[str] | None = None,
    ) -> int:
        expected = {"macos": "darwin", "linux": "linux"}[host]
        if sys.platform != expected:
            raise NucleantProjectError(
                f"`nucleant {'apple macos' if host == 'macos' else 'linux'} run` builds "
                f"for the machine it runs on, and this is {sys.platform}. "
                "Cross-compiling a desktop app is not supported."
            )
        if host == "linux" and not self.config.has_linux:
            print("[nucleant] note: nucleant.toml has no [linux] table; running anyway.")
        package = self.generate()
        product = self.bootstrap.app_target()
        # Everything after the product name goes to the app.
        args = ["run", "-c", configuration, product, *(app_args or [])]
        return self.swift.run(
            args, cwd=package, extra_env=self.bootstrap.build_env(), check=False
        )


def merged_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env.update(extra or {})
    return env
