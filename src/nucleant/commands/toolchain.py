"""``nucleant toolchain …`` — swiftly, the pinned Swift, and Swift SDKs."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..nucleant_toml import NucleantToml, ToolchainData
from ..swift import SDK_KINDS, resolve_swift_toolchain, sdk_id


def _project_config() -> NucleantToml | None:
    if NucleantToml.find(Path.cwd()).is_file():
        return NucleantToml.load(Path.cwd())
    return None


class ToolchainCommands:

    def register(self, sub: argparse._SubParsersAction) -> None:
        tc = sub.add_parser("toolchain", help="Swift toolchain (swiftly) and Swift SDKs")
        tsub = tc.add_subparsers(dest="command", required=True)

        install = tsub.add_parser(
            "install",
            help="Install swiftly, the pinned Swift, and the Swift SDKs the project needs",
            description=(
                "Installs swiftly if missing, the toolchain [toolchain] swift pins "
                "(default 6.3.3), and a Swift SDK for every cross-compiled platform "
                "nucleant.toml has: [android] -> Android SDK, [wasm] -> wasm SDK. "
                "--android / --wasm install those regardless."
            ),
        )
        install.add_argument("--android", action="store_true", help="Install the Android Swift SDK")
        install.add_argument("--wasm", action="store_true", help="Install the wasm Swift SDK")
        install.set_defaults(func=self.install)

        show = tsub.add_parser("show", help="Print the resolved toolchain and installed Swift SDKs")
        show.set_defaults(func=self.show)

    def install(self, args: argparse.Namespace) -> int:
        config = _project_config()
        tc_cfg = config.toolchain if config else ToolchainData({})
        swift = resolve_swift_toolchain(tc_cfg)
        print(f"[nucleant] {swift.describe()}")

        kinds = set()
        if args.android or (config and config.android is not None):
            kinds.add("android")
        if args.wasm or (config and config.has_wasm):
            kinds.add("wasm")
        for kind in SDK_KINDS:
            if kind in kinds:
                override = getattr(tc_cfg, f"{kind}_sdk")
                print(f"[nucleant] Swift SDK: {swift.ensure_sdk(kind, override)}")
        return 0

    def show(self, args: argparse.Namespace) -> int:
        config = _project_config()
        tc_cfg = config.toolchain if config else ToolchainData({})
        swift = resolve_swift_toolchain(tc_cfg, install=False)
        print(swift.describe())
        installed = swift.installed_sdks()
        for kind in SDK_KINDS:
            wanted = getattr(tc_cfg, f"{kind}_sdk") or sdk_id(swift.version, kind)
            mark = "installed" if wanted in installed else "missing"
            print(f"  {kind:<8} {wanted}  ({mark})")
        others = [s for s in installed if s not in {sdk_id(swift.version, k) for k in SDK_KINDS}]
        if others:
            print(f"  other SDKs: {', '.join(others)}")
        return 0
