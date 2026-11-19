"""Translate Octave's error wording into what MATLAB would say, so the student
learns MATLAB's messages. Unknown messages pass through unchanged."""

import re

_PREFIX = re.compile(r"^(Error in [^:]+ line \d+: )")

_RULES: list[tuple[re.Pattern, object]] = [
    # x(5): out of bound 3 (dimensions are 1x3)   /  A(3,_): out of bound 2 ...
    (re.compile(r"^(?:index |[\w.]+)\(([^)]*)\): out of bound (\d+)"), "bounds"),
    (re.compile(r"^(?:index |[\w.]+)?\([^)]*\): subscripts must be either integers 1 to"),
     "Array indices must be positive integers or logical values."),
    (re.compile(r"^'(\w+)' undefined"), lambda m: f"Unrecognized function or variable '{m.group(1)}'."),
    (re.compile(r"^operator \*: nonconformant arguments"),
     "Incorrect dimensions for matrix multiplication. Check that the number of columns in the first "
     "matrix matches the number of rows in the second matrix. To operate on each element of the "
     "matrix individually, use TIMES (.*) for elementwise multiplication."),
    (re.compile(r"^operator [\\/]: nonconformant arguments"), "Matrix dimensions must agree."),
    (re.compile(r"^operator \S+: nonconformant arguments"), "Arrays have incompatible sizes for this operation."),
    (re.compile(r"^(?:vertical|horizontal) dimensions mismatch"),
     "Dimensions of arrays being concatenated are not consistent."),
    (re.compile(r"^Invalid call to (\w+)"), lambda m: f"Wrong number of input arguments for {m.group(1)}."),
    (re.compile(r"called with too many inputs"), "Too many input arguments."),
    (re.compile(r"called with too many outputs"), "Too many output arguments."),
    (re.compile(r"^element number \d+ undefined in return list"),
     "An output argument was not assigned a value (or too many outputs were requested)."),
    (re.compile(r"^value on right hand side of assignment"), "An output argument was not assigned a value."),
    (re.compile(r"structure has no member '(\w+)'"), lambda m: f'Unrecognized field name "{m.group(1)}".'),
    (re.compile(r"^binary operator '(\S+)' not implemented for '(\w+)' by '(\w+)' operations"),
     lambda m: f"Operator '{m.group(1)}' is not supported for operands of type '{m.group(2)}'."),
    (re.compile(r"^(\w+) cannot be indexed with \{"), "Brace indexing is not supported for variables of this type."),
    (re.compile(r"^(?:parse|syntax) error.*?near line (\d+)(?:, column \d+)?(?: in file .*?([\w-]+\.m))?",
                re.S), "syntax"),
]


def _bounds(m: re.Match) -> str:
    subs, limit = m.group(1), m.group(2)
    parts = [p.strip() for p in subs.split(",")]
    if len(parts) > 1:
        pos = next((i + 1 for i, p in enumerate(parts) if p != "_"), 1)
        return f"Index in position {pos} exceeds array bounds. Index must not exceed {limit}."
    return f"Index exceeds the number of array elements. Index must not exceed {limit}."


def matlab_message(message: str) -> str:
    if not message:
        return message
    prefix = ""
    m = _PREFIX.match(message)
    if m:
        prefix, message = m.group(1), message[m.end():]
    for pattern, replacement in _RULES:
        hit = pattern.search(message)
        if not hit:
            continue
        if replacement == "bounds":
            text = _bounds(hit)
        elif replacement == "syntax":
            file = f" in {hit.group(2)}" if hit.group(2) else ""
            text = f"Invalid syntax{file} near line {hit.group(1)}. Check for a missing operator, bracket or `end`."
        elif callable(replacement):
            text = replacement(hit)
        else:
            text = replacement
        return prefix + text
    return prefix + message
