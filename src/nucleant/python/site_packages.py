"""site_packages for each platform slice (Python layer — disabled for now).

The two ``install_*`` functions are ksproject's ``GradleProject`` /
``XcodeProject.install_site_packages`` lifted out of the project classes, so
those classes only call into Python when a project has it enabled.
"""

from __future__ import annotations

import platform
from pathlib import Path
from shutil import rmtree

from nucleant_bootstraps.platforms import (
    AndroidArm64Platform,
    AndroidPlatform,
    AndroidX86_64Platform,
    IOSArm64Platform,
    IOSSim_Arm64Platform,
    IOSSim_X86_64Platform,
    MacOSArm64Platform,
    MacOSPlatform,
    MacOSX86_64Platform,
)

from .collect_gradle_configs import MergedGradleConfig, collect_and_merge
from .pip_install import PipInstaller
from .python_apple import copy_site_frameworks

_ANDROID_PLATFORMS: dict[str, type[AndroidPlatform]] = {
    "arm64-v8a": AndroidArm64Platform,
    "x86_64": AndroidX86_64Platform,
}

IOS_MODULE_TEMPLATE = Path(__file__).parent / "templates" / "ios.file"


def android_platforms(project_path: Path, archs: list[str]) -> list[AndroidPlatform]:
    out = []
    for arch in archs:
        cls = _ANDROID_PLATFORMS.get(str(arch))
        if cls is None:
            raise ValueError(f"No Android Python platform for arch {arch}")
        out.append(cls(str(project_path)))
    return out


def install_android_site_packages(
    project_path: Path, archs: list[str], clean: bool = False
) -> MergedGradleConfig:
    """Install the project into per-ABI site_packages and merge their
    ``.gradle/*.json`` (extra gradle dependencies + permissions)."""
    dirs = []
    for plat in android_platforms(project_path, archs):
        if clean:
            rmtree(plat.site_packages, ignore_errors=True)
        Path(plat.site_packages).mkdir(parents=True, exist_ok=True)
        PipInstaller.install(
            uv_src=str(project_path), platform=plat, site_packages=plat.site_packages
        )
        dirs.append(Path(plat.site_packages))
    return collect_and_merge(dirs)


def install_apple_site_packages(
    project_path: Path, xcode_dir: Path, platforms: list[str], simulator: bool = False
) -> None:
    """Install into per-slice site_packages; move wheel-shipped xcframeworks
    into ``Frameworks/``."""
    machine = platform.machine()
    classes = []
    if "iOS" in platforms:
        if simulator:
            classes.append(IOSSim_Arm64Platform if machine == "arm64" else IOSSim_X86_64Platform)
        else:
            classes.append(IOSArm64Platform)
    if "macOS" in platforms:
        classes.append(MacOSArm64Platform if machine == "arm64" else MacOSX86_64Platform)

    for cls in classes:
        plat = cls(str(project_path))
        site = Path(plat.site_packages)
        site.mkdir(parents=True, exist_ok=True)
        PipInstaller.install(uv_src=str(project_path), platform=plat, site_packages=str(site))
        if not isinstance(plat, MacOSPlatform):
            ios_module = site / "ios.py"
            if not ios_module.exists():
                ios_module.write_bytes(IOS_MODULE_TEMPLATE.read_bytes())

    copy_site_frameworks(xcode_dir / "Frameworks", xcode_dir / "site_packages")
