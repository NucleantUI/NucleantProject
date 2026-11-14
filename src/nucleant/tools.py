from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path


def which(name: str) -> str | None:
    return shutil.which(name)


def get_uv() -> str | None:
    return which("uv")


def load_dotenv(file_path: str | Path = ".env", quiet: bool = True) -> None:
    """Load ``KEY=value`` lines from a ``.env`` file into ``os.environ``.

    Values already in the environment win, so CI secrets are never replaced
    by a stale local file.
    """
    path = Path(file_path)
    if not path.is_file():
        return
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)
        if not quiet:
            print(f"[nucleant] loaded environment from {path}")
    except OSError as exc:
        print(f"[nucleant] could not read {path}: {exc}")


REPLACE_CHARS = ["-", ".", " "]

RESOLVE_REGEX = rf"[{''.join(REPLACE_CHARS)}]"


def resolve_module_name(name: str) -> str:
    return re.sub(RESOLVE_REGEX, "_", name.strip()).lower()


def run_hook(script: Path | None, project_path: Path, env: dict[str, str] | None = None) -> None:
    """Run a ``pre_build`` hook: ``uv run`` for ``.py``, else executed directly.

    Relative paths are relative to the project. ``WHEELHOUSE`` is set for
    hooks written for the ksproject era.
    """
    if script is None:
        return
    path = script if script.is_absolute() else project_path / script
    if not path.exists():
        raise FileNotFoundError(f"pre_build hook not found: {path}")
    hook_env = {**os.environ, **(env or {})}
    hook_env.setdefault("WHEELHOUSE", str(project_path / "wheelhouse"))
    hook_env["NUCLEANT_PROJECT_DIR"] = str(project_path)
    cmd = ["uv", "run", str(path)] if path.suffix == ".py" else [str(path)]
    print(f"[nucleant] pre_build: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=hook_env, cwd=project_path)
