"""Run student code and evaluators in GNU Octave.

Every Run / Submit starts a fresh Octave process in a temporary folder, so nothing leaks between
attempts. The fast `octave-cli` is used unless the code draws plots; plots need Octave's Qt graphics,
which only the full `octave` program has (started with --no-gui, so no window opens).
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from . import config, octave_compat
from .errors import matlab_message
from .problems import Problem

IS_WINDOWS = sys.platform == "win32"
RUN_TIMEOUT_S = 10
MAX_OUTPUT = 20_000

PLOT_WORDS = {
    "plot", "figure", "subplot", "bar", "barh", "scatter", "hist", "histogram", "surf", "mesh", "fplot",
    "semilogx", "semilogy", "loglog", "area", "stem", "stairs", "errorbar", "polar", "polarplot",
    "contour", "contourf", "quiver", "pie", "imagesc", "image", "line", "fill", "patch", "plot3",
    "scatter3", "title", "xlabel", "ylabel", "zlabel", "legend", "axis", "grid", "hold", "text",
    "ezplot", "boxplot", "yyaxis", "xlim", "ylim", "gca", "gcf", "colorbar", "colormap", "subtitle",
}


@dataclass
class Octave:
    cli: str | None
    gui: str | None
    version: str | None = None

    @property
    def found(self) -> bool:
        return self.cli is not None


def _version_key(path: str) -> tuple:
    m = re.search(r"Octave-(\d+)\.(\d+)\.(\d+)", path)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def _cli_candidates() -> list[str]:
    found: list[str] = []
    configured = config.setting("OCTAVE")
    if configured:
        found.append(configured)
    if IS_WINDOWS:
        roots = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", ""),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"), r"C:\Octave"]
        hits: list[str] = []
        for root in filter(None, roots):
            hits += glob.glob(os.path.join(root, "GNU Octave", "Octave-*", "mingw64", "bin", "octave-cli.exe"))
            hits += glob.glob(os.path.join(root, "Octave-*", "mingw64", "bin", "octave-cli.exe"))
        found += sorted(hits, key=_version_key, reverse=True)
    else:
        found += ["/opt/homebrew/bin/octave-cli", "/usr/local/bin/octave-cli", "/usr/bin/octave-cli"]
        found += sorted(glob.glob("/Applications/Octave-*.app/Contents/Resources/usr/bin/octave-cli"), reverse=True)
    on_path = shutil.which("octave-cli")
    if on_path:
        found.append(on_path)
    return found


def _gui_for(cli: str) -> str | None:
    configured = config.setting("OCTAVE_GUI")
    if configured and os.path.isfile(configured):
        return configured
    folder = os.path.dirname(cli)
    names = ["octave.exe", "octave-gui.exe"] if IS_WINDOWS else ["octave"]
    for name in names:
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            return path
    return shutil.which("octave")


_cached: Octave | None = None


def find_octave(refresh: bool = False) -> Octave:
    global _cached
    if _cached is not None and not refresh:
        return _cached
    cli = next((c for c in _cli_candidates() if c and os.path.isfile(c)), None)
    if cli is None:
        _cached = Octave(None, None)
        return _cached
    version = None
    try:
        out = subprocess.run([cli, "--norc", "--quiet", "--no-gui", "--eval", "disp(OCTAVE_VERSION)"],
                             capture_output=True, text=True, timeout=60, **_popen_flags())
        version = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else None
    except (OSError, subprocess.TimeoutExpired):
        pass
    _cached = Octave(cli, _gui_for(cli), version)
    return _cached


def _popen_flags() -> dict:
    if IS_WINDOWS:
        return {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=10)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def uses_graphics(*codes: str | None) -> bool:
    for code in codes:
        if not code:
            continue
        stripped = re.sub(r"%.*", "", code)
        stripped = re.sub(r"'[^'\n]*'", "''", stripped)
        if any(w in PLOT_WORDS for w in re.findall(r"[A-Za-z_]\w*", stripped)):
            return True
    return False


@dataclass
class RawRun:
    result: dict | None
    progress: list[dict]
    stdout: str
    stderr: str
    timed_out: bool
    seconds: float
    figures: list[Path]
    workdir: Path


def _clean(text: str, workdir: Path) -> str:
    for w in {str(workdir), os.path.realpath(workdir), str(workdir).replace("\\", "/"),
              os.path.realpath(workdir).replace("\\", "/")}:
        text = text.replace(w + os.sep, "").replace(w + "/", "").replace(w, "")
    if len(text) > MAX_OUTPUT:
        text = text[:MAX_OUTPUT] + "\n... (output cut off)"
    return text


def _matlab_str(path: Path | str) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def _execute(problem: Problem, files: dict[str, str], mode: str, timeout: float, graphics: bool,
             tests_file: Path | None = None, extra_files: dict[str, str] | None = None) -> RawRun:
    octave = find_octave()
    if not octave.found:
        raise RuntimeError("Octave wasn't found. Install it (see INSTALL.md) or set OCTAVE in .env.")
    workdir = Path(tempfile.mkdtemp(prefix="mp-"))
    real = Path(os.path.realpath(workdir))
    figdir = real / "figs"
    figdir.mkdir()
    # MATLAB puts a script's local functions at the end; Octave can't run that, so move them out.
    scripts = {"scratch.m"} | ({problem.file} if problem.kind != "function" else set())
    files, origin = octave_compat.prepare_files(files, scripts)
    # Functions from linked "previous problems" (the student's own files); local ones win.
    for name, text in (extra_files or {}).items():
        files.setdefault(name, text)
    for name, text in files.items():
        (real / name).write_text(text, encoding="utf-8", newline="\n")
    if tests_file is not None:
        shutil.copyfile(tests_file, real / "tests.m")
    cfg = {
        "mode": mode, "kind": problem.kind, "func": problem.func_name,
        "inputs": problem.function.get("inputs", []) if problem.kind == "function" else [],
        "outputs": problem.function.get("outputs", []) if problem.kind == "function" else [],
        "script": problem.script_name if mode == "run" else Path(problem.file).stem,
        "workdir": real.as_posix(), "figdir": figdir.as_posix(),
        "out": (real / "mp_result.json").as_posix(), "progress": (real / "mp_progress.jsonl").as_posix(),
    }
    (real / "mp_config.json").write_text(json.dumps(cfg), encoding="utf-8")
    exe = octave.gui if (graphics and octave.gui) else octave.cli
    env = os.environ.copy()
    qpa = config.setting("QT_QPA_PLATFORM")
    if qpa:
        env["QT_QPA_PLATFORM"] = qpa
    elif graphics and sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        # No screen at all (Linux servers). Qt's offscreen mode can't render plots on macOS or
        # Windows ("invalid empty image"), so there the normal platform is used, with hidden figures.
        env["QT_QPA_PLATFORM"] = "offscreen"
    eval_cmd = f"addpath('{_matlab_str(config.MATLAB_DIR)}'); mp_run('mp_config.json');"
    args = [exe, "--no-gui", "--norc", "--quiet", "--no-history", "--eval", eval_cmd]
    start = time.monotonic()
    timed_out = False
    proc = subprocess.Popen(args, cwd=real, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                            env=env, **_popen_flags())
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            out, err = b"", b""
    seconds = time.monotonic() - start
    stdout = _clean(out.decode("utf-8", "replace"), real)
    stderr = _clean(err.decode("utf-8", "replace"), real)
    result = None
    result_file = real / "mp_result.json"
    if result_file.is_file():
        try:
            result = json.loads(result_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            result = None
    progress = []
    prog_file = real / "mp_progress.jsonl"
    if prog_file.is_file():
        for line in prog_file.read_text(encoding="utf-8").splitlines():
            try:
                progress.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    figures = sorted(figdir.glob("*.png"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0)
    if origin:
        result, progress = _point_back(result, origin), [_point_back(c, origin) for c in progress]
    return RawRun(result, progress, stdout, _filter_stderr(stderr), timed_out, seconds, figures, real)


def _point_back(obj, origin: dict[str, str]):
    """Errors in a moved-out local function name its generated file: name the student's script instead."""
    if isinstance(obj, str):
        for generated, script in origin.items():
            obj = obj.replace(f"Error in {generated} line", f"Error in {script} line")
        return obj
    if isinstance(obj, dict):
        return {k: _point_back(v, origin) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_point_back(v, origin) for v in obj]
    return obj


_NOISE = re.compile(r"^(FALLBACK \(log once\)|QStandardPaths|qt\.|libpng warning|warning: using the fltk)")


def _filter_stderr(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not _NOISE.match(l.strip())).strip()


def _case_out(c: dict) -> dict:
    return {
        "name": c.get("name", ""), "status": c.get("status", "error"),
        "message": matlab_message(c.get("message") or ""),
        "input": c.get("input") or None, "expected": c.get("expected") or None,
        "actual": c.get("actual") or None, "hidden": bool(c.get("hidden")),
    }


def run_tests(problem: Problem, code: str, tests_file: Path | None = None,
              extra_files: dict[str, str] | None = None) -> dict:
    """Grade `code` with the problem's tests.m. Returns the tests part of a submission."""
    tests_file = tests_file or problem.dir / "tests.m"
    graphics = problem.kind == "plot" or uses_graphics(code)
    raw = _execute(problem, {problem.file: code}, "test", problem.timeout_s, graphics, tests_file, extra_files)
    cases = [_case_out(c) for c in (raw.result or {}).get("cases", [])] if raw.result else [
        _case_out(c) for c in raw.progress]
    error = None
    if raw.timed_out:
        verdict = "timeout"
        done = len(cases)
        error = (f"Stopped after {problem.timeout_s} s: your code took too long "
                 f"(maybe an infinite loop) after {done} test case{'s' if done != 1 else ''} finished.")
    elif raw.result is None:
        verdict = "error"
        error = matlab_message(raw.stderr.strip() or "Octave stopped without a result.")
    elif raw.result.get("status") == "error":
        verdict = "error"
        error = matlab_message(raw.result.get("error") or "Unknown error")
    elif not cases:
        verdict = "accepted"  # self-checked plot problem
    elif any(c["status"] == "error" for c in cases):
        verdict = "error" if all(c["status"] != "passed" for c in cases) else "wrong"
    elif all(c["status"] == "passed" for c in cases):
        verdict = "accepted"
    else:
        verdict = "wrong"
    fig_problem = (raw.result or {}).get("figure_error") or ""
    return {
        "tests_verdict": verdict, "cases": cases, "error": error,
        "passed": sum(c["status"] == "passed" for c in cases), "total": len(cases),
        "stdout": raw.stdout, "stderr": raw.stderr if verdict == "error" and raw.result is None else "",
        "figures_paths": raw.figures, "figure_error": fig_problem, "seconds": round(raw.seconds, 2),
        "workdir": raw.workdir,
    }


def run_code(problem: Problem, code: str, scratch: str | None, extra_files: dict[str, str] | None = None) -> dict:
    """The Run button: execute scratch.m (function problems) or the solution script."""
    files = {problem.file: code}
    if problem.kind == "function":
        files["scratch.m"] = scratch or ""
    graphics = uses_graphics(code, scratch)
    raw = _execute(problem, files, "run", RUN_TIMEOUT_S, graphics, None, extra_files)
    error = None
    if raw.timed_out:
        error = f"Stopped after {RUN_TIMEOUT_S} s: your code took too long (maybe an infinite loop)."
    elif raw.result is None:
        error = matlab_message(raw.stderr.strip() or "Octave stopped without a result.")
    elif raw.result.get("status") == "error":
        error = matlab_message(raw.result.get("error") or "Unknown error")
    return {
        "stdout": raw.stdout, "stderr": raw.stderr if raw.result is None else "", "error": error,
        "timed_out": raw.timed_out, "seconds": round(raw.seconds, 2), "figures_paths": raw.figures,
        "figure_error": (raw.result or {}).get("figure_error") or "", "workdir": raw.workdir,
    }


def cleanup(workdir: Path) -> None:
    shutil.rmtree(workdir, ignore_errors=True)
