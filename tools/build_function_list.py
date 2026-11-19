"""Build src/matlab_practice/checker/matlab_functions.txt from MathWorks' official function list.

Source: the MATLAB "Functions" reference list (core MATLAB only, no toolboxes)
    https://www.mathworks.com/help/matlab/referencelist.html?type=function&listtype=alpha
That page is drawn by JavaScript from this data file:
    https://www.mathworks.com/help/matlab/referencelist_function_alpha.xml

MathWorks' CDN usually refuses scripts (HTTP 403), so the reliable way is:

1. Open the data-file URL above in a normal browser and save it (File > Save Page As), then
       uv run python tools/build_function_list.py --xml path/to/referencelist_function_alpha.xml
2. Or, on the reference-list page, run this in the browser's developer console and save the
   printed text to a file, then pass it with --names:
       const d = new DOMParser().parseFromString(
         await (await fetch('/help/matlab/referencelist_function_alpha.xml')).text(), 'application/xml');
       [...d.getElementsByTagName('ref')].filter(r => !r.getAttribute('addon'))
         .map(r => r.getAttribute('name').trim().replace(/\\s*\\(.*\\)$/, '')).join('\\n')

With no arguments the script tries to download the XML itself.

Rules: support-package entries (``addon`` attribute) are dropped; names like ``fopen (serial)``
keep only ``fopen``; operator/keyword entries ("+", "if, elseif, else") are dropped (the checker
handles syntax itself); dotted names are kept only for a few namespaces students may meet
(``containers.Map``, ``matlab.lang.makeValidName``, ...). SUPPLEMENT adds the operator function
names and documented aliases the alphabetical list doesn't show by name. Octave-only names from the
checker's own table are removed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from matlab_practice.checker.tables import OCTAVE_END_KEYWORDS, OCTAVE_FUNCTIONS  # noqa: E402

PAGE_URL = "https://www.mathworks.com/help/matlab/referencelist.html?type=function&listtype=alpha"
XML_URL = "https://www.mathworks.com/help/matlab/referencelist_function_alpha.xml"
OUT = ROOT / "src" / "matlab_practice" / "checker" / "matlab_functions.txt"

IDENT = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
DOTTED = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$")
KEEP_DOTTED = re.compile(r"^(MException|RandStream|containers|event|matlab\.lang|parallel\.pool)\.")
EXCLUDE_DOTTED = re.compile(r"^matlab\.lang\.(Workspace|obfuscateNames)")

# Documented MATLAB functions the alphabetical list only shows under operator symbols
# (e.g. "-" -> minus), plus documented lower-case aliases.
SUPPLEMENT = """
plus minus uminus uplus times mtimes rdivide ldivide mrdivide mldivide power mpower
eq ne lt le gt ge and or not xor colon transpose ctranspose horzcat vertcat
inf nan display
""".split()


def names_from_xml(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    out = []
    for ref in root.iter():
        if not ref.tag.endswith("ref") or ref.get("addon"):
            continue
        out.append(ref.get("name", ""))
    return out


def clean(raw_names: list[str]) -> list[str]:
    keep = set()
    for raw in raw_names:
        name = re.sub(r"\s*\(.*\)$", "", raw.strip())
        if IDENT.match(name):
            keep.add(name)
        elif DOTTED.match(name) and KEEP_DOTTED.match(name) and not EXCLUDE_DOTTED.match(name):
            keep.add(name)
    keep.update(SUPPLEMENT)
    keep -= set(OCTAVE_FUNCTIONS)
    keep -= set(OCTAVE_END_KEYWORDS)
    return sorted(keep, key=lambda s: (s.lower(), s))


def download() -> str:
    req = urllib.request.Request(XML_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--xml", type=Path, help="saved referencelist_function_alpha.xml")
    src.add_argument("--names", type=Path, help="names extracted in the browser (whitespace separated)")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--release", default="", help="MATLAB release shown in the docs, for the header")
    args = ap.parse_args(argv)

    if args.xml:
        raw = names_from_xml(args.xml.read_text(encoding="utf-8"))
        how = f"parsed from {XML_URL}"
    elif args.names:
        raw = args.names.read_text(encoding="utf-8").split()
        how = f"extracted in a browser from {XML_URL} (entries without an add-on)"
    else:
        try:
            raw = names_from_xml(download())
        except Exception as exc:  # noqa: BLE001
            print(f"Could not download {XML_URL}: {exc}", file=sys.stderr)
            print("Save it with a browser and pass --xml FILE (see --help).", file=sys.stderr)
            return 2
        how = f"downloaded from {XML_URL}"

    names = clean(raw)
    release = f" (docs release {args.release})" if args.release else ""
    header = [
        "# MATLAB functions and constants (core MATLAB only, no toolboxes), one per line.",
        f"# Source: MathWorks official function reference list{release}",
        f"#   {PAGE_URL}",
        f"#   data {how}",
        f"# Built {dt.date.today().isoformat()} by tools/build_function_list.py: {len(names)} names.",
        "# Support-package entries dropped; operator function names and inf/nan/display added;",
        "# Octave-only names removed. Lines starting with # are comments.",
        "# To add a name by hand, add it to SUPPLEMENT in tools/build_function_list.py and rebuild,",
        "# or append it at the end of this file (keep the list sorted).",
    ]
    args.out.write_text("\n".join(header + names) + "\n", encoding="utf-8")
    print(f"wrote {len(names)} names to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
