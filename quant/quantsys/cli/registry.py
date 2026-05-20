"""Command registry for QuantSys CLI discovery and dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .context import CliContext


CommandHandler = Callable[[CliContext, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class CommandSpec:
    """A command exposed through the agent-friendly CLI."""

    name: str
    domain: str
    action: str
    description: str
    params: dict[str, dict[str, Any]]
    examples: list[str]
    handler: CommandHandler


class CommandRegistry:
    """In-memory command registry."""

    def __init__(self) -> None:
        self._commands: dict[str, CommandSpec] = {}

    def register(self, spec: CommandSpec) -> None:
        self._commands[spec.name] = spec

    def get(self, name: str) -> CommandSpec | None:
        return self._commands.get(name)

    def list(self) -> list[CommandSpec]:
        return sorted(self._commands.values(), key=lambda spec: spec.name)

