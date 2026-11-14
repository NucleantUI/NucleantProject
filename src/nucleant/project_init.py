"""``nucleant init`` — make a directory a NucleantProject (new or existing).

Writes nucleant.toml, a starter NucleantUI app under ``Sources/<Target>``,
``.swift-version``, the editable Android templates and the desktop
``Package.swift``. Never overwrites a file that is already there.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from nucleant_bootstraps.bootstraps.nucleantui import ANDROID_TEMPLATE_FILES
from nucleant_bootstraps.bootstraps.nucleantui.swift_config import portable_relpath
from nucleant_bootstraps.tools import swift_identifier

from . import init_template as tmpl
from .nucleant_toml import DEFAULT_SWIFT_VERSION, NUCLEANT_TOML
from .project import DesktopProject
from .tools import get_uv, resolve_module_name


class ProjectInitError(Exception):
    pass


class ProjectInit:

    def __init__(
        self,
        project_path: Path,
        app_name: str | None = None,
        nucleantui_path: Path | None = None,
    ) -> None:
        self.project_path = Path(project_path).resolve()
        self.app_name = app_name or self.project_path.name
        self.module_name = resolve_module_name(self.app_name)
        self.target = swift_identifier(self.app_name)
        # `struct MyApp` inside module `MyApp` makes the type and the module
        # ambiguous to Swift, hence the SwiftUI-style `…App` suffix.
        self.entry = f"{self.target}App"
        self.nucleantui_path = Path(nucleantui_path).resolve() if nucleantui_path else None

    def run(self) -> None:
        self.project_path.mkdir(parents=True, exist_ok=True)
        if not (self.project_path / "pyproject.toml").exists():
            self._uv_init()
        self._write_nucleant_toml()
        self._write_app_sources()
        self._write_if_missing(".swift-version", f"{DEFAULT_SWIFT_VERSION}\n")
        self._write_if_missing(".env", tmpl.ENV_TEMPLATE)
        self._update_gitignore()
        for name, content in ANDROID_TEMPLATE_FILES.items():
            self._write_if_missing(name, content)
        package = DesktopProject(self.project_path).generate()
        print(f"[nucleant] desktop package: {package / 'Package.swift'}")
        print(f"[nucleant] initialized {self.app_name} at {self.project_path}")
        print("[nucleant] next: `uv run nucleant toolchain install`, then e.g. "
              "`uv run nucleant apple macos run` or `uv run nucleant android run`")

    # ------------------------------------------------------------------

    def _uv_init(self) -> None:
        """A bare pyproject.toml: uv tracks the nucleant tool, nothing else yet."""
        uv = get_uv()
        if uv is None:
            print("[nucleant] `uv` not found; skipping pyproject.toml (add nucleant-project with uv later)")
            return
        result = subprocess.run(
            [uv, "init", "--bare", "--name", self.module_name.replace("_", "-"), str(self.project_path)]
        )
        if result.returncode != 0:
            raise ProjectInitError(f"`uv init` exited with code {result.returncode}")

    def _write_if_missing(self, rel: str, content: str) -> bool:
        path = self.project_path / rel
        if path.exists():
            print(f"[nucleant] {rel} exists; leaving it")
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"[nucleant] wrote {rel}")
        return True

    def _write_nucleant_toml(self) -> None:
        rel_ui = None
        if self.nucleantui_path is not None:
            if not (self.nucleantui_path / "Package.swift").is_file():
                raise ProjectInitError(f"{self.nucleantui_path} has no Package.swift")
            rel_ui = portable_relpath(self.nucleantui_path, self.project_path)
        self._write_if_missing(
            NUCLEANT_TOML,
            tmpl.nucleant_toml(self.app_name, self.module_name, self.target, self.entry, rel_ui),
        )

    def _write_app_sources(self) -> None:
        sources = self.project_path / "Sources" / self.target
        if sources.is_dir() and any(sources.glob("*.swift")):
            print(f"[nucleant] Sources/{self.target} has Swift files; leaving them")
            return
        self._write_if_missing(
            f"Sources/{self.target}/{self.entry}.swift",
            tmpl.app_swift(self.app_name, self.entry),
        )

    def _update_gitignore(self) -> None:
        path = self.project_path / ".gitignore"
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        have = {line.strip() for line in existing.splitlines()}
        missing = [
            line for line in tmpl.GITIGNORE_BLOCK.splitlines()
            if line and not line.startswith("#") and line not in have
        ]
        if not missing:
            return
        sep = "" if not existing or existing.endswith("\n") else "\n"
        block = "\n# nucleant\n" + "\n".join(missing) + "\n"
        path.write_text(existing + sep + block, encoding="utf-8")
        print(f"[nucleant] .gitignore: added {', '.join(missing)}")
