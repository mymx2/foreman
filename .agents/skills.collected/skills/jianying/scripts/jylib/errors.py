"""Errors carry a machine-readable code plus a human fix, so the CLI can keep
stdout valid JSON while still telling the agent what to do next."""

from __future__ import annotations


class SkillError(Exception):
    def __init__(self, message, *, code="FAILED", details=None, fix=None, retriable=False):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.fix = fix
        self.retriable = retriable

    def to_dict(self):
        out = {"code": self.code, "message": self.message, "retriable": self.retriable}
        if self.details:
            out["details"] = self.details
        if self.fix:
            out["fix"] = self.fix
        return out
