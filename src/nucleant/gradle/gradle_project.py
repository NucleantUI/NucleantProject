"""High-level Gradle/Android project orchestrator.

``run`` is the development loop — generate, build, install, launch — the way
``swift run`` is on the desktop. ``archive`` builds without launching (release
APK/AAB/AAR for distribution); ``sign`` and ``genkey`` cover the store side.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from nucleant_bootstraps.bootstrap import BootstrapProtocol

from ..nucleant_toml import AndroidData
from ..project import NucleantProject, SwiftDelegate
from ..tools import run_hook
from .adb import ADB, ADBError
from .android_emulator import DEFAULT_AVD_NAME, AndroidEmulator
from .android_toolchain import DEFAULT_API_VERSION, DEFAULT_SDK_VERSION, AndroidToolchain


class GradleProjectError(Exception):
    pass


class GradleProjectDelegate(SwiftDelegate):
    """What the bootstrap asks of the CLI while writing the Gradle project."""

    def __init__(self, project: "GradleProject") -> None:
        super().__init__(project)
        self._gradle = project
        self._python_pin = None

    @property
    def swift_android_sdk(self) -> str | None:
        return self._gradle.swift_android_sdk

    @property
    def default_api_version(self) -> int:
        return DEFAULT_API_VERSION

    @property
    def sdk_path(self) -> str:
        return self._gradle.toolchain.sdk_path

    @property
    def ndk_version(self) -> str:
        return self._gradle.toolchain.ndk_version

    @property
    def ndk_path(self) -> str:
        return self._gradle.toolchain.ndk_path

    @property
    def java_path(self) -> str:
        return self._gradle.toolchain.java_path

    # --- Python layer (only reached when python_enabled) ---------------------

    @property
    def _pin(self):
        if self._python_pin is None:
            from ..python.python_version import read_python_version_pin

            self._python_pin = read_python_version_pin(self.working_dir)
        return self._python_pin

    @property
    def py_version(self) -> str:
        from ..python.cpython_android import PY_VERSION

        return self._pin.major_minor_or(PY_VERSION)

    @property
    def android_py_version(self) -> str:
        from ..python.cpython_android import ANDROID_VERSION

        return self._pin.resolve(ANDROID_VERSION)

    @property
    def uv_py_version(self) -> str:
        return self._pin.full_or(self.py_version)

    def install_cpython(self) -> None:
        from ..python.cpython_android import install_cpython_android

        data = self._gradle.android_data
        install_cpython_android(
            data.tools_root(self.working_dir),
            [arch.value for arch in data.archs],
            self.sdk_path,
            self.ndk_path,
            self.java_path,
            py_version=self.py_version,
            android_version=self.android_py_version,
        )

    def android_prefix(self, root: Path, arch: str, android_version: str) -> Path:
        from ..python.cpython_android import android_prefix

        return android_prefix(root, arch, android_version)


class GradleProject(NucleantProject):

    adb: ADB | None
    emulator: AndroidEmulator | None
    bootstrap: BootstrapProtocol
    android_data: AndroidData

    def __init__(self, project_path: Path | None = None) -> None:
        super().__init__(project_path)
        if self.config.android is None:
            raise GradleProjectError("[android] section is missing in nucleant.toml")
        self.android_data = self.config.android
        self._toolchain: AndroidToolchain | None = None
        self._swift_android_sdk: str | None = None

        # Lightweight SDK lookup (no downloads), enough for devices/run on a
        # machine that already has one. A build resolves the full toolchain.
        sdk_path = AndroidToolchain.find_sdk_path(self.android_data, self.project_path)
        self.adb = ADB(sdk_path) if sdk_path else None
        self.emulator = AndroidEmulator(sdk_path, self.sdk_version) if sdk_path else None

        self.delegate = GradleProjectDelegate(self)
        self.bootstrap = self.make_bootstrap(self.delegate)

    @property
    def sdk_version(self) -> str:
        data = self.android_data
        return data.sdk or (str(data.api) if data.api else DEFAULT_SDK_VERSION)

    @property
    def toolchain(self) -> AndroidToolchain:
        """Full Android toolchain resolution (may download SDK/NDK/Java)."""
        if self._toolchain is None:
            self._toolchain = AndroidToolchain.resolve(self.android_data, self.project_path)
            if self.adb is None:
                self.adb = ADB(self._toolchain.sdk_path)
                self.emulator = AndroidEmulator(self._toolchain.sdk_path, self.sdk_version)
        return self._toolchain

    @property
    def swift_android_sdk(self) -> str:
        """The Swift Android SDK for the pinned toolchain, installed if missing."""
        if self._swift_android_sdk is None:
            self._swift_android_sdk = self.swift.ensure_sdk(
                "android", self.config.toolchain.android_sdk
            )
        return self._swift_android_sdk

    @property
    def gradle_dir(self) -> Path:
        return self.project_path / "project_dist" / "gradle"

    # ------------------------------------------------------------------
    # Generation / build
    # ------------------------------------------------------------------

    def generate(self, aar: bool = False, clean: bool = False) -> Path:
        """Write the Gradle project (and the Main Swift Package)."""
        extra_deps: list[str] = []
        extra_perms: list[str] = []
        if self.config.python_enabled:
            from ..python.site_packages import install_android_site_packages

            self.delegate.install_cpython()
            merged = install_android_site_packages(
                self.project_path, [a.value for a in self.android_data.archs], clean=clean
            )
            extra_deps, extra_perms = merged.gradle_dependencies, merged.permissions

        # Resolve both toolchains before writing anything that names them.
        _ = self.swift_android_sdk
        result = self.bootstrap.generate(
            platform="android",
            aar=aar,
            extra_gradle_dependencies=extra_deps,
            extra_permissions=extra_perms,
            sdk_path=self.toolchain.sdk_path,
        )
        assert result is not None
        return result

    def generate_templates(self, force: bool = False) -> None:
        """Write the editable Android templates to the project root."""
        for name, content in self.bootstrap.android_templates().items():
            path = self.project_path / name
            existed = path.exists()
            if force or not existed:
                path.write_text(content, encoding="utf-8")
                print(f"[nucleant] {'Overwrote' if existed else 'Generated'} {name}")
            else:
                print(f"[nucleant] {name} already exists. Use --force to overwrite.")

    def _gradle_task(self, variant: str, aar: bool, bundle: bool) -> str:
        if variant not in ("debug", "release"):
            raise GradleProjectError(f"Unknown variant {variant!r}; expected 'debug' or 'release'")
        suffix = "Debug" if variant == "debug" else "Release"
        return f"bundle{suffix}" if bundle and not aar else f"assemble{suffix}"

    def gradle_assemble(
        self,
        variant: str = "debug",
        aar: bool = False,
        bundle: bool = False,
        clean: bool = False,
    ) -> list[Path]:
        task = self._gradle_task(variant, aar, bundle)

        env = self.swift.env()
        env["JAVA_HOME"] = self.toolchain.java_path
        if sys.platform == "linux" and "JAVA_TOOL_OPTIONS" not in env:
            env["JAVA_TOOL_OPTIONS"] = "-XX:TieredStopAtLevel=1 -Xshare:off"

        gradlew = self.gradle_dir / ("gradlew.bat" if sys.platform == "win32" else "gradlew")
        if not gradlew.exists():
            raise GradleProjectError(f"Gradle project not generated yet: {gradlew} missing.")

        args = [str(gradlew)]
        if clean:
            args.append("clean")
        args.append(task)

        print(f"[nucleant] Running Gradle task: {' '.join(args[1:])}")
        result = subprocess.run(
            args, cwd=self.gradle_dir, env=env, shell=sys.platform == "win32"
        )
        if result.returncode != 0:
            raise GradleProjectError(f"./gradlew {' '.join(args[1:])} exited with code {result.returncode}")

        if aar:
            aar_dir = self.gradle_dir / "app" / "build" / "outputs" / "aar"
            artifacts = sorted(aar_dir.rglob(f"*{variant}*.aar"))
        elif bundle:
            artifacts = self.find_bundles(variant)
        else:
            artifacts = self.find_apks(variant)
        if not artifacts:
            raise GradleProjectError("Expected build artifacts were not produced.")

        if len(artifacts) > 1:
            print(f"\n[nucleant] Found {len(artifacts)} artifacts:")
            for art in artifacts:
                print(f"  • {art.name} ({art.parent.name}) -> {art}")
        else:
            print(f"\n[nucleant] Found artifact: {artifacts[0]}")
        return artifacts

    def build(
        self,
        variant: str = "debug",
        aar: bool = False,
        bundle: bool = False,
        clean: bool = False,
    ) -> list[Path]:
        """pre_build hook → generate → gradlew assemble/bundle."""
        run_hook(self.android_data.pre_build, self.project_path)
        self.generate(aar=aar, clean=clean)
        return self.gradle_assemble(variant, aar=aar, bundle=bundle, clean=clean)

    archive = build

    # ------------------------------------------------------------------
    # Devices / run
    # ------------------------------------------------------------------

    def _require_sdk(self) -> tuple[ADB, AndroidEmulator]:
        if self.adb is None or self.emulator is None:
            # No SDK found by the cheap lookup: resolve (and install) it.
            _ = self.toolchain
        assert self.adb is not None and self.emulator is not None
        return self.adb, self.emulator

    def devices(self) -> list[dict]:
        """Attached adb devices and available AVDs."""
        adb, emulator = self._require_sdk()
        items: list[dict] = list(adb.devices())
        for name in emulator.list_avds():
            items.append({"name": name, "kind": "avd"})
        return items

    def find_apks(self, variant: str = "debug", unsigned_only: bool = False) -> list[Path]:
        apk_base_dir = self.gradle_dir / "app" / "build" / "outputs" / "apk"
        if not apk_base_dir.exists():
            return []
        apks = [
            p
            for p in apk_base_dir.rglob(f"*{variant}*.apk")
            if not (unsigned_only and "-signed" in p.name)
        ]

        def sort_key(p: Path) -> int:
            if "-signed" in p.name:
                return 0
            if "-unsigned" in p.name:
                return 2
            return 1

        return sorted(apks, key=sort_key)

    def find_bundles(self, variant: str = "release", unsigned_only: bool = False) -> list[Path]:
        bundle_base_dir = self.gradle_dir / "app" / "build" / "outputs" / "bundle"
        if not bundle_base_dir.exists():
            return []
        return sorted(
            p
            for p in bundle_base_dir.rglob(f"*{variant}*.aab")
            if not (unsigned_only and "-signed" in p.name)
        )

    def _pick_target(self, adb: ADB, emulator: AndroidEmulator, uuid: str | None, name: str | None) -> str:
        """An adb serial: the one given, the AVD named (booted), the first
        online device, or the default AVD."""
        if uuid is not None:
            adb.wait_for_device(uuid)
            return uuid
        if name is not None:
            return emulator.boot_and_wait(name, adb)
        online = [d for d in adb.devices() if d["state"] == "device"]
        if online:
            print(f"[nucleant] Using connected device {online[0]['serial']}")
            return online[0]["serial"]
        avds = emulator.list_avds()
        avd = DEFAULT_AVD_NAME if DEFAULT_AVD_NAME in avds else (avds[0] if avds else DEFAULT_AVD_NAME)
        print(f"[nucleant] No device connected; booting AVD {avd!r}")
        return emulator.boot_and_wait(avd, adb)

    def run(
        self,
        uuid: str | None = None,
        name: str | None = None,
        variant: str = "debug",
        clean: bool = False,
        logcat: bool = False,
    ) -> None:
        """Build, install and launch — the Android `swift run`."""
        if uuid is not None and name is not None:
            raise GradleProjectError("run takes at most one of --uuid / --name")

        apks = self.build(variant, clean=clean)
        adb, emulator = self._require_sdk()
        serial = self._pick_target(adb, emulator, uuid, name)

        device_abis = adb.get_device_abis(serial)
        print(f"[nucleant] Detected device ABIs: {', '.join(device_abis)}")
        best_apk = self._match_apk(apks, device_abis)

        print(f"[nucleant] Installing {best_apk.name} on {serial}...")
        adb.install(best_apk, serial)
        adb.start_app(serial, self.android_data.package_name)
        if logcat:
            self._stream_logcat(adb, serial)

    @staticmethod
    def _match_apk(apks: list[Path], device_abis: list[str]) -> Path:
        for abi in device_abis:
            flavor = abi.replace("-", "_")
            matches = [a for a in apks if flavor in a.name]
            if matches:
                signed = [a for a in matches if "unsigned" not in a.name]
                chosen = (signed or matches)[0]
                print(f"[nucleant] Matched ABI '{abi}' -> {chosen.name}")
                return chosen
        print(f"[nucleant] No ABI-specific APK; using {apks[0].name}")
        return apks[0]

    def _stream_logcat(self, adb: ADB, serial: str) -> None:
        """Follow the app's own log lines until Ctrl-C."""
        package = self.android_data.package_name
        pid = ""
        for _ in range(20):
            try:
                pid = adb.shell(serial, "pidof", "-s", package).strip()
            except ADBError:
                pid = ""
            if pid:
                break
            time.sleep(0.5)
        if not pid:
            print(f"[nucleant] {package} is not running; no logcat to follow.")
            return
        print(f"[nucleant] logcat for {package} (pid {pid}) — Ctrl-C to stop")
        try:
            subprocess.run([adb.binary, "-s", serial, "logcat", "--pid", pid])
        except KeyboardInterrupt:
            pass

    # ------------------------------------------------------------------
    # Signing & keystore generation
    # ------------------------------------------------------------------

    def _jdk_tool(self, name: str) -> Path:
        tool = Path(self.toolchain.java_path) / "bin" / (f"{name}.exe" if sys.platform == "win32" else name)
        if not tool.exists():
            raise GradleProjectError(f"{name} executable missing from JDK home at {tool}")
        return tool

    def genkey(
        self,
        keystore_path: Path | str,
        storepass: str,
        keyalias: str,
        keypass: str | None = None,
        dname: str | None = None,
        validity: int = 10000,
    ) -> Path:
        """Generate a new release keystore with keytool."""
        keystore_path = Path(keystore_path).resolve()
        if keystore_path.exists():
            raise GradleProjectError(f"Keystore file already exists at: {keystore_path}")
        keystore_path.parent.mkdir(parents=True, exist_ok=True)

        args = [
            str(self._jdk_tool("keytool")),
            "-genkeypair", "-v",
            "-keystore", str(keystore_path),
            "-alias", keyalias,
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", str(validity),
            "-storepass", storepass,
            "-dname", dname or f"CN={self.config.app_name}, O=NucleantUI, C=US",
            "-keypass", keypass or storepass,
        ]
        self._run_java_tool(args, "keytool generation failed")
        return keystore_path

    def sign_project_artifact(
        self,
        keystore: Path | str,
        storepass: str,
        keyalias: str,
        keypass: str | None = None,
        variant: str = "release",
        bundle: bool = False,
    ) -> list[Path]:
        """Sign every unsigned artifact of the variant."""
        keystore_path = Path(keystore).resolve()
        signed: list[Path] = []
        if bundle:
            targets = self.find_bundles(variant, unsigned_only=True)
            if not targets:
                raise GradleProjectError(f"No unsigned {variant} AABs found to sign.")
            print(f"[nucleant] Signing {len(targets)} App Bundle(s)...")
            for target in targets:
                signed.append(self._sign_aab(target, keystore_path, storepass, keyalias, keypass))
                print(f"  [✓] Signed AAB: {signed[-1].name}")
        else:
            targets = self.find_apks(variant, unsigned_only=True)
            if not targets:
                raise GradleProjectError(f"No unsigned {variant} APKs found to sign.")
            print(f"[nucleant] Signing {len(targets)} APK(s)...")
            for target in targets:
                signed.append(self._sign_apk(target, keystore_path, storepass, keyalias, keypass))
                print(f"  [✓] Signed APK: {signed[-1].name}")
        return signed

    @staticmethod
    def _signed_name(path: Path, suffix: str) -> Path:
        if "-unsigned" in path.name:
            return path.with_name(path.name.replace("-unsigned", "-signed"))
        return path.with_name(f"{path.stem}-signed{suffix}")

    def _sign_apk(self, apk: Path, keystore: Path, storepass: str, keyalias: str, keypass: str | None) -> Path:
        build_tools = Path(self.toolchain.sdk_path) / "build-tools"
        versions = sorted(d for d in build_tools.iterdir() if d.is_dir()) if build_tools.is_dir() else []
        if not versions:
            raise GradleProjectError(f"No build-tools found under {build_tools} to locate apksigner.")
        apksigner = versions[-1] / ("apksigner.bat" if sys.platform == "win32" else "apksigner")
        if not apksigner.exists():
            raise GradleProjectError(f"apksigner executable missing at {apksigner}")

        out = self._signed_name(apk, ".apk")
        args = [
            str(apksigner), "sign",
            "--ks", str(keystore),
            "--ks-pass", f"pass:{storepass}",
            "--ks-key-alias", keyalias,
            "--out", str(out),
        ]
        if keypass:
            args += ["--key-pass", f"pass:{keypass}"]
        args.append(str(apk))
        self._run_java_tool(args, "Signing command failed")
        return out

    def _sign_aab(self, aab: Path, keystore: Path, storepass: str, keyalias: str, keypass: str | None) -> Path:
        out = self._signed_name(aab, ".aab")
        shutil.copy2(aab, out)
        args = [
            str(self._jdk_tool("jarsigner")),
            "-keystore", str(keystore),
            "-storepass", storepass,
            str(out),
            keyalias,
        ]
        if keypass:
            args += ["-keypass", keypass]
        self._run_java_tool(args, "Signing command failed")
        return out

    def _run_java_tool(self, args: list[str], message: str) -> None:
        env = os.environ.copy()
        env["JAVA_HOME"] = self.toolchain.java_path
        result = subprocess.run(
            args, env=env, shell=sys.platform == "win32", capture_output=True, text=True
        )
        if result.returncode != 0:
            raise GradleProjectError(f"{message}:\n{result.stderr or result.stdout}")
