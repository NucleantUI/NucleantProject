"""``nucleant android …``"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ..gradle.android_toolchain import AndroidToolchain
from ..gradle.github_actions import write_playstore_workflow
from ..gradle.gradle_project import GradleProject
from ..nucleant_toml import NucleantToml


def _variant(parser: argparse.ArgumentParser, default: str) -> None:
    parser.add_argument("variant", nargs="?", default=default, choices=["debug", "release"])


class AndroidCommands:

    def register(self, sub: argparse._SubParsersAction) -> None:
        android = sub.add_parser("android", help="Android (Gradle) commands")
        asub = android.add_subparsers(dest="command", required=True)

        # --- RUN: build + install + launch ---
        p_run = asub.add_parser(
            "run",
            help="Build, install and launch on a device or emulator",
            description=(
                "Generates the Gradle project and the Main Swift Package, builds "
                "the APK, installs it and launches it. Without --uuid/--name it "
                "uses the first connected device, else boots an AVD."
            ),
        )
        _variant(p_run, "debug")
        target = p_run.add_mutually_exclusive_group()
        target.add_argument("--uuid", help="adb serial of a device or running emulator")
        target.add_argument("--name", help="AVD name to boot")
        p_run.add_argument("--clean", action="store_true", help="Start over: remove project_dist/gradle (Gradle and Swift builds, the Android Package.resolved) and resolve the packages again")
        p_run.add_argument("--logcat", action="store_true", help="Follow the app's logcat after launch")
        p_run.set_defaults(func=self.run)

        # --- ARCHIVE: build artifacts for distribution, no launch ---
        p_archive = asub.add_parser(
            "archive", help="Build an APK, AAB (--bundle) or AAR (--aar) without launching"
        )
        _variant(p_archive, "release")
        kind = p_archive.add_mutually_exclusive_group()
        kind.add_argument("--aar", action="store_true", help="Build an AAR library")
        kind.add_argument("--bundle", action="store_true", help="Build an AAB (Android App Bundle)")
        p_archive.add_argument("--clean", action="store_true", help="Start over: remove project_dist/gradle (Gradle and Swift builds, the Android Package.resolved) and resolve the packages again")
        p_archive.set_defaults(func=self.archive)

        # --- GENERATE ---
        p_gen = asub.add_parser(
            "generate", help="Write project_dist/gradle and the Main Swift Package, no build"
        )
        p_gen.set_defaults(func=self.generate)

        p_templates = asub.add_parser(
            "generate-templates",
            help="Write build.tmpl.gradle.kts / AndroidManifest.tmpl.xml to the project",
        )
        p_templates.add_argument("--force", action="store_true", help="Overwrite existing templates")
        p_templates.set_defaults(func=self.generate_templates)

        # --- SIGN ---
        p_sign = asub.add_parser("sign", help="Sign the built release artifacts")
        p_sign.add_argument("--keystore", type=Path, default=os.environ.get("KEYSTORE"),
                            help="Keystore file (fallback: KEYSTORE)")
        p_sign.add_argument("--storepass", default=os.environ.get("STOREPASS"),
                            help="Keystore password (fallback: STOREPASS)")
        p_sign.add_argument("--keyalias", default=os.environ.get("KEYALIAS"),
                            help="Key alias (fallback: KEYALIAS)")
        p_sign.add_argument("--keypass", default=os.environ.get("KEYPASS"),
                            help="Key password, if different (fallback: KEYPASS)")
        p_sign.add_argument("--variant", default="release", choices=["debug", "release"])
        sign_kind = p_sign.add_mutually_exclusive_group()
        sign_kind.add_argument("--bundle", action="store_true", help="Sign the AAB")
        sign_kind.add_argument("--apk", action="store_true", default=True, help="Sign the APK (default)")
        p_sign.set_defaults(func=self.sign)

        # --- GENKEY ---
        p_genkey = asub.add_parser("genkey", help="Generate a release keystore")
        p_genkey.add_argument("--out", type=Path, default=os.environ.get("KEYSTORE"),
                              help="Output keystore path (fallback: KEYSTORE)")
        p_genkey.add_argument("--storepass", default=os.environ.get("STOREPASS"),
                              help="Keystore password (fallback: STOREPASS)")
        p_genkey.add_argument("--keyalias", default=os.environ.get("KEYALIAS"),
                              help="Key alias (fallback: KEYALIAS)")
        p_genkey.add_argument("--keypass", default=os.environ.get("KEYPASS"),
                              help="Key password (default: storepass)")
        p_genkey.add_argument("--dname", help="Distinguished Name, e.g. 'CN=App, O=Org'")
        p_genkey.set_defaults(func=self.genkey)

        # --- CREATE-ACTION ---
        p_action = asub.add_parser(
            "create-action", help="Write a tag-triggered GitHub Actions Play Store workflow"
        )
        p_action.set_defaults(func=self.create_action)

        # --- GET-PATH ---
        p_path = asub.add_parser("get-path", help="Print the resolved path of a tool")
        p_path.add_argument("tool", choices=["sdk", "ndk", "emulator"])
        p_path.set_defaults(func=self.get_path)

        # --- DEVICES ---
        p_devices = asub.add_parser("devices", help="List devices and AVDs")
        p_devices.set_defaults(func=self.devices)

    # ------------------------------------------------------------------

    def run(self, args: argparse.Namespace) -> int:
        GradleProject().run(
            uuid=args.uuid,
            name=args.name,
            variant=args.variant,
            clean=args.clean,
            logcat=args.logcat,
        )
        return 0

    def archive(self, args: argparse.Namespace) -> int:
        GradleProject().archive(args.variant, aar=args.aar, bundle=args.bundle, clean=args.clean)
        return 0

    def generate(self, args: argparse.Namespace) -> int:
        out = GradleProject().generate()
        print(f"gradle: {out}")
        return 0

    def generate_templates(self, args: argparse.Namespace) -> int:
        GradleProject().generate_templates(force=args.force)
        return 0

    def get_path(self, args: argparse.Namespace) -> int:
        config = NucleantToml.load(Path.cwd())
        android = config.android
        if args.tool == "sdk":
            path = AndroidToolchain.find_sdk_path(android, Path.cwd())
        elif args.tool == "ndk":
            path = AndroidToolchain.find_ndk_path(android, Path.cwd())
        else:
            sdk = AndroidToolchain.find_sdk_path(android, Path.cwd())
            emu = Path(sdk) / "emulator" / ("emulator.exe" if sys.platform == "win32" else "emulator") if sdk else None
            path = str(emu) if emu and emu.exists() else None
        if path is None:
            print(f"{args.tool} not found", file=sys.stderr)
            return 1
        print(path)
        return 0

    def sign(self, args: argparse.Namespace) -> int:
        if not args.keystore or not args.storepass or not args.keyalias:
            print(
                "Error: missing credentials. Provide --keystore, --storepass and --keyalias "
                "or set KEYSTORE / STOREPASS / KEYALIAS.",
                file=sys.stderr,
            )
            return 1
        signed = GradleProject().sign_project_artifact(
            keystore=args.keystore,
            storepass=args.storepass,
            keyalias=args.keyalias,
            keypass=args.keypass,
            variant=args.variant,
            bundle=args.bundle,
        )
        label = "AAB" if args.bundle else "APK"
        for path in signed:
            print(f"Signed {label}: {path}")
        return 0

    def genkey(self, args: argparse.Namespace) -> int:
        if not args.out or not args.storepass or not args.keyalias:
            print(
                "Error: missing credentials. Provide --out, --storepass and --keyalias "
                "or set KEYSTORE / STOREPASS / KEYALIAS.",
                file=sys.stderr,
            )
            return 1
        out = GradleProject().genkey(
            keystore_path=args.out,
            storepass=args.storepass,
            keyalias=args.keyalias,
            keypass=args.keypass,
            dname=args.dname,
        )
        print(f"Keystore generated: {out}")
        return 0

    def create_action(self, args: argparse.Namespace) -> int:
        # Straight from the config: GradleProject would resolve toolchains
        # just to write a file.
        config = NucleantToml.load(Path.cwd())
        if config.android is None:
            print("Error: [android] section is missing in nucleant.toml", file=sys.stderr)
            return 1
        print(f"workflow: {write_playstore_workflow(Path.cwd(), config.android.package_name)}")
        return 0

    def devices(self, args: argparse.Namespace) -> int:
        items = GradleProject().devices()
        if not items:
            print("(no devices or AVDs found)")
            return 0
        for it in items:
            if it.get("kind") == "device":
                print(
                    f"device  serial={it['serial']:<20} state={it['state']:<12}"
                    f" model={it.get('model', '')}"
                )
            else:
                print(f"avd     name={it['name']}")
        return 0
