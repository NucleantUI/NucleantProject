"""``nucleant linux …`` — the desktop app on Linux, through SwiftPM."""

from __future__ import annotations

import argparse

from ..project import DesktopProject


class LinuxCommands:

    def register(self, sub: argparse._SubParsersAction) -> None:
        linux = sub.add_parser("linux", help="Linux commands")
        lsub = linux.add_subparsers(dest="command", required=True)

        run = lsub.add_parser("run", help="Build and run on this Linux machine (`swift run`)")
        run.add_argument("variant", nargs="?", default="debug", choices=["debug", "release"])
        run.add_argument("app_args", nargs=argparse.REMAINDER,
                         help="Arguments passed to the app (after --)")
        run.set_defaults(func=self.run)

    def run(self, args: argparse.Namespace) -> int:
        app_args = [a for a in args.app_args if a != "--"] if args.app_args else []
        return DesktopProject().run("linux", configuration=args.variant, app_args=app_args)
