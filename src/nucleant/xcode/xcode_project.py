"""High-level XcodeGen/xcodebuild orchestrator — the Apple side of GradleProject.

Xcode is used where ``swift run`` cannot go: iOS devices and simulators, and
the macOS ``.app`` (archive / App Store, or ``macos run --xcode``). Plain
``nucleant apple macos run`` is ``swift run`` (see ``project.DesktopProject``).
"""

from __future__ import annotations

import json
import platform
import plistlib
import subprocess
from os import environ
from pathlib import Path

from nucleant_bootstraps.bootstrap import BootstrapProtocol

from ..nucleant_toml import AppleData
from ..project import NucleantProject, SwiftDelegate
from ..tools import run_hook
from .github_actions import write_appstore_workflow
from .xcodegen_runner import XcodeGenRunner


class XcodeProjectError(Exception):
    pass


class XcodeProjectDelegate(SwiftDelegate):
    def __init__(self, project: "XcodeProject") -> None:
        super().__init__(project)
        self._xcode = project
        self._runner: XcodeGenRunner | None = None
        self._python_pin = None

    def xcode_generate(self, *, spec_path: Path, project_dir: Path) -> None:
        if self._runner is None:
            self._runner = XcodeGenRunner()
        self._runner.generate(spec_path=spec_path, project_dir=project_dir)

    # --- Python layer (only reached when python_enabled) ---------------------

    @property
    def _pin(self):
        if self._python_pin is None:
            from ..python.python_version import read_python_version_pin

            self._python_pin = read_python_version_pin(self.working_dir)
        return self._python_pin

    @property
    def py_version(self) -> str:
        from ..python.python_apple import PY_VERSION

        return self._pin.major_minor_or(PY_VERSION)

    @property
    def uv_py_version(self) -> str:
        return self._pin.full_or(self.py_version)

    def install_cpython(self) -> None:
        from ..python.python_apple import (
            DEFAULT_APPLE_PY_VERSION,
            ApplePythonFramework,
            apple_python_cache_root,
            unsupported_apple_py_error,
        )

        framework = ApplePythonFramework(
            apple_python_cache_root(), version=self._pin.resolve(DEFAULT_APPLE_PY_VERSION)
        )
        if framework.framework is None:
            raise unsupported_apple_py_error(framework.version)
        framework.install_to(self._xcode.xcode_dir / "Frameworks")


class XcodeProject(NucleantProject):

    bootstrap: BootstrapProtocol
    apple: AppleData

    def __init__(self, project_path: Path | None = None) -> None:
        super().__init__(project_path)
        if self.config.apple is None:
            raise XcodeProjectError("nucleant.toml has neither [ios] nor [macos]")
        self.apple = self.config.apple
        self.delegate = XcodeProjectDelegate(self)
        self.bootstrap = self.make_bootstrap(self.delegate)

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    @property
    def app_name(self) -> str:
        return self.config.app_name

    @property
    def xcode_dir(self) -> Path:
        return self.project_path / "project_dist" / "xcode"

    @property
    def xcodeproj(self) -> Path:
        return self.xcode_dir / f"{self.app_name}.xcodeproj"

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self, force: bool = False) -> Path:
        result = self.bootstrap.generate(platform="apple", force=force)
        if result is None:
            raise XcodeProjectError("bootstrap did not return an Xcode project")
        return result

    def open_in_xcode(self) -> None:
        if not self.xcodeproj.exists():
            self.generate()
        subprocess.run(["open", str(self.xcodeproj)], check=False)

    def _prepare(self, platform_data, install_platforms: list[str], simulator: bool = False) -> None:
        """pre_build hook → (Python layer) → project generation."""
        if platform_data is not None:
            run_hook(platform_data.pre_build, self.project_path)
        if self.config.python_enabled:
            from ..python.site_packages import install_apple_site_packages

            self.bootstrap.install_frameworks()
            install_apple_site_packages(
                self.project_path, self.xcode_dir, install_platforms, simulator=simulator
            )
        self.generate()
        if self.config.python_enabled:
            self.bootstrap.sync_site_xcframeworks()

    # ------------------------------------------------------------------
    # xcodebuild
    # ------------------------------------------------------------------

    @staticmethod
    def _configuration(variant: str) -> str:
        if variant in ("debug", "release"):
            return variant.capitalize()
        raise XcodeProjectError(f"Unknown variant {variant!r}; expected 'debug' or 'release'")

    def _env(self) -> dict[str, str]:
        # nucleant.toml [swift.env] reaches package resolution this way —
        # NUCLEANT_LOCAL_DEV, for instance, is read by every Nucleant manifest.
        return {**environ, **self.bootstrap.build_env()}

    def _xcodebuild(self, action: list[str], destination: str, variant: str, extra: list[str] | None = None) -> None:
        cmd = [
            "xcodebuild",
            *action,
            "-project", str(self.xcodeproj),
            "-scheme", self.app_name,
            "-configuration", self._configuration(variant),
            "-destination", destination,
            "-derivedDataPath", str(self.xcode_dir / "build"),
            "-skipPackagePluginValidation",
            "-skipMacroValidation",
            "-allowProvisioningUpdates",
            *(extra or []),
        ]
        print(f"[nucleant] xcodebuild {' '.join(action)} ({destination}, {variant})")
        result = subprocess.run(cmd, cwd=self.xcode_dir, stdin=subprocess.DEVNULL, env=self._env())
        if result.returncode != 0:
            raise XcodeProjectError(f"xcodebuild {' '.join(action)} exited with code {result.returncode}")

    @staticmethod
    def _app_sdk(app: Path) -> str:
        # Products subdir: "Debug-iphoneos", "Release-iphonesimulator", or
        # plain "Debug"/"Release" for macOS.
        name = app.parent.name
        if name.endswith("-iphonesimulator"):
            return "iphonesimulator"
        if name.endswith("-iphoneos"):
            return "iphoneos"
        return "macos"

    def _find_app(self, sdk: str, variant: str | None = None) -> Path:
        products = self.xcode_dir / "build" / "Build" / "Products"
        candidates = [c for c in sorted(products.rglob(f"{self.app_name}.app")) if self._app_sdk(c) == sdk]
        if variant is not None:
            config = self._configuration(variant)
            candidates = [c for c in candidates if c.parent.name.startswith(config)] or candidates
        if not candidates:
            raise XcodeProjectError(f"No {self.app_name}.app for {sdk} under {products}.")
        return max(candidates, key=lambda c: c.stat().st_mtime)

    def build_for(self, destination: str, sdk: str, variant: str = "debug") -> Path:
        self._xcodebuild(["build"], destination, variant)
        return self._find_app(sdk, variant)

    # ------------------------------------------------------------------
    # Run (build + install + launch)
    # ------------------------------------------------------------------

    def ios_run(
        self,
        uuid: str | None = None,
        name: str | None = None,
        variant: str = "debug",
        kind: str = "simulator",
    ) -> None:
        """Build for the chosen simulator/device, install, launch with console."""
        if self.apple.ios is None:
            raise XcodeProjectError("[ios] section is missing in nucleant.toml")
        if uuid is not None and name is not None:
            raise XcodeProjectError("run takes at most one of --uuid / --name")
        target = self._resolve_target(kind, uuid, name)
        udid: str = target["uuid"]
        kind = target["kind"]

        self._prepare(self.apple.ios, ["iOS"], simulator=kind == "simulator")
        sdk = "iphonesimulator" if kind == "simulator" else "iphoneos"
        app = self.build_for(f"id={udid}", sdk, variant)
        bundle_id = self._bundle_id(app / "Info.plist")
        print(f"[nucleant] App: {app}")

        if kind == "simulator":
            print(f"[nucleant] Booting simulator {target.get('name') or udid}...")
            subprocess.run(["xcrun", "simctl", "boot", udid], check=False, capture_output=True)
            subprocess.run(["open", "-a", "Simulator"], check=False)
            print(f"[nucleant] Installing {app.name}...")
            subprocess.run(["xcrun", "simctl", "install", udid, str(app)], check=True)
            subprocess.run(["xcrun", "simctl", "launch", "--console-pty", udid, bundle_id], check=True)
        else:
            subprocess.run(
                ["xcrun", "devicectl", "device", "install", "app", "--device", udid, str(app)],
                check=True,
            )
            subprocess.run(
                ["xcrun", "devicectl", "device", "process", "launch", "--console", "--device", udid, bundle_id],
                check=True,
            )

    def macos_run_app(self, variant: str = "debug") -> None:
        """Build the macOS .app with Xcode and run it, output in this terminal."""
        if self.apple.macos is None:
            raise XcodeProjectError("[macos] section is missing in nucleant.toml")
        self._prepare(self.apple.macos, ["macOS"])
        app = self.build_for(f"platform=macOS,arch={platform.machine()}", "macos", variant)
        executable = self._plist(app / "Contents" / "Info.plist")["CFBundleExecutable"]
        # The executable directly (not `open`) so stdout/stderr stream here.
        subprocess.run([str(app / "Contents" / "MacOS" / executable)], check=False)

    def _resolve_target(self, kind: str, uuid: str | None, name: str | None) -> dict:
        if uuid is not None:
            found = self._find_device_by_uuid(uuid)
            return found or {"uuid": uuid, "kind": kind, "name": ""}
        if name is not None:
            return self._find_device_by_name(name)
        if kind == "simulator":
            sims = [d for d in self._list_simulators() if "iOS" in d.get("runtime", "")]
            booted = [d for d in sims if d["state"] == "Booted"]
            phones = [d for d in sims if d["name"].startswith("iPhone")]
            pick = (booted or phones or sims or [None])[0]
            if pick is None:
                raise XcodeProjectError("No iOS simulators available (Xcode > Settings > Components).")
            print(f"[nucleant] Using simulator {pick['name']} ({pick['uuid']})")
            return pick
        devices = self._list_physical_devices()
        if not devices:
            raise XcodeProjectError("No connected iOS device found.")
        print(f"[nucleant] Using device {devices[0]['name']} ({devices[0]['uuid']})")
        return devices[0]

    # ------------------------------------------------------------------
    # Archive / App Store Connect upload
    # ------------------------------------------------------------------

    def _resolve_upload_creds(
        self, key_id: str | None, issuer_id: str | None, key_path: str | None
    ) -> tuple[str, str, Path]:
        key_id = key_id or environ.get("ASC_KEY_ID")
        issuer_id = issuer_id or environ.get("ASC_ISSUER_ID")
        key_path = key_path or environ.get("ASC_KEY_PATH")
        missing = [
            n
            for n, v in (
                ("--asc-key-id / ASC_KEY_ID", key_id),
                ("--asc-issuer-id / ASC_ISSUER_ID", issuer_id),
                ("--asc-key-path / ASC_KEY_PATH", key_path),
            )
            if not v
        ]
        if missing:
            raise XcodeProjectError("App Store Connect upload requires: " + ", ".join(missing))
        p8 = Path(key_path).expanduser()  # type: ignore[arg-type]
        if not p8.is_file():
            raise XcodeProjectError(f"App Store Connect key file not found: {p8}")
        return key_id, issuer_id, p8  # type: ignore[return-value]

    def _export_upload(self, archive: Path, team: str | None, key_id: str, issuer_id: str, key_path: Path) -> None:
        opts: dict = {"method": "app-store-connect", "destination": "upload"}
        if team:
            opts["teamID"] = team
        opts_path = self.xcode_dir / "ExportOptions.plist"
        with opts_path.open("wb") as f:
            plistlib.dump(opts, f)
        cmd = [
            "xcodebuild", "-exportArchive",
            "-archivePath", str(archive),
            "-exportOptionsPlist", str(opts_path),
            "-exportPath", str(self.xcode_dir / "export"),
            "-allowProvisioningUpdates",
            "-authenticationKeyID", key_id,
            "-authenticationKeyIssuerID", issuer_id,
            "-authenticationKeyPath", str(key_path),
        ]
        result = subprocess.run(cmd, cwd=self.xcode_dir, stdin=subprocess.DEVNULL, env=self._env())
        if result.returncode != 0:
            raise XcodeProjectError(f"xcodebuild -exportArchive (upload) exited with code {result.returncode}")

    def archive(
        self,
        platform_name: str,
        variant: str = "release",
        upload: bool = False,
        key_id: str | None = None,
        issuer_id: str | None = None,
        key_path: str | None = None,
        build_number: str | None = None,
        app_version: str | None = None,
    ) -> Path:
        """``xcodebuild archive`` for "ios" or "macos", optionally uploaded."""
        data = self.apple.ios if platform_name == "ios" else self.apple.macos
        if data is None:
            raise XcodeProjectError(f"[{platform_name}] section is missing in nucleant.toml")
        creds = self._resolve_upload_creds(key_id, issuer_id, key_path) if upload else None
        if upload and not data.developer_team:
            raise XcodeProjectError(
                f"An App Store archive needs developer_team in [{platform_name}]."
            )
        self._prepare(data, ["iOS"] if platform_name == "ios" else ["macOS"])

        # Build settings on the command line override the project's: a CI run
        # number becomes the build, a tag the version, nothing is rewritten.
        overrides = []
        if build_number is not None:
            overrides.append(f"CURRENT_PROJECT_VERSION={build_number}")
        if app_version is not None:
            overrides.append(f"MARKETING_VERSION={app_version}")

        archive = self.xcode_dir / "archives" / f"{self.app_name}-{platform_name}.xcarchive"
        destination = "generic/platform=iOS" if platform_name == "ios" else "generic/platform=macOS"
        self._xcodebuild(["archive"], destination, variant, ["-archivePath", str(archive), *overrides])
        if upload:
            assert creds is not None
            self._export_upload(archive, data.developer_team, *creds)
        return archive

    def create_action(self, platform_name: str) -> Path:
        return write_appstore_workflow(self.project_path, platform_name)

    # ------------------------------------------------------------------
    # Devices (simctl + devicectl)
    # ------------------------------------------------------------------

    def devices(self) -> list[dict]:
        return [*self._list_simulators(), *self._list_physical_devices()]

    def _list_simulators(self) -> list[dict]:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "--json", "devices", "available"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
        out = []
        for runtime, devs in (data.get("devices") or {}).items():
            for d in devs:
                out.append(
                    {
                        "kind": "simulator",
                        "uuid": d.get("udid", ""),
                        "name": d.get("name", ""),
                        "state": d.get("state", ""),
                        "runtime": runtime.rsplit(".", 1)[-1],
                    }
                )
        return out

    def _list_physical_devices(self) -> list[dict]:
        try:
            result = subprocess.run(
                ["xcrun", "devicectl", "list", "devices", "--json-output", "-"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, OSError):
            return []
        if result.returncode != 0:
            return []
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
        out = []
        for d in data.get("result", {}).get("devices") or []:
            out.append(
                {
                    "kind": "device",
                    "uuid": d.get("hardwareProperties", {}).get("udid") or d.get("identifier", ""),
                    "name": d.get("deviceProperties", {}).get("name", ""),
                    "state": d.get("connectionProperties", {}).get("tunnelState", ""),
                }
            )
        return out

    def _find_device_by_uuid(self, uuid: str) -> dict | None:
        return next((d for d in self.devices() if d["uuid"] == uuid), None)

    def _find_device_by_name(self, name: str) -> dict:
        matches = [d for d in self.devices() if d["name"] == name]
        if not matches:
            raise XcodeProjectError(f"No simulator or device named {name!r}")
        if len(matches) > 1:
            raise XcodeProjectError(f"Ambiguous name {name!r}; use --uuid instead")
        return matches[0]

    @staticmethod
    def _plist(path: Path) -> dict:
        with path.open("rb") as f:
            return plistlib.load(f)

    def _bundle_id(self, info_plist: Path) -> str:
        return self._plist(info_plist)["CFBundleIdentifier"]
