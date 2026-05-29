"""Environment loading tests for backfill_klines.py."""

import importlib.util
import os
from pathlib import Path


def test_backfill_script_reads_repo_root_env_without_overriding_existing(tmp_path, monkeypatch):
    """Backfill script should pick up PostgreSQL settings from the repo .env."""
    source_script = Path(__file__).parents[1] / "scripts" / "backfill_klines.py"
    script_path = tmp_path / "repo" / "quant" / "scripts" / "backfill_klines.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text(source_script.read_text())
    script_path.parents[2].joinpath(".env").write_text(
        "QUANT_DB_PROVIDER=postgres\nPGDATABASE=quant_investment\nPGUSER=from_env\n"
    )

    monkeypatch.delenv("QUANT_DB_PROVIDER", raising=False)
    monkeypatch.delenv("PGDATABASE", raising=False)
    monkeypatch.setenv("PGUSER", "explicit_user")

    spec = importlib.util.spec_from_file_location("backfill_klines_env_test", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert os.environ["QUANT_DB_PROVIDER"] == "postgres"
    assert os.environ["PGDATABASE"] == "quant_investment"
    assert os.environ["PGUSER"] == "explicit_user"
