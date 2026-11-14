"""The ``nucleant`` command."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .commands.android import AndroidCommands
from .commands.apple import AppleCommands
from .commands.linux import LinuxCommands
from .commands.toolchain import ToolchainCommands
from .tools import load_dotenv

#: Errors that are the user's to fix: printed without a traceback
#: (NUCLEANT_DEBUG=1 shows it anyway).
_USER_ERRORS: tuple[type[BaseException], ...] = ()


def _user_errors() -> tuple[type[BaseException], ...]:
    global _USER_ERRORS
    if not _USER_ERRORS:
        from nucleant_bootstraps import BootstrapError
        from nucleant_bootstraps.bootstraps.nucleantui.swift_config import SwiftConfigError
        from nucleant_bootstraps.bootstraps.nucleantui.xcode_builder import XcodeBuilderError

        from .gradle.adb import ADBError
        from .gradle.android_emulator import AndroidEmulatorError
        from .gradle.android_toolchain import AndroidToolchainError
        from .gradle.gradle_project import GradleProjectError
        from .nucleant_toml import NucleantTomlError
        from .project import NucleantProjectError
        from .project_init import ProjectInitError
        from .swift import SwiftlyError, SwiftSdkError, SwiftToolchainError
        from .xcode.xcode_project import XcodeProjectError
        from .xcode.xcodegen_runner import XcodeGenError

        _USER_ERRORS = (
            ADBError, AndroidEmulatorError, AndroidToolchainError, BootstrapError,
            GradleProjectError, NucleantProjectError, NucleantTomlError, ProjectInitError,
            SwiftConfigError, SwiftlyError, SwiftSdkError, SwiftToolchainError,
            XcodeBuilderError, XcodeGenError, XcodeProjectError,
        )
    return _USER_ERRORS


class NucleantCLI:

    def __init__(self) -> None:
        self.parser = self._build_parser()

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="nucleant",
            description="Build and run NucleantUI apps on Android, iOS, macOS and Linux.",
        )
        parser.add_argument("--version", action="version", version=f"nucleant {__version__}")
        sub = parser.add_subparsers(dest="subsystem", required=True)

        p_init = sub.add_parser("init", help="Make a directory a NucleantProject")
        p_init.add_argument("path", nargs="?", default=".",
                            help="Project directory (default: current directory)")
        p_init.add_argument("--name", help="App name (default: directory name)")
        p_init.set_defaults(func=self.init)

        AndroidCommands().register(sub)
        AppleCommands().register(sub)
        LinuxCommands().register(sub)
        ToolchainCommands().register(sub)

        from .plugin import load_plugins

        for plugin in load_plugins():
            plugin.register(sub)
        return parser

    def init(self, args: argparse.Namespace) -> int:
        from .project_init import ProjectInit

        ProjectInit(Path(args.path), app_name=args.name).run()
        return 0

    def run(self, argv: list[str] | None = None) -> int:
        load_dotenv()
        args = self.parser.parse_args(argv)
        try:
            return args.func(args) or 0
        except KeyboardInterrupt:
            return 130
        except _user_errors() as exc:
            if os.environ.get("NUCLEANT_DEBUG"):
                raise
            print(f"error: {exc}", file=sys.stderr)
            return 1


def main() -> None:
    sys.exit(NucleantCLI().run())
