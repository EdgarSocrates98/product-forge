"""Structured errors — stable codes, never leak internals."""

from __future__ import annotations

from typing import Any


class ForgeError(Exception):
    """Base error carrying a stable machine code for the API envelope."""

    code = "FORGE-ERROR"
    http_status = 500
    severity = "error"
    retryable = False

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}

    def body(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "code": self.code,
            "message": str(self),
            "severity": self.severity,
            "retryable": self.retryable,
        }
        if self.details:
            body["details"] = self.details
        return body


class NotFoundError(ForgeError):
    code = "PORTAL-NOT-FOUND"
    http_status = 404


class ValidationError(ForgeError):
    code = "PF-VALIDATION"
    http_status = 422
    severity = "warning"


class PermissionDeniedError(ForgeError):
    code = "PF-PERMISSION-DENIED"
    http_status = 403


class ConflictError(ForgeError):
    code = "PF-CONFLICT"
    http_status = 409
    retryable = True


class SourceUnavailableError(ForgeError):
    code = "PF-SOURCE-UNAVAILABLE"
    http_status = 503
    retryable = True


class UnsafeOperationError(ForgeError):
    code = "PF-UNSAFE-OPERATION"
    http_status = 400


class BudgetExceededError(ForgeError):
    code = "PF-BUDGET-EXCEEDED"
    http_status = 429
    retryable = True
