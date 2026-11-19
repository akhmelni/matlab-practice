"""The Issue record returned by the checker."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Issue:
    """One problem found in the code.

    Lines and columns are 1-based; ``end_col`` is exclusive.
    """

    line: int
    col: int
    end_line: int
    end_col: int
    rule: str
    severity: str  # "error" or "warning"
    message: str

    def to_dict(self) -> dict:
        return {
            "line": self.line,
            "col": self.col,
            "end_line": self.end_line,
            "end_col": self.end_col,
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
        }
