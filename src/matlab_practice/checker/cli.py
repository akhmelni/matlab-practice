"""Command line: ``mcheck FILE.m [--profile authoring] [--ban NAME ...] [--ban-op OP ...] [--allow NAME ...] [--json]``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .rules import PROFILES, check


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mcheck", description="Check that a .m file is plain MATLAB (no Octave-only code).")
    ap.add_argument("file", type=Path, help="the .m file to check")
    ap.add_argument("--profile", choices=PROFILES, default="student")
    ap.add_argument("--ban", action="append", default=[], metavar="NAME", help="function the code may not call")
    ap.add_argument("--ban-op", action="append", default=[], metavar="OP", help="operator spelling, e.g. '^0.5'")
    ap.add_argument("--allow", action="append", default=[], metavar="NAME", help="extra name defined elsewhere")
    ap.add_argument("--json", action="store_true", help="print the issues as JSON")
    args = ap.parse_args(argv)

    try:
        code = args.file.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"mcheck: can't read {args.file}: {exc}", file=sys.stderr)
        return 2
    issues = check(
        code,
        filename=args.file.name,
        profile=args.profile,
        banned_functions=args.ban,
        banned_operators=args.ban_op,
        extra_allowed=args.allow,
    )
    if args.json:
        print(json.dumps([i.to_dict() for i in issues], indent=2))
    else:
        for i in issues:
            print(f"{args.file}:{i.line}:{i.col}: {i.rule}: {i.message}")
    return 1 if any(i.severity == "error" for i in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
