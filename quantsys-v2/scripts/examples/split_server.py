#!/usr/bin/env python3
"""
将 server.py 拆分为 domain blueprint 文件。

生成:
  api/routes/{domain}.py — 每个 domain 一个 blueprint
  api/server.py          — 重写为 app factory

用法: python scripts/split_server.py
"""

import re, os, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "api" / "server.py"
ROUTES_DIR = ROOT / "api" / "routes"
SHARED_IMPORTS = [
    "ds",
    "api_response", "handle_api_error",
    "sanitize_for_json",
    "convert_keys_to_snake", "convert_keys_to_camel",
    "to_camel_case", "to_snake_case",
    "get_query_params_snake_case",
    "_safe_float", "enrich_stock_data", "signal_to_opportunity",
    "_parse_sina_a_quote", "_parse_sina_hk_quote",
    "_V2_ROOT", "_PROJECT_ROOT_PATH", "_LEGACY_QUANT_ROOT",
    "_read_watchlist", "_write_watchlist", "_read_groups", "_write_groups",
    "_load_pipeline_runs", "_save_pipeline_runs",
    "_get_pipeline_run", "_update_pipeline_run",
    "acquire_task", "release_task", "get_running_tasks_snapshot",
    "strategy_service", "stock_pool_service", "factor_adapter", "scoring_service",
]

# ── 域定义: section_header_keyword → (blueprint_name, extra_imports) ──
DOMAINS = [
    # (section header contains, blueprint file stem, extra imports for this blueprint)
    ("健康检查",     "health",     ["json", "datetime", "shutil as _shutil", "repositories.stock_repository.StockRepository"]),
    ("股票相关",     "stock",      ["datetime", "timedelta", "json"]),
    ("自选股管理",   "watchlist",  ["uuid"]),
    ("K线相关",     "kline",      ["datetime", "timedelta"]),
    ("个股详情与市场概览", "quote_market", ["datetime", "timedelta", "re", "requests", "akshare"]),
    ("Market V2 wrappers", "market", ["akshare"]),
    ("Sentiment V2 wrappers", "sentiment", []),
    ("因子和技术指标", "analysis", ["datetime", "timedelta", "sys", "pathlib.Path"]),
    ("Tools meta endpoints", "tools", []),
    ("Risk V2 wrappers", "risk", ["sys", "pathlib.Path"]),
    ("Screening V2 wrappers", "screening", ["sys"]),
    ("Stock Analytics V2 wrappers", "stock_analytics", ["sys", "pathlib.Path"]),
    ("HK Market V2 wrappers", "hk", ["sys"]),
    ("Financial detail V2 wrappers", "financial_detail", ["sys", "datetime"]),
    ("Stock V2 wrappers", "stock_extras", ["sys"]),
    ("Portfolio V2 wrappers", "portfolio_analytics", ["sys", "pathlib.Path"]),
    ("港股综合摘要", "hk_summary", ["sys"]),
    ("策略参数优化", "strategy_analytics", ["sys", "pathlib.Path"]),
    ("流水线专用",   "pipeline",   []),  # already extracted, skip
    ("订单管理",     "orders",     ["sys", "pathlib.Path", "decimal", "json", "uuid"]),
    ("指标管理",     "indicators", ["sys", "pathlib.Path"]),
    ("Scheduler",    "scheduler",  ["datetime", "json", "uuid"]),
    ("Training Endpoints", "training", ["sys", "pathlib.Path", "glob as _glob", "json as _json"]),
    ("Charts", "charts", ["datetime", "json"]),
    ("ML Pipeline", "ml_pipeline", ["json"]),
    ("策略管理",     "strategies", ["json", "datetime"]),
    ("策略 RESTful", "strategies_rest", []),
    ("性能相关",     "performance", ["datetime"]),
    ("信号执行接口", "executions", ["datetime"]),
    ("因子解释与特征重要性", "factor_explain", ["json"]),
    ("Pipeline管理", "pipeline_mgmt", []),  # already extracted, skip
    ("Health check alias", "health", []),   # merge with health
]


def main():
    content = SERVER.read_text(encoding="utf-8")
    lines = content.split("\n")

    # 找到所有 # ==== 分割线
    section_starts = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# =====") and "====" in stripped:
            section_starts.append(i)

    # 用 domain 映射来分组
    sections = {}  # domain_name → list of line ranges [(start, end), ...]
    current_domain = None
    section_idx = 0

    for idx, start_line in enumerate(section_starts):
        # 找到这个 section 匹配的 domain
        header = lines[start_line].strip()
        domain = None
        for keyword, bp_name, _ in DOMAINS:
            if keyword in header:
                domain = bp_name
                break
        if domain is None:
            domain = "misc"

        # 找到 next section start (or end of file)
        if idx + 1 < len(section_starts):
            end_line = section_starts[idx + 1]
        else:
            end_line = len(lines)

        if domain not in sections:
            sections[domain] = []
        sections[domain].append((start_line, end_line))

    # 提取 imports & app/setup 代码 (在第一个 section header 之前)
    first_section = section_starts[0] if section_starts else 0
    preamble = lines[:first_section]
    preamble_text = "\n".join(preamble)

    # ── 生成每个 blueprint 文件 ──
    extra_imports_map = {bp: extras for _, bp, extras in DOMAINS}

    blueprint_names = []
    for domain, ranges in sorted(sections.items()):
        if domain in ("pipeline", "pipeline_mgmt"):
            continue  # already extracted

        bp_lines = _build_blueprint(domain, ranges, lines, extra_imports_map.get(domain, []))
        bp_path = ROUTES_DIR / f"{domain}.py"
        bp_path.write_text("\n".join(bp_lines) + "\n", encoding="utf-8")
        blueprint_names.append(domain)
        print(f"  ✅ {bp_path.name} ({len(bp_lines)} lines)")

    # ── 生成新的 server.py ──
    server_lines = _build_server_py(blueprint_names)
    SERVER.write_text("\n".join(server_lines) + "\n", encoding="utf-8")
    print(f"\n  ✅ server.py ({len(server_lines)} lines)")
    print(f"\nTotal: {len(blueprint_names)} blueprints + server.py app factory")


def _build_blueprint(domain: str, ranges: list, lines: list, extra_imports: list) -> list:
    """Generate blueprint file content."""
    bp_var = f"{domain}_bp"

    output = []
    output.append('"""')
    output.append(f"{domain} routes — auto-generated blueprint.")
    output.append('"""')
    output.append("import sys")
    output.append("from datetime import datetime, timedelta")
    output.append("from pathlib import Path")
    output.append("import re")

    # Extra imports
    for imp in extra_imports:
        output.append(f"import {imp}")

    output.append("")
    output.append("from flask import Blueprint, jsonify, request")
    output.append("")
    output.append("from adapters.inbound.api.shared import (")
    for name in SHARED_IMPORTS:
        output.append(f"    {name},")
    output.append(")")
    output.append("")
    output.append(f"{bp_var} = Blueprint('{domain}', __name__)")
    output.append("")

    # Extract routes from each range
    for start, end in ranges:
        section_lines = lines[start:end]
        # Replace @app.route with @bp_var.route
        processed = []
        skip_until_route = False
        for line in section_lines:
            stripped = line.strip()

            # Skip section header comments
            if stripped.startswith("# ====="):
                continue
            # Skip section description comments (single # lines before routes)
            if stripped.startswith("#") and "@app.route" not in line and "def " not in stripped:
                # keep useful comments (替代, 兼容, etc.)
                if any(kw in stripped for kw in ["替代旧", "兼容", "端点", "数据源", "封装自"]):
                    processed.append(line)
                continue

            # Replace @app.route with blueprint route
            if "@app.route(" in stripped:
                line = line.replace("@app.route(", f"@{bp_var}.route(")
                processed.append(line)
            elif "@handle_api_error" in stripped:
                processed.append(line)
            elif stripped.startswith("def "):
                processed.append(line)
            elif stripped == "":
                processed.append(line)
            else:
                # function body
                processed.append(line)

        output.extend(processed)
        output.append("")  # blank line between sections

    # Clean up: remove leading/trailing blanks, collapse 3+ blanks to 2
    result = _clean_output(output)
    return result


def _clean_output(output: list) -> list:
    text = "\n".join(output)
    # Collapse 4+ blank lines to 2
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text.split("\n")


def _build_server_py(blueprint_names: list) -> list:
    """Generate the new server.py app factory."""
    lines = []
    lines.append('"""')
    lines.append("QuantSys V2 API 服务 — App Factory")
    lines.append("")
    lines.append("Blueprint 路由:")
    for bp in sorted(blueprint_names):
        lines.append(f"  api/routes/{bp}.py")
    lines.append('"""')
    lines.append("from flask import Flask")
    lines.append("from flask_cors import CORS")
    lines.append("")
    lines.append("")
    lines.append("def create_app():")
    lines.append("    app = Flask(__name__)")
    lines.append("    CORS(app)")
    lines.append("")
    lines.append("    # ── 注册 blueprints ──")
    lines.append("")
    # pipeline first (already extracted)
    lines.append("    from adapters.inbound.api.routes.pipeline import pipeline_bp")
    lines.append("    app.register_blueprint(pipeline_bp)")
    lines.append("")
    for bp in sorted(blueprint_names):
        lines.append(f"    from adapters.inbound.api.routes.{bp} import {bp}_bp")
        lines.append(f"    app.register_blueprint({bp}_bp)")
    lines.append("")
    lines.append("    return app")
    lines.append("")
    lines.append("")
    lines.append("# ── 模块级 app 实例（兼容直接 python api/server.py 启动）──")
    lines.append("app = create_app()")
    lines.append("")
    lines.append("")
    lines.append('if __name__ == "__main__":')
    lines.append('    app.run(host="0.0.0.0", port=5001, debug=True)')
    return lines


if __name__ == "__main__":
    main()
