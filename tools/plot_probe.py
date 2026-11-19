"""Diagnose saving plots without a window: try each Octave program, Qt platform and toolkit.

    uv run python tools/plot_probe.py

Prints one line per combination: whether a PNG was written, plus the end of any error output.
Used in CI to find what works on Windows; safe to run anywhere.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from matlab_practice import engine  # noqa: E402

octave = engine.find_octave(refresh=True)
print(f"octave-cli: {octave.cli}\ngraphics program: {octave.gui}\nversion: {octave.version}")
if not octave.found:
    sys.exit(1)
folder = Path(octave.cli).parent
print("programs in", folder, ":", sorted(p.name for p in folder.iterdir() if p.name.lower().startswith(("octave", "gnuplot"))))

exes = [octave.cli] + [str(folder / n) for n in ("octave", "octave.exe", "octave-gui", "octave-gui.exe")
                       if (folder / n).is_file()]
platforms = [None, "offscreen", "minimal"] + (["windows"] if sys.platform == "win32" else [])
toolkits = ["", "qt", "gnuplot", "fltk"]
for exe in dict.fromkeys(exes):
    for qpa in platforms:
        for tk in toolkits:
            with tempfile.TemporaryDirectory() as tmp:
                png = Path(tmp) / "t.png"
                select = f"graphics_toolkit('{tk}'); " if tk else ""
                code = (f"{select}disp(graphics_toolkit()); set(0,'defaultfigurevisible','off'); "
                        f"plot(1:3); print('-dpng', '{png.as_posix()}');")
                env = os.environ.copy()
                env.pop("QT_QPA_PLATFORM", None)
                if qpa:
                    env["QT_QPA_PLATFORM"] = qpa
                try:
                    r = subprocess.run([exe, "--no-gui", "--norc", "--quiet", "--eval", code], capture_output=True,
                                       text=True, timeout=60, env=env, cwd=tmp)
                    out = (r.stdout + r.stderr).strip().replace("\n", " | ")
                    status = f"rc={r.returncode}"
                except subprocess.TimeoutExpired:
                    out, status = "", "TIMEOUT"
                ok = png.is_file() and png.stat().st_size > 500
                print(f"{'PNG ' if ok else 'none'} {Path(exe).name:16} qpa={qpa or '-':9} tk={tk or 'default':8} "
                      f"{status:8} {out[-160:]}")
