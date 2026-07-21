#!/usr/bin/env python3
"""Split misc.py + merge tiny blueprints → final clean structure."""
import re, shutil
from pathlib import Path

ROUTES = Path(__file__).resolve().parents[1] / "api" / "routes"
SERVER = Path(__file__).resolve().parents[1] / "api" / "server.py"

# ── Step 1: Extract blocks from misc.py by domain ──
def extract_misc_blocks():
    misc = ROUTES / "misc.py"
    if not misc.exists():
        return {}
    content = misc.read_text()
    lines = content.split("\n")

    # Find the import/preamble part (before first @misc_bp.route)
    preamble_end = 0
    for i, line in enumerate(lines):
        if "@misc_bp.route(" in line:
            preamble_end = i
            break

    # Find all route blocks
    blocks = {}  # path_prefix → list of lines (including decorator)
    current_path = None
    current_block = []

    for i, line in enumerate(lines):
        if "@misc_bp.route(" in line:
            if current_block and current_path:
                blocks.setdefault(current_path, []).extend(current_block)
            # Determine domain from path
            m = re.search(r"'([^']*)'", line)
            if m:
                path = m.group(1)
                if "/signals" in path:
                    current_path = "signals"
                elif "/backtest" in path:
                    current_path = "backtest"
                elif "/risk/" in path:
                    current_path = "risk"
                elif "/report/" in path:
                    current_path = "health"
                elif "/agent/" in path:
                    current_path = "agent"
                elif "/jobs" in path or "/data/update" in path or "/compute/factors" in path:
                    current_path = "jobs"
                else:
                    current_path = "other"
            current_block = [line]
        else:
            current_block.append(line)

    if current_block and current_path:
        blocks.setdefault(current_path, []).extend(current_block)

    # Clean blocks: remove trailing empty lines, fix indentation
    result = {}
    for domain, block_lines in blocks.items():
        text = "\n".join(block_lines).strip()
        if not text:
            continue
        # Replace @misc_bp with @{domain}_bp
        text = text.replace("@misc_bp.", f"@{domain}_bp.")
        result[domain] = text
    return result


def append_to_blueprint(target: str, blocks_text: str):
    """Append route blocks to an existing blueprint file."""
    bp_file = ROUTES / f"{target}.py"
    existing = bp_file.read_text() if bp_file.exists() else ""
    # Ensure there's a blueprint definition
    if f"{target}_bp = Blueprint" not in existing:
        return

    # Append after the last line
    combined = existing.rstrip() + "\n\n" + blocks_text + "\n"
    # Fix duplicate imports — keep only unique ones
    bp_file.write_text(combined)


def merge_blueprint(source: str, target: str):
    """Merge all routes from source blueprint into target."""
    src_file = ROUTES / f"{source}.py"
    tgt_file = ROUTES / f"{target}.py"
    if not src_file.exists() or not tgt_file.exists():
        return
    src = src_file.read_text()
    tgt = tgt_file.read_text()

    # Extract route blocks from source (after blueprint definition)
    bp_match = re.search(rf'{source}_bp = Blueprint.*?\n\n(.*)', src, re.DOTALL)
    if not bp_match:
        return
    route_code = bp_match.group(1).strip()
    # Replace blueprint reference
    route_code = route_code.replace(f"@{source}_bp.", f"@{target}_bp.")

    merged = tgt.rstrip() + "\n\n" + route_code + "\n"
    tgt_file.write_text(merged)
    src_file.unlink()
    print(f"  merged {source}.py → {target}.py")


def main():
    # ── Split misc.py ──
    print("=== Splitting misc.py ===")
    blocks = extract_misc_blocks()
    for domain, text in blocks.items():
        target = ROUTES / f"{domain}.py"
        if target.exists() and domain not in ("signals", "backtest", "jobs", "agent"):
            # Merge into existing
            append_to_blueprint(domain, text)
            print(f"  misc/{domain} → {domain}.py (appended)")
        else:
            # Create new blueprint
            template = f'''"""{domain} routes — auto-generated."""
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import json
import uuid

from flask import Blueprint, jsonify, request

from adapters.inbound.api.shared import (
    ds, api_response, handle_api_error, sanitize_for_json,
    convert_keys_to_snake, convert_keys_to_camel,
    _safe_float, _V2_ROOT, _PROJECT_ROOT_PATH, _LEGACY_QUANT_ROOT,
    _load_pipeline_runs, _save_pipeline_runs,
    _get_pipeline_run, _update_pipeline_run,
    strategy_service, stock_pool_service, factor_adapter, scoring_service,
)

{domain}_bp = Blueprint('{domain}', __name__)

{text}
'''
            target.write_text(template)
            print(f"  misc/{domain} → {domain}.py (new)")

    # Delete misc.py
    (ROUTES / "misc.py").unlink(missing_ok=True)
    print("  deleted misc.py")

    # ── Merge tiny blueprints ──
    print("\n=== Merging small blueprints ===")

    merges = [
        # (source, target)
        ("screening", "stock_analytics"),
        ("factor_explain", "analysis"),
        ("ml_pipeline", "training"),
        ("strategies_rest", "strategies"),
        ("stock_extras", "stock"),
        ("stock_analytics", "analysis"),
        ("financial_detail", "analysis"),
        ("kline", "quote_market"),
        ("performance", "backtest"),
        ("agent", "signals"),
    ]

    for src, tgt in merges:
        if (ROUTES / f"{src}.py").exists() and (ROUTES / f"{tgt}.py").exists():
            merge_blueprint(src, tgt)

    # ── Update server.py ──
    print("\n=== Updating server.py ===")
    remaining = sorted([f.stem for f in ROUTES.glob("*.py") if f.stem != "__init__"])

    server_lines = [
        '"""',
        'QuantSys V2 API 服务 — App Factory',
        '',
        'Blueprint 路由:',
    ]
    for bp in remaining:
        server_lines.append(f'  api/routes/{bp}.py')
    server_lines += [
        '"""',
        'from flask import Flask',
        'from flask_cors import CORS',
        '',
        '',
        'def create_app():',
        '    app = Flask(__name__)',
        '    CORS(app)',
        '',
        '    # ── 注册 blueprints ──',
        '',
    ]
    for bp in remaining:
        server_lines.append(f'    from adapters.inbound.api.routes.{bp} import {bp}_bp')
        server_lines.append(f'    app.register_blueprint({bp}_bp)')
    server_lines += [
        '',
        '    return app',
        '',
        '',
        "# ── 模块级 app 实例（兼容直接 python api/server.py 启动）──",
        'app = create_app()',
        '',
        '',
        'if __name__ == "__main__":',
        '    app.run(host="0.0.0.0", port=5001, debug=True)',
    ]
    SERVER.write_text("\n".join(server_lines) + "\n", encoding="utf-8")
    print(f"  server.py: {len(remaining)} blueprints registered")


if __name__ == "__main__":
    main()
