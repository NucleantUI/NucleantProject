"""The ``nucleant.toml`` project model.

``nucleant.toml`` is the only place NucleantProject reads project settings
from. Its root table is what ``[tool.nucleant]`` in pyproject.toml will be
later; pyproject.toml itself is only there for uv to track the ``nucleant``
dev tool (and, once the Python layer is back, the app's Python packages).

Layout::

    app_name = "MyApp"
    bootstrap = "nucleantui"

    [toolchain]        # Swift: version, swiftly, Swift SDK overrides
    [swift]            # the app's Swift — parsed by the bootstrap
    [android]          # Gradle / Android
    [ios]  [macos]     # Xcode / Apple
    [linux]            # swift run on Linux
    [wasm]             # presence = install the wasm Swift SDK
    [python]           # the Python layer (transferred, not enabled yet)
"""

from __future__ import annotations

import tomllib
from enum import StrEnum
from pathlib import Path

from .tools import resolve_module_name

NUCLEANT_TOML = "nucleant.toml"

DEFAULT_SWIFT_VERSION = "6.3.3"
DEFAULT_BOOTSTRAP = "nucleantui"

#: The Python layer is transferred from ksproject (site-packages, CPython for
#: Android/Apple) but switched off: a NucleantUI app is pure Swift for now.
#: Flip this when the layer comes back; `[python] enabled = true` in a project
#: then turns it on per project.
PYTHON_SUPPORT_ENABLED = False


class NucleantTomlError(Exception):
    pass


def _path(value) -> Path | None:
    return Path(value).expanduser() if value else None


class ToolchainData:
    """``[toolchain]`` — which Swift builds the app."""

    #: Toolchain version, installed and selected with swiftly.
    swift: str
    #: Install/select the toolchain with swiftly. False: use `swift` on PATH.
    swiftly: bool
    #: Swift SDK ids to build with, when not ``swift-<ver>-RELEASE_<kind>``.
    android_sdk: str | None
    wasm_sdk: str | None

    def __init__(self, data: dict):
        self.swift = str(data.get("swift", DEFAULT_SWIFT_VERSION))
        self.swiftly = bool(data.get("swiftly", True))
        self.android_sdk = data.get("android_sdk")
        self.wasm_sdk = data.get("wasm_sdk")


class AndroidData:
    """``[android]``."""

    class Arch(StrEnum):
        ARM64_V8A = "arm64-v8a"
        X86_64 = "x86_64"

    class ServiceData:
        name: str
        entrypoint: str
        foreground: bool
        foreground_service_type: str | None
        start_type: str
        notification_title: str
        notification_text: str
        notification_icon: str

        def __init__(self, data: dict):
            self.name = data["name"]
            # Module syntax, even if ".py" or "/" slipped in.
            raw_entry = data.get("entrypoint", "service_main")
            self.entrypoint = raw_entry.replace("/", ".").replace(".py", "")
            self.foreground = data.get("foreground", False)
            self.foreground_service_type = data.get("foreground_service_type")
            self.start_type = data.get("start_type", "START_NOT_STICKY")
            self.notification_title = data.get("notification_title", f"{self.name} is running")
            self.notification_text = data.get("notification_text", "Background task active")
            self.notification_icon = data.get("notification_icon", "stat_notify_sync")

    package_name: str
    archs: list["AndroidData.Arch"]
    api: int | None
    min_api: int | None
    sdk: str | None
    ndk: str | None
    ndk_api: int | None
    sdk_path: Path | None
    ndk_path: Path | None
    java_path: Path | None
    global_tools: bool
    global_tools_path: Path | None
    icon: str | None
    presplash: str | None
    presplash_color: str | None
    presplash_lottie: str | None
    permissions: list[str]
    meta_data: dict[str, str]
    gradle_dependencies: list[str]
    gradle_plugins: list[str]
    services: list["AndroidData.ServiceData"]
    version_code: int
    version_name: str
    include_files: list[tuple[str, list[str]]]
    pre_build: Path | None
    post_build: Path | None
    byte_compile_python: bool
    universal_apk: bool

    def __init__(self, data: dict):
        if "package_name" not in data:
            raise NucleantTomlError("[android] needs a package_name")
        self.package_name = data["package_name"]
        try:
            self.archs = [self.Arch(a) for a in data.get("archs", ["arm64-v8a"])]
        except ValueError as exc:
            raise NucleantTomlError(
                f"[android] archs: {exc}; supported: "
                + ", ".join(a.value for a in self.Arch)
            ) from exc
        self.api = data.get("api")
        self.min_api = data.get("min_api")
        self.sdk = data.get("sdk")
        self.ndk = data.get("ndk")
        self.ndk_api = data.get("ndk_api")
        self.sdk_path = _path(data.get("sdk_path"))
        self.ndk_path = _path(data.get("ndk_path"))
        self.java_path = _path(data.get("java_path"))
        self.global_tools = bool(data.get("global_tools", False))
        self.global_tools_path = _path(data.get("global_tools_path"))
        self.icon = data.get("icon")
        self.presplash = data.get("presplash")
        self.presplash_color = data.get("presplash_color") or "#FFFFFF"
        self.presplash_lottie = data.get("presplash_lottie")
        self.permissions = list(data.get("permissions", []))
        self.meta_data = dict(data.get("meta_data", {}))
        self.gradle_dependencies = list(data.get("gradle_dependencies", []))
        self.gradle_plugins = list(data.get("gradle_plugins", []))
        self.include_files = []
        for item in data.get("include_files", []):
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                dest = str(item[0])
                if len(item) == 2 and isinstance(item[1], (list, tuple)):
                    sources = [str(x) for x in item[1]]
                else:
                    sources = [str(x) for x in item[1:]]
                self.include_files.append((dest, sources))
        self.services = [self.ServiceData(s) for s in data.get("services", [])]
        self.version_code = int(data.get("version_code", 1))
        self.version_name = str(data.get("version_name", "1.0"))
        self.pre_build = _path(data.get("pre_build"))
        self.post_build = _path(data.get("post_build"))
        self.byte_compile_python = bool(data.get("byte_compile_python", True))
        self.universal_apk = bool(data.get("universal_apk", True))

    def tools_root(self, working_dir: Path) -> Path:
        """Root for nucleant-managed tools and caches (Android SDK/NDK, CPython).

        ``global_tools = false`` (default) → ``<project>/.nucleant``.
        ``global_tools = true``            → ``global_tools_path`` if set, else ``~/.nucleant``.
        """
        if not self.global_tools:
            return working_dir / ".nucleant"
        if self.global_tools_path is not None:
            return self.global_tools_path
        return Path.home() / ".nucleant"


class _AppleTargetData:
    bundle_id: str
    info_plist: dict
    entitlements: dict
    permissions: list[str]
    developer_team: str | None
    minimum_deployment: str | None
    version: str
    build_number: str
    pre_build: Path | None
    post_build: Path | None

    _section = "apple"

    def __init__(self, data: dict):
        if "bundle_id" not in data:
            raise NucleantTomlError(f"[{self._section}] needs a bundle_id")
        self.bundle_id = data["bundle_id"]
        self.info_plist = dict(data.get("info_plist", {}))
        self.entitlements = dict(data.get("entitlements", {}))
        self.permissions = list(data.get("permissions", []))
        self.developer_team = data.get("developer_team") or None
        self.minimum_deployment = data.get("minimum_deployment")
        self.version = str(data.get("version", "1.0"))
        self.build_number = str(data.get("build_number", "1"))
        self.pre_build = _path(data.get("pre_build"))
        self.post_build = _path(data.get("post_build"))


class IosData(_AppleTargetData):
    """``[ios]``."""

    _section = "ios"
    frameworks: list[str]
    site_frameworks: list[str]

    def __init__(self, data: dict):
        super().__init__(data)
        self.frameworks = list(data.get("frameworks", []))
        self.site_frameworks = list(data.get("site_frameworks", []))


class MacosData(_AppleTargetData):
    """``[macos]``."""

    _section = "macos"
    archs: list[str]

    def __init__(self, data: dict):
        super().__init__(data)
        self.archs = list(data.get("archs", ["arm64", "x86_64"]))


class AppleData:
    def __init__(self, ios: IosData | None, macos: MacosData | None):
        self.ios = ios
        self.macos = macos


class PythonData:
    """``[python]`` — the Python layer. Off unless the CLI supports it."""

    def __init__(self, data: dict):
        self.enabled = bool(data.get("enabled", False))


class NucleantToml:
    """A loaded ``nucleant.toml``."""

    path: Path
    data: dict
    app_name: str
    name: str
    bootstrap: str
    command_plugins: list[str]
    toolchain: ToolchainData
    android: AndroidData | None
    apple: AppleData | None
    python: PythonData

    def __init__(self, path: Path, data: dict):
        self.path = path
        self.data = data
        self.app_name = str(data.get("app_name") or path.parent.name)
        self.name = str(data.get("name") or resolve_module_name(self.app_name))
        self.bootstrap = str(data.get("bootstrap", DEFAULT_BOOTSTRAP))
        self.command_plugins = list(data.get("command_plugins", []))
        self.toolchain = ToolchainData(data.get("toolchain", {}))
        self.android = AndroidData(data["android"]) if "android" in data else None
        ios = IosData(data["ios"]) if "ios" in data else None
        macos = MacosData(data["macos"]) if "macos" in data else None
        self.apple = AppleData(ios, macos) if (ios or macos) else None
        self.python = PythonData(data.get("python", {}))

    @property
    def has_linux(self) -> bool:
        return "linux" in self.data

    @property
    def has_wasm(self) -> bool:
        return "wasm" in self.data

    @property
    def python_enabled(self) -> bool:
        return PYTHON_SUPPORT_ENABLED and self.python.enabled

    @classmethod
    def find(cls, project_path: Path) -> Path:
        return Path(project_path).resolve() / NUCLEANT_TOML

    @classmethod
    def load(cls, project_path: Path) -> "NucleantToml":
        path = cls.find(project_path)
        if not path.is_file():
            raise NucleantTomlError(
                f"No {NUCLEANT_TOML} at {path.parent}. Run `nucleant init` first."
            )
        try:
            with path.open("rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            raise NucleantTomlError(f"{path}: {exc}") from exc
        config = cls(path, data)
        if config.python.enabled and not PYTHON_SUPPORT_ENABLED:
            print(
                "[nucleant] nucleant.toml has [python] enabled = true, but this "
                "version of nucleant ships the Python layer switched off — "
                "building without Python."
            )
        return config


def load_nucleant_toml(project_path: Path) -> NucleantToml:
    return NucleantToml.load(project_path)
