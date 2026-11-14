"""``nucleant apple …`` — iOS device, iOS Simulator, macOS, Xcode."""

from __future__ import annotations

import argparse

from ..project import DesktopProject
from ..xcode.xcode_project import XcodeProject


def _variant(parser: argparse.ArgumentParser, default: str) -> None:
    parser.add_argument("variant", nargs="?", default=default, choices=["debug", "release"])


def _add_archive(parser: argparse.ArgumentParser) -> None:
    _variant(parser, "release")
    parser.add_argument("--upload", action="store_true",
                        help="Upload the archive to App Store Connect")
    parser.add_argument("--asc-key-id", help="App Store Connect API Key ID (fallback: ASC_KEY_ID)")
    parser.add_argument("--asc-issuer-id", help="App Store Connect Issuer ID (fallback: ASC_ISSUER_ID)")
    parser.add_argument("--asc-key-path", help="Path to the .p8 API key (fallback: ASC_KEY_PATH)")
    parser.add_argument("--build-number", help="CFBundleVersion for this archive (e.g. CI run number)")
    parser.add_argument("--app-version", help="CFBundleShortVersionString (e.g. tag 1.2.3)")


def _add_target(parser: argparse.ArgumentParser, what: str) -> None:
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--uuid", help=f"UDID of the {what}")
    target.add_argument("--name", help=f"{what.capitalize()} name")


def _print_devices(items: list[dict], empty_msg: str) -> None:
    if not items:
        print(empty_msg)
        return
    for it in items:
        print(
            f"{it['kind']:<10} uuid={it['uuid']:<40} "
            f"state={it.get('state', ''):<12} name={it.get('name', '')}"
            + (f"  ({it['runtime']})" if it.get("runtime") else "")
        )


def _archive(platform_name: str, args: argparse.Namespace) -> int:
    archive = XcodeProject().archive(
        platform_name,
        variant=args.variant,
        upload=args.upload,
        key_id=args.asc_key_id,
        issuer_id=args.asc_issuer_id,
        key_path=args.asc_key_path,
        build_number=args.build_number,
        app_version=args.app_version,
    )
    print(f"archive: {archive}")
    return 0


class AppleCommands:

    def register(self, sub: argparse._SubParsersAction) -> None:
        apple = sub.add_parser("apple", help="Apple platform commands (iOS / macOS)")
        psub = apple.add_subparsers(dest="platform", required=True)
        self._register_ios(psub)
        self._register_sim(psub)
        self._register_macos(psub)
        self._register_xcode(psub)

    # --- iOS device -----------------------------------------------------

    def _register_ios(self, sub: argparse._SubParsersAction) -> None:
        ios = sub.add_parser("ios", help="iOS device commands")
        isub = ios.add_subparsers(dest="command", required=True)

        run = isub.add_parser("run", help="Build, install and launch on a connected device")
        _variant(run, "debug")
        _add_target(run, "device")
        run.set_defaults(func=lambda a: self._ios_run(a, "device"))

        archive = isub.add_parser("archive", help="Archive for distribution (App Store)")
        _add_archive(archive)
        archive.set_defaults(func=lambda a: _archive("ios", a))

        action = isub.add_parser("create-action", help="Write a tag-triggered App Store workflow")
        action.set_defaults(func=lambda a: self._create_action("ios"))

        devices = isub.add_parser("devices", help="List connected iOS devices")
        devices.set_defaults(func=lambda a: self._devices("device", "(no connected iOS devices found)"))

    # --- iOS Simulator ----------------------------------------------------

    def _register_sim(self, sub: argparse._SubParsersAction) -> None:
        sim = sub.add_parser("sim", help="iOS Simulator commands")
        ssub = sim.add_subparsers(dest="command", required=True)

        run = ssub.add_parser("run", help="Build, install and launch on a simulator")
        _variant(run, "debug")
        _add_target(run, "simulator")
        run.set_defaults(func=lambda a: self._ios_run(a, "simulator"))

        devices = ssub.add_parser("devices", help="List available iOS simulators")
        devices.set_defaults(func=lambda a: self._devices("simulator", "(no iOS simulators found)"))

    # --- macOS --------------------------------------------------------------

    def _register_macos(self, sub: argparse._SubParsersAction) -> None:
        macos = sub.add_parser("macos", help="macOS commands")
        msub = macos.add_subparsers(dest="command", required=True)

        run = msub.add_parser(
            "run",
            help="Build and run on this Mac (`swift run`; --xcode for the .app)",
        )
        _variant(run, "debug")
        run.add_argument("--xcode", action="store_true",
                         help="Build the .app through the Xcode project instead of SwiftPM")
        run.add_argument("app_args", nargs=argparse.REMAINDER,
                         help="Arguments passed to the app (after --)")
        run.set_defaults(func=self._macos_run)

        archive = msub.add_parser("archive", help="Archive for distribution (App Store)")
        _add_archive(archive)
        archive.set_defaults(func=lambda a: _archive("macos", a))

        action = msub.add_parser("create-action", help="Write a tag-triggered App Store workflow")
        action.set_defaults(func=lambda a: self._create_action("macos"))

    # --- Xcode ----------------------------------------------------------------

    def _register_xcode(self, sub: argparse._SubParsersAction) -> None:
        xcode = sub.add_parser("xcode", help="Xcode project commands")
        xsub = xcode.add_subparsers(dest="command", required=True)

        gen = xsub.add_parser("generate", help="Write project_dist/xcode and run xcodegen")
        gen.add_argument("--force", action="store_true", help="Run xcodegen even if project.yml is unchanged")
        gen.set_defaults(func=self._xcode_generate)

        open_p = xsub.add_parser("open", help="Open the Xcode project in Xcode")
        open_p.set_defaults(func=lambda a: XcodeProject().open_in_xcode() or 0)

    # ------------------------------------------------------------------

    def _ios_run(self, args: argparse.Namespace, kind: str) -> int:
        XcodeProject().ios_run(uuid=args.uuid, name=args.name, variant=args.variant, kind=kind)
        return 0

    def _macos_run(self, args: argparse.Namespace) -> int:
        if args.xcode:
            XcodeProject().macos_run_app(variant=args.variant)
            return 0
        app_args = [a for a in args.app_args if a != "--"] if args.app_args else []
        return DesktopProject().run("macos", configuration=args.variant, app_args=app_args)

    def _devices(self, kind: str, empty: str) -> int:
        _print_devices([d for d in XcodeProject().devices() if d["kind"] == kind], empty)
        return 0

    def _create_action(self, platform_name: str) -> int:
        print(f"workflow: {XcodeProject().create_action(platform_name)}")
        return 0

    def _xcode_generate(self, args: argparse.Namespace) -> int:
        print(f"xcodeproj: {XcodeProject().generate(force=args.force)}")
        return 0
