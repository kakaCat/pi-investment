import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "infrastructure" / "persistence" / "migrations" / "20261102_t_trade_cycles.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("mig_t_trade", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_is_idempotent_and_dry_run_by_default(capsys):
    module = load_migration()
    assert module.build_parser().parse_args([]).apply is False
    assert "CREATE TABLE IF NOT EXISTS" in module.TABLE_DDL
    assert all("IF NOT EXISTS" in ddl for ddl in module.INDEXES)
    assert module.main([]) == 0
    assert "DRY-RUN done" in capsys.readouterr().out


def test_migration_enforces_one_active_cycle_and_real_fill_identity():
    module = load_migration()
    ddl = module.TABLE_DDL
    assert "sell_trade_id integer UNIQUE REFERENCES" in ddl
    assert "buyback_trade_id integer UNIQUE REFERENCES" in ddl
    assert any("CREATE UNIQUE INDEX" in item and "waiting_buyback" in item for item in module.INDEXES)
