"""Swift SDKs for cross-compiling: Android and WebAssembly.

Both cross-compile from macOS or Linux, so they are installed whenever a
project targets them. The bundle has to come from the same release as the
toolchain, so the id, URL and checksum are all derived from the toolchain
version — the checksum from swift.org's own release index, which is what
``swift sdk install`` verifies the download against.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Literal

SdkKind = Literal["android", "wasm"]
SDK_KINDS: tuple[SdkKind, ...] = ("android", "wasm")

RELEASES_URL = "https://www.swift.org/api/v1/install/releases.json"


class SwiftSdkError(Exception):
    pass


def sdk_id(version: str, kind: SdkKind) -> str:
    """``swift-6.3.3-RELEASE_android`` — the id ``swift sdk list`` shows."""
    return f"swift-{version}-RELEASE_{kind}"


def sdk_url(version: str, kind: SdkKind) -> str:
    return (
        f"https://download.swift.org/swift-{version}-release/{kind}-sdk/"
        f"swift-{version}-RELEASE/{sdk_id(version, kind)}.artifactbundle.tar.gz"
    )


def sdk_checksum(version: str, kind: SdkKind, releases: list[dict] | None = None) -> str:
    """The SHA-256 swift.org publishes for this release's ``<kind>`` SDK."""
    if releases is None:
        releases = fetch_releases()
    for release in releases:
        if release.get("name") != version:
            continue
        for plat in release.get("platforms", []):
            if plat.get("platform") == f"{kind}-sdk" and plat.get("checksum"):
                return plat["checksum"]
        raise SwiftSdkError(f"Swift {version} has no {kind} SDK in {RELEASES_URL}")
    raise SwiftSdkError(f"Swift {version} is not a release listed at {RELEASES_URL}")


def fetch_releases() -> list[dict]:
    try:
        with urllib.request.urlopen(RELEASES_URL, timeout=30) as resp:
            return json.load(resp)
    except (OSError, ValueError) as exc:
        raise SwiftSdkError(f"could not read {RELEASES_URL}: {exc}") from exc


def parse_sdk_list(output: str) -> list[str]:
    """Ids from ``swift sdk list`` (one per line, possibly with notes)."""
    ids = []
    for line in output.splitlines():
        line = line.strip()
        if line and not line.startswith(("No Swift SDKs", "warning:", "error:")):
            ids.append(line.split()[0])
    return ids
