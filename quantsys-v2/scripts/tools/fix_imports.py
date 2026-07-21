#!/usr/bin/env python3
"""Fix imports in all generated blueprints."""
import re, sys
from pathlib import Path

ROUTES = Path(__file__).resolve().parents[1] / "api" / "routes"

PROPER_HEADER = '''"""
{name} routes.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid

from flask import Blueprint, jsonify, request

from adapters.inbound.api.shared import (
    ds,
    api_response,
    handle_api_error,
    sanitize_for_json,
    convert_keys_to_snake,
    convert_keys_to_camel,
    _safe_float,
    _V2_ROOT,
    _PROJECT_ROOT_PATH,
    _LEGACY_QUANT_ROOT,
    _load_pipeline_runs,
    _save_pipeline_runs,
    _get_pipeline_run,
    _update_pipeline_run,
    acquire_task,
    release_task,
    get_running_tasks_snapshot,
    strategy_service,
    stock_pool_service,
    factor_adapter,
    scoring_service,
    _read_watchlist,
    _write_watchlist,
    _read_groups,
    _write_groups,
    _parse_sina_a_quote,
    _parse_sina_hk_quote,
    to_camel_case,
    to_snake_case,
    get_query_params_snake_case,
    enrich_stock_data,
    signal_to_opportunity,
)

{name}_bp = Blueprint('{name}', __name__)

'''


def fix_file(fp: Path):
    content = fp.read_text()
    name = fp.stem

    # Find the blueprint definition
    bp_match = re.search(rf'{name}_bp = Blueprint\(.*?\n\n', content)
    if not bp_match:
        print(f"  ⚠️  {name}: no blueprint def found")
        return

    # Extract everything after "bp = Blueprint(...)\n\n"
    after_bp = content[bp_match.end():]

    # Remove all garbled import lines (stray lines like "import timedelta", "import pathlib.Path", etc.)
    clean_lines = []
    for line in after_bp.split("\n"):
        stripped = line.strip()
        # Skip garbled import-like lines
        if stripped.startswith("import ") and "." in stripped.split()[1] if len(stripped.split()) > 1 else False:
            if any(garb in stripped for garb in ["timedelta", "pathlib", "datetime.datetime", "json.json"]):
                continue
        if stripped in ("import timedelta", "import pathlib.Path", "import datetime.datetime",
                        "import shutil", "import uuid as uuid", "import glob as _glob", "import json as _json"):
            continue
        if stripped == "import sys" and line == after_bp.split("\n")[0]:
            continue  # duplicate at first line
        clean_lines.append(line)

    # Remove leading blank lines
    while clean_lines and clean_lines[0].strip() == "":
        clean_lines.pop(0)

    body = "\n".join(clean_lines)

    # Replace stray @bp-name_bp with @{name}_bp
    body = re.sub(r'@\w+_bp\.', f'@{name}_bp.', body)

    # Assemble
    result = PROPER_HEADER.format(name=name) + body
    # Clean trailing blanks
    result = re.sub(r'\n{4,}', '\n\n\n', result)
    fp.write_text(result)
    print(f"  ✅ {name}.py")


def main():
    for fp in sorted(ROUTES.glob("*.py")):
        if fp.stem == "__init__":
            continue
        fix_file(fp)

    print("\nDone. Run syntax check to verify.")


if __name__ == "__main__":
    main()
