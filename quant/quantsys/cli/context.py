"""Runtime context for QuantSys CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CliContext:
    """Resolved paths shared by command handlers."""

    quant_root: Path
    project_root: Path
    db_path: Path
    output_dir: Path
    python: str


def build_context(
    db_path: str | None = None,
    output_dir: str | None = None,
    python: str | None = None,
) -> CliContext:
    """Resolve project paths from the installed package location."""
    quant_root = Path(__file__).resolve().parents[2]
    project_root = quant_root.parent
    resolved_db_path = Path(db_path) if db_path else project_root / ".pi-invest" / "stock-db" / "stocks.db"
    resolved_output_dir = Path(output_dir) if output_dir else project_root / ".pi-invest"

    return CliContext(
        quant_root=quant_root,
        project_root=project_root,
        db_path=resolved_db_path.expanduser(),
        output_dir=resolved_output_dir.expanduser(),
        python=python or "python",
    )

