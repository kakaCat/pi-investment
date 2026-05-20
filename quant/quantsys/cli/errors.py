"""Typed errors for stable CLI responses."""

from __future__ import annotations


class CliError(Exception):
    """Base CLI error with a machine-readable code and exit status."""

    def __init__(self, code: str, message: str, exit_code: int = 1, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.hint = hint


class UnknownCommandError(CliError):
    """Raised when no command is registered for a domain/action pair."""

    def __init__(self, command: str) -> None:
        super().__init__(
            "UNKNOWN_COMMAND",
            f"Unknown command: {command}",
            exit_code=2,
            hint="Run `quant tools +list --json` to discover available commands.",
        )

