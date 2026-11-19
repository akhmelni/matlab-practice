"""MATLAB-compatibility checker.

Blocks code that GNU Octave accepts but MATLAB would reject (or run differently), unsafe calls,
and functions or operators a problem bans. See README.md in this folder.

    from matlab_practice.checker import check, Issue
    issues = check(code, profile="student", banned_functions=["interp1"])
"""

from .issue import Issue
from .rules import PROFILES, check

__all__ = ["Issue", "check", "PROFILES"]
