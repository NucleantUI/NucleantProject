"""swiftly: install it, install a toolchain with it, and find that toolchain.

swiftly is the default way nucleant gets Swift. The project's toolchain is
pinned (``[toolchain] swift``) and selected per command with ``+<version>``,
so nucleant never changes the user's global default toolchain.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SWIFTLY_MACOS_PKG = "https://download.swift.org/swiftly/darwin/swiftly.pkg"
SWIFTLY_LINUX_TARBALL = "https://download.swift.org/swiftly/linux/swiftly-{arch}.tar.gz"


class SwiftlyError(Exception):
    pass


def swiftly_home() -> Path:
    env = os.environ.get("SWIFTLY_HOME_DIR")
    if env:
        return Path(env).expanduser()
    if sys.platform == "darwin":
        return Path.home() / ".swiftly"
    data = os.environ.get("XDG_DATA_HOME")
    base = Path(data).expanduser() if data else Path.home() / ".local" / "share"
    return base / "swiftly"


def find_swiftly() -> str | None:
    """``swiftly`` on PATH, else in its default install location."""
    on_path = shutil.which("swiftly")
    if on_path:
        return on_path
    candidate = swiftly_home() / "bin" / "swiftly"
    return str(candidate) if candidate.is_file() and os.access(candidate, os.X_OK) else None


def supported_host() -> bool:
    return sys.platform in ("darwin", "linux")


def install_swiftly() -> str:
    """Install swiftly for the current user, without touching shell profiles.

    The official installers: the user-domain .pkg on macOS, the per-arch
    tarball on Linux, then ``swiftly init`` with ``--skip-install`` (nucleant
    installs the toolchain it needs itself) and ``--no-modify-profile`` (no
    edits to the user's dotfiles; nucleant calls swiftly by path).
    """
    if not supported_host():
        raise SwiftlyError(f"swiftly does not support {sys.platform}")

    print("[nucleant] installing swiftly...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        if sys.platform == "darwin":
            pkg = tmp_path / "swiftly.pkg"
            _download(SWIFTLY_MACOS_PKG, pkg)
            _run(["installer", "-pkg", str(pkg), "-target", "CurrentUserHomeDirectory"])
            binary = swiftly_home() / "bin" / "swiftly"
        else:
            arch = platform.machine()
            arch = {"amd64": "x86_64", "arm64": "aarch64"}.get(arch, arch)
            tarball = tmp_path / "swiftly.tar.gz"
            _download(SWIFTLY_LINUX_TARBALL.format(arch=arch), tarball)
            _run(["tar", "-zxf", str(tarball), "-C", str(tmp_path)])
            binary = tmp_path / "swiftly"
        if not binary.is_file():
            raise SwiftlyError(f"swiftly installer did not produce {binary}")
        _run(
            [
                str(binary),
                "init",
                "--assume-yes",
                "--skip-install",
                "--no-modify-profile",
                "--quiet-shell-followup",
            ]
        )

    found = find_swiftly()
    if found is None:
        raise SwiftlyError(
            f"swiftly was installed but not found under {swiftly_home() / 'bin'}"
        )
    print(f"[nucleant] swiftly installed at {found}")
    return found


def toolchain_swift(swiftly: str, version: str) -> Path | None:
    """The ``swift`` executable of an installed toolchain, or None.

    Asks the toolchain itself (``swift -print-target-info``) through
    ``swiftly run … +<version>``, which works the same for swiftly's macOS
    ``.xctoolchain`` installs and its Linux toolchain directories.
    """
    result = subprocess.run(
        [swiftly, "run", "swift", "-print-target-info", f"+{version}"],
        capture_output=True,
        text=True,
        cwd=Path.home(),
    )
    if result.returncode != 0:
        return None
    info = _first_json_object(result.stdout)
    resource = (info or {}).get("paths", {}).get("runtimeResourcePath")
    if not resource:
        return None
    # <toolchain>/usr/lib/swift -> <toolchain>/usr/bin/swift
    swift = Path(resource).parent.parent / "bin" / "swift"
    return swift if swift.is_file() else None


def install_toolchain(swiftly: str, version: str) -> None:
    print(f"[nucleant] installing Swift {version} with swiftly (this can take a while)...")
    _run([swiftly, "install", version, "--assume-yes"])


def _first_json_object(text: str) -> dict | None:
    start = text.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _download(url: str, dst: Path) -> None:
    print(f"[nucleant] downloading {url}")
    with urllib.request.urlopen(url) as resp, dst.open("wb") as f:
        shutil.copyfileobj(resp, f)


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SwiftlyError(f"{' '.join(cmd)} exited with code {result.returncode}")
