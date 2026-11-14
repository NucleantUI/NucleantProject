"""The project's Swift toolchain: resolved once per command, pinned by version.

Resolution, in order:

1. ``[toolchain] swiftly = true`` (default): swiftly, installed if missing;
   the pinned version (``[toolchain] swift``, default 6.3.3) installed with it
   if missing; then that toolchain's own ``swift`` by absolute path.
2. Otherwise — or where swiftly cannot run (Windows) — ``swift`` from PATH,
   with a warning when its version is not the pinned one.

Everything that compiles Swift for the project — ``swift run``, the Gradle
cross-compile, ``swift sdk install`` — uses :attr:`SwiftToolchain.swift`, so
the toolchain and the Swift SDKs always come from the same release.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from ..nucleant_toml import ToolchainData
from . import swiftly as _swiftly
from .sdks import SdkKind, parse_sdk_list, sdk_checksum, sdk_id, sdk_url


class SwiftToolchainError(Exception):
    pass


@dataclass
class SwiftToolchain:
    version: str
    #: Absolute path of ``swift``, or the bare name when taken from PATH.
    swift: str
    via_swiftly: bool
    _sdks: list[str] | None = field(default=None, repr=False)

    @property
    def bin_dir(self) -> Path | None:
        p = Path(self.swift)
        return p.parent if p.is_absolute() else None

    def env(self, base: dict[str, str] | None = None) -> dict[str, str]:
        """``base`` (default: os.environ) with this toolchain's bin first on PATH."""
        env = dict(os.environ if base is None else base)
        if self.bin_dir is not None:
            env["PATH"] = f"{self.bin_dir}{os.pathsep}{env.get('PATH', '')}"
        return env

    def run(
        self,
        args: list[str],
        cwd: Path | None = None,
        extra_env: dict[str, str] | None = None,
        check: bool = True,
    ) -> int:
        env = self.env()
        env.update(extra_env or {})
        print(f"[nucleant] swift {' '.join(args)}")
        result = subprocess.run([self.swift, *args], cwd=cwd, env=env)
        if check and result.returncode != 0:
            raise SwiftToolchainError(
                f"swift {' '.join(args)} exited with code {result.returncode}"
            )
        return result.returncode

    # --- Swift SDKs ----------------------------------------------------------

    def installed_sdks(self, refresh: bool = False) -> list[str]:
        if self._sdks is None or refresh:
            result = subprocess.run(
                [self.swift, "sdk", "list"], capture_output=True, text=True, env=self.env()
            )
            self._sdks = parse_sdk_list(result.stdout) if result.returncode == 0 else []
        return self._sdks

    def ensure_sdk(self, kind: SdkKind, override: str | None = None) -> str:
        """Install the ``kind`` Swift SDK for this toolchain if missing; return its id."""
        wanted = override or sdk_id(self.version, kind)
        if wanted in self.installed_sdks():
            return wanted
        if override:
            raise SwiftToolchainError(
                f"Swift SDK {override!r} ([toolchain] {kind}_sdk) is not installed. "
                f"Installed: {', '.join(self.installed_sdks()) or 'none'}"
            )
        url = sdk_url(self.version, kind)
        checksum = sdk_checksum(self.version, kind)
        print(f"[nucleant] installing the Swift {self.version} {kind} SDK...")
        self.run(["sdk", "install", url, "--checksum", checksum])
        if wanted not in self.installed_sdks(refresh=True):
            raise SwiftToolchainError(
                f"`swift sdk install` succeeded but {wanted} is not in `swift sdk list`"
            )
        return wanted

    def describe(self) -> str:
        how = "swiftly" if self.via_swiftly else "PATH"
        return f"Swift {self.version} ({how}): {self.swift}"


def _swift_version(swift: str) -> str | None:
    try:
        out = subprocess.run([swift, "--version"], capture_output=True, text=True).stdout
    except OSError:
        return None
    m = re.search(r"Swift version (\d+\.\d+(?:\.\d+)?)", out)
    return m.group(1) if m else None


def resolve_swift_toolchain(
    config: ToolchainData, install: bool = True
) -> SwiftToolchain:
    version = config.swift
    if config.swiftly and _swiftly.supported_host():
        swiftly = _swiftly.find_swiftly()
        if swiftly is None and install:
            swiftly = _swiftly.install_swiftly()
        if swiftly is not None:
            swift = _swiftly.toolchain_swift(swiftly, version)
            if swift is None and install:
                _swiftly.install_toolchain(swiftly, version)
                swift = _swiftly.toolchain_swift(swiftly, version)
            if swift is not None:
                return SwiftToolchain(version=version, swift=str(swift), via_swiftly=True)
            if install:
                raise SwiftToolchainError(
                    f"swiftly installed Swift {version}, but its toolchain could not be located"
                )
        print(
            f"[nucleant] swiftly/Swift {version} not available; falling back to "
            "`swift` on PATH."
        )

    swift = shutil.which("swift")
    if swift is None:
        raise SwiftToolchainError(
            "No Swift toolchain: install swiftly (https://www.swift.org/install) "
            "or put `swift` on PATH."
        )
    found = _swift_version(swift)
    if found != version:
        print(
            f"[nucleant] warning: `swift` on PATH is {found or 'unknown'}, the project "
            f"pins {version}. Swift SDKs must match the toolchain exactly."
        )
    return SwiftToolchain(version=found or version, swift=swift, via_swiftly=False)
