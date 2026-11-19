"""Name tables used by the rules: MATLAB function list, Octave-only names, unsafe and unsupported calls."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

# ---------------------------------------------------------------------------------------------
# Octave-only functions and constants. Value: what to write in MATLAB (shown to the student).
# A value that starts with "!" is a full sentence; otherwise it's shown as "In MATLAB, use `...`."
OCTAVE_FUNCTIONS: dict[str, str] = {
    "printf": "fprintf(...)",
    "puts": "fprintf('%s', text)",
    "fputs": "fprintf('%s', text)",
    "fdisp": "disp(x)",
    "fflush": "!MATLAB doesn't need it. Delete this line.",
    "stdout": "!In MATLAB, leave it out: `fprintf('...')` prints to the screen.",
    "stderr": "!In MATLAB, leave it out and use `fprintf('...')`.",
    "columns": "size(x, 2)",
    "rows": "size(x, 1)",
    "postpad": "!In MATLAB, add the zeros yourself, e.g. `[x, zeros(1, n)]`.",
    "prepad": "!In MATLAB, add the zeros yourself, e.g. `[zeros(1, n), x]`.",
    "isargout": "!In MATLAB, check `nargout` instead.",
    "nthargout": "!In MATLAB, ask for the outputs directly: `[~, b] = f(x)`.",
    "e": "exp(1)",
    "NA": "NaN",
    "I": "1i",
    "J": "1i",
    "sumsq": "sum(x.^2)",
    "cbrt": "nthroot(x, 3)",
    "lgamma": "gammaln(x)",
    "toupper": "upper(s)",
    "tolower": "lower(s)",
    "isalpha": "isletter(s)",
    "isdigit": "isstrprop(s, 'digit')",
    "isupper": "isstrprop(s, 'upper')",
    "islower": "isstrprop(s, 'lower')",
    "isalnum": "isstrprop(s, 'alphanum')",
    "ispunct": "isstrprop(s, 'punct')",
    "index": "strfind(s, t)",
    "rindex": "strfind(s, t)",
    "substr": "s(first:last)",
    "ostrsplit": "strsplit(s, delimiter)",
    "cstrcat": "[a, b]",
    "is_function_handle": "isa(f, 'function_handle')",
    "print_usage": "error('your message')",
    "ifelse": "!In MATLAB, use an `if` statement or logical indexing.",
    "size_equal": "isequal(size(a), size(b))",
    "vec": "x(:)",
    "range": "max(x) - min(x)",
    "nanmax": "max(x, [], 'omitnan')",
    "nanmin": "min(x, [], 'omitnan')",
    "nansum": "sum(x, 'omitnan')",
    "nanmean": "mean(x, 'omitnan')",
    "quadcc": "integral(f, a, b)",
    "lsode": "ode45(...)",
    "usleep": "!MATLAB doesn't have it, and waiting isn't needed here. Delete it.",
    "sleep": "!MATLAB doesn't have it, and waiting isn't needed here. Delete it.",
    "kbhit": "!Reading the keyboard isn't allowed in practice problems.",
    "putenv": "!MATLAB doesn't have it.",
    "pkg": "!MATLAB doesn't need `pkg`. Delete this line.",
    "page_screen_output": "!Delete this line.",
    "page_output_immediately": "!Delete this line.",
    "OCTAVE_VERSION": "!Delete it.",
    "OCTAVE_HOME": "!Delete it.",
    "argv": "!Delete it.",
    "program_name": "!Delete it.",
    "issquare": "size(A, 1) == size(A, 2)",
    "numfields": "numel(fieldnames(s))",
    "finite": "isfinite(x)",
    "polyout": "!Print the polynomial yourself with `fprintf`.",
    "common_size": "!Check sizes yourself with `size`.",
    "fskipl": "!Reading files isn't allowed in practice problems.",
}


def octave_function_message(name: str) -> str:
    fix = OCTAVE_FUNCTIONS[name]
    head = f"`{name}` only exists in Octave, not MATLAB."
    if name in ("e", "NA", "I", "J"):
        head = f"`{name}` is a constant only in Octave."
    if fix.startswith("!"):
        return f"{head} {fix[1:]}"
    return f"{head} In MATLAB, use `{fix}`."


# Octave-only block keywords. Value: what MATLAB writes instead.
OCTAVE_END_KEYWORDS: dict[str, str] = {
    "endif": "end",
    "endfor": "end",
    "endwhile": "end",
    "endfunction": "end",
    "endswitch": "end",
    "end_try_catch": "end",
    "endparfor": "end",
    "end_unwind_protect": "end",
}

# ---------------------------------------------------------------------------------------------
# Unsafe calls (student profile only).
_FILES = "Reading or writing files isn't allowed in practice problems."
_SHELL = "Running computer commands isn't allowed in practice problems."
_EVAL = "Running code from text isn't allowed in practice problems. Write the code directly."
_WAIT = "would wait forever for typing. Put the value in a variable instead."
_WEB = "Using the internet isn't allowed in practice problems."
_PATH = "Changing folders, the path or settings isn't allowed in practice problems."
_LANG = "Calling other programs or languages isn't allowed in practice problems."

UNSAFE: dict[str, str] = {}
for _n in (
    "fopen fclose fread fwrite fgetl fgets fscanf fileread load save importdata csvread csvwrite "
    "dlmread dlmwrite readmatrix writematrix readtable writetable xlsread xlswrite readcell writecell "
    "readlines writelines readstruct writestruct readvars textread diary matfile imread imwrite "
    "audioread audiowrite xmlread xmlwrite type edit open saveas savefig exportgraphics hgsave "
    "dir ls delete rmdir mkdir movefile copyfile zip unzip tar untar gzip gunzip"
).split():
    UNSAFE[_n] = _FILES
for _n in "system unix dos winopen popen popen2 pclose exec fork shell_cmd".split():
    UNSAFE[_n] = _SHELL
for _n in "eval evalin evalc assignin builtin run source timer".split():
    UNSAFE[_n] = _EVAL
UNSAFE["feval"] = "Calling functions by name isn't allowed here. Call the function directly, e.g. `f(x)`."
UNSAFE["str2func"] = "Making functions from text isn't allowed here. Use `@`, e.g. `f = @(x) x.^2`."
for _n in "input keyboard inputdlg questdlg listdlg ginput waitforbuttonpress uiwait".split():
    UNSAFE[_n] = f"`{_n}` {_WAIT}"
UNSAFE["pause"] = "`pause` would just make the grader wait. Delete it."
UNSAFE["exit"] = "`exit` would stop the grader. Delete it."
UNSAFE["quit"] = "`quit` would stop the grader. Delete it."
for _n in "web webread webwrite urlread urlwrite websave ftp sftp sendmail tcpclient".split():
    UNSAFE[_n] = _WEB
for _n in "cd addpath rmpath path genpath setenv savepath userpath restoredefaultpath".split():
    UNSAFE[_n] = _PATH
for _n in (
    "javaObject javaMethod javaArray java perl python pyrun pyrunfile pyenv loadlibrary calllib "
    "mex actxserver"
).split():
    UNSAFE[_n] = _LANG
UNSAFE["print"] = (
    "`print` saves or prints figures, which isn't allowed here. To show a value, use `disp(x)` or `fprintf`."
)
SHELL_ESCAPE_MESSAGE = "`!` runs a computer command, which isn't allowed in practice problems."


def unsafe_message(name: str) -> str:
    msg = UNSAFE[name]
    if msg.startswith("`"):
        return msg
    return f"`{name}`: {msg[0].lower()}{msg[1:]}"


# ---------------------------------------------------------------------------------------------
# MATLAB features that Octave can't run (or runs differently).
UNSUPPORTED_NAMES: dict[str, str] = {
    "table": "`table` isn't supported here (Octave doesn't have it). Use a matrix or a struct instead.",
    "timetable": "`timetable` isn't supported here (Octave doesn't have it). Use a matrix instead.",
    "datetime": "`datetime` isn't supported here (Octave doesn't have it). Use numbers instead.",
    "duration": "`duration` isn't supported here (Octave doesn't have it). Use numbers instead.",
    "categorical": "`categorical` isn't supported here (Octave doesn't have it). Use a cell array instead.",
    "dictionary": "`dictionary` isn't supported here (Octave doesn't have it). Use `containers.Map` instead.",
    "string": "`string` isn't supported here. Use char arrays in single quotes, like 'text'.",
    "strings": "`strings` isn't supported here. Use char arrays in single quotes, like 'text'.",
}
DQ_MESSAGE = (
    "Use single quotes: 'text'. In MATLAB, double quotes make a different kind of text."
)


# ---------------------------------------------------------------------------------------------
# The MATLAB function list.
@lru_cache(maxsize=1)
def matlab_names() -> tuple[frozenset[str], dict[str, frozenset[str]]]:
    """Return (plain names, {root: dotted names}) from ``matlab_functions.txt``."""
    text = resources.files(__package__).joinpath("matlab_functions.txt").read_text(encoding="utf-8")
    plain: set[str] = set()
    dotted: dict[str, set[str]] = {}
    for raw in text.splitlines():
        name = raw.split("%", 1)[0].split("#", 1)[0].strip()
        if not name:
            continue
        if "." in name:
            dotted.setdefault(name.split(".", 1)[0], set()).add(name)
        else:
            plain.add(name)
    return frozenset(plain), {k: frozenset(v) for k, v in dotted.items()}
