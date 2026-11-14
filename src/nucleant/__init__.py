"""NucleantProject — the ``nucleant`` CLI.

Builds and runs NucleantUI apps: ``nucleant init``, then ``nucleant android
run``, ``nucleant apple {ios,sim,macos} run`` or ``nucleant linux run``.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("nucleant-project")
except PackageNotFoundError:  # running from a source tree
    __version__ = "0.0.0"


def main() -> None:
    from .cli import main as _main

    _main()
