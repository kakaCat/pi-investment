#!/usr/bin/env python3
"""
文档清理脚本 - 将根目录违规 MD 文件迁移到 docs/ 子目录

根据 docs/DOCUMENT-MANAGEMENT-PLAN.md 规范：
- 根目录只保留 README.md 和 CLAUDE.md
- 工作报告 → docs/work-logs/YYYY-MM/
- 架构文档 → docs/architecture/
- ADR → docs/adr/
- RFC → docs/rfcs/
"""

# 2026-10-01（REQ-261001145152-3982 t-720861）修补三处：
#   ① 本文件原先在 py3.8 下**直接崩**（`def classify_file(...) -> tuple[str, str]` 在 3.8 会
#      `TypeError: 'type' object is not subscriptable`）→ 加 `from __future__ import annotations`；
#   ② 只能交互式 `input()` 确认、**没有 --dry-run**，无法在不改磁盘的前提下审阅迁移清单；
#   ③ 目标目录写死为 quantsys-v2 **项目根**（那里早已只剩 README/CLAUDE），
#      而真正需要归位的 140 个 md 在 **docs/ 根** → 加 `--root` 参数；
#   ④ 迁移后**不更新引用**（实测有 235 处引用指向 docs/ 根，99 个不同路径）→ 加 `--update-refs`。
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# quantsys-v2 根目录（--root 可覆盖；默认仍是历史行为：清项目根）
ROOT = Path(__file__).parent.parent / "quantsys-v2"

# 引用重写时要扫的文件类型（迁移后把 docs/<旧> 改成 docs/<新>）
REF_SUFFIXES = ('.md', '.py', '.yml', '.yaml', '.json', '.txt')

# 分类规则
CLASSIFICATION_RULES = {
    # 工作报告类 - 按月份归档
    'work-logs': [
        r'.*_(REPORT|COMPLETE|SUMMARY|FIX|STATUS|ANALYSIS)\.md$',
        r'^(BUGFIX|FIX|MIGRATION|REFACTOR|PHASE|PROJECT|TASK|BATCH).*\.md$',
        r'.*(COMPLETION|PROGRESS|SUCCESS|FINAL|HANDOVER|VERIFICATION).*\.md$',
        r'^CONNECTION_LEAK.*\.md$',
        r'^FRONTEND_DISPLAY.*\.md$',
        r'^DOMAIN_REFACTORING.*\.md$',
        r'^ACCEPTANCE\.md$',
        r'^EXECUTIVE_SUMMARY\.txt$',
        r'^DELIVERY_SUMMARY\.txt$',
        r'^COMMIT_MESSAGE\.txt$',
    ],

    # 架构文档类
    'architecture': [
        r'^AGENTS\.md$',
        r'^ARCHITECTURE.*\.md$',
        r'^FUNCTIONALITY_OVERVIEW\.md$',
        r'^PERFORMANCE_OPTIMIZATION_README\.md$',
    ],

    # 指南类
    'guides': [
        r'^DATA_ACCESS_GUIDE\.md$',
        r'^INSTALLATION\.md$',
        r'^DEPLOYMENT_PLAN\.md$',
        r'^PYTHON_ENVIRONMENT\.md$',
        r'^README_(PHASE|MIGRATION|PYTHON)\.md$',
        r'^LOGGING_WORKFLOW\.md$',
    ],

    # 调度系统相关（单独归档）
    'scheduler': [
        r'^SCHEDULER.*\.md$',
    ],

    # V14 策略相关（单独归档）
    'v14': [
        r'^V14_.*\.md$',
        r'^V15_.*\.md$',
    ],

    # ML 相关
    'ml': [
        r'^ML_.*\.md$',
    ],

    # API 相关
    'api': [
        r'^API_.*\.md$',
        r'^URL_.*\.md$',
        r'^FLASK_.*\.md$',
    ],

    # 其他技术文档
    'technical': [
        r'^TOOL_ISSUES.*\.md$',
        r'^STOCK_API.*\.md$',
        r'^STRATEGY_API.*\.md$',
        r'^ROOT_CAUSE.*\.md$',
    ],
}

# 需要保留的文件（白名单）
KEEP_FILES = {
    'README.md',
    'CLAUDE.md',
    'AUDIT_FIX_PLAN.md',  # 当前审计正在使用
}

# 月份推测规则（基于文件名）
def guess_month(filename: str) -> str:
    """从文件名推测创建月份"""
    # 尝试从文件名提取日期
    date_match = re.search(r'20260(\d{2})', filename)
    if date_match:
        month = date_match.group(1)
        return f"2026-{month}"

    # 根据关键词推测
    if 'MIGRATION' in filename or 'FLASK' in filename:
        return "2026-07"  # Flask→FastAPI 迁移在 7 月
    if 'SCHEDULER' in filename:
        return "2026-08"  # 调度迁移在 8 月
    if 'V14' in filename:
        return "2026-07"  # V14 策略在 7 月

    # 默认当前月份
    return datetime.now().strftime("%Y-%m")


def classify_file(filename: str) -> Tuple[str, str]:
    """
    分类文件

    Returns:
        (category, target_path) - 类别和目标路径
    """
    # 检查白名单
    if filename in KEEP_FILES:
        return ('keep', '')

    # 按规则分类
    for category, patterns in CLASSIFICATION_RULES.items():
        for pattern in patterns:
            if re.match(pattern, filename, re.IGNORECASE):
                # work-logs 需要按月份归档
                if category == 'work-logs':
                    month = guess_month(filename)
                    return (category, f"docs/work-logs/{month}/{filename}")
                else:
                    return (category, f"docs/{category}/{filename}")

    # 未分类的归入 misc
    return ('misc', f"docs/misc/{filename}")


def update_references(pairs: List[Tuple[str, str]], base: Path, dry_run: bool) -> int:
    """把仓库内引用从 `docs/<旧相对路径>` 改为 `docs/<新相对路径>`。

    2026-10-01（t-720861）新增：本脚本原先只搬文件、**不管引用**——实测 quantsys-v2 内
    有 235 处引用指向 docs/ 根（99 个不同路径），不重写就是大片死链。

    Args:
        pairs: [(相对 quantsys-v2 的旧路径, 相对 quantsys-v2 的新路径), ...]
               —— 例如 ("docs/OLD.md", "docs/misc/OLD.md")；
               引用文本即按这两个字符串直接替换，**不再额外拼 `docs/` 前缀**
               （2026-10-01 修补：初版多拼了一次前缀 → 去找 `docs/docs/...`，预估恒为 0）。
        base: 相对路径的基准目录（如 quantsys-v2）
        dry_run: True 时只统计不落盘
    """
    repo_root = Path(__file__).parent.parent
    # 长路径优先，避免 "docs/a.md" 抢走 "docs/a.md" 的前缀关系
    pairs = sorted(pairs, key=lambda p: -len(p[0]))
    touched = 0
    for f in repo_root.rglob('*'):
        if not f.is_file() or f.suffix not in REF_SUFFIXES:
            continue
        if any(part in ('.git', 'venv', '.venv', 'node_modules', '__pycache__') for part in f.parts):
            continue
        try:
            text = f.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        original = text
        for old_ref, new_ref in pairs:
            if old_ref in text:
                text = text.replace(old_ref, new_ref)
        if text != original:
            touched += 1
            if not dry_run:
                f.write_text(text, encoding='utf-8')
    return touched


def main(argv: List[str] | None = None):
    """执行文档清理。默认仍清 quantsys-v2 项目根；`--root docs` 可改为清 docs/ 根。"""
    parser = argparse.ArgumentParser(
        description="把散落的 md/txt 按规范归入 docs/ 子目录（默认清 quantsys-v2 项目根）"
    )
    parser.add_argument("--root", default=None,
                        help="要清理的目录（相对 quantsys-v2，如 docs）；缺省 = 项目根")
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印迁移清单与引用改写数，**不动任何文件**")
    parser.add_argument("--yes", action="store_true", help="跳过交互确认")
    parser.add_argument("--update-refs", action="store_true",
                        help="迁移后同步重写仓库内引用（docs/<旧> → docs/<新>）")
    args = parser.parse_args(argv)

    global ROOT
    scan_root = (ROOT / args.root) if args.root else ROOT

    # 2026-10-01（t-720861 复核）：目录不存在时必须**响亮失败**。
    # 初版会让 glob 静默返回空、打印"扫描到 0 个文件 + dry-run 结束"，
    # 使用者会误以为"没有需要迁的文件"（本仓反复出现过的"静默降级"模式）。
    if not scan_root.is_dir():
        print(f"❌ 扫描目录不存在：{scan_root}", file=sys.stderr)
        print("   传 --root 时请用**相对 quantsys-v2 的路径**（如 --root docs）", file=sys.stderr)
        return 2

    print("=" * 60)
    print("quantsys-v2 文档清理脚本")
    print(f"  扫描目录: {scan_root}")
    print(f"  模式: {'DRY-RUN（不改磁盘）' if args.dry_run else '执行'}")
    print("=" * 60)
    print()

    # 扫描 MD 和 TXT 文件
    md_files = list(scan_root.glob("*.md")) + list(scan_root.glob("*.txt"))
    md_files = [f for f in md_files if f.is_file()]

    print(f"📂 扫描到 {len(md_files)} 个文档文件")
    print()

    # 分类统计
    classification: Dict[str, List[tuple]] = {}

    for file in md_files:
        category, target_path = classify_file(file.name)

        if category == 'keep':
            continue

        if category not in classification:
            classification[category] = []

        classification[category].append((file, target_path))

    # 显示分类结果
    print("📊 分类结果:")
    print()
    for category, files in sorted(classification.items()):
        print(f"  {category:15s} : {len(files):3d} 个文件")
    print()
    print(f"  {'保留':15s} : {len(KEEP_FILES):3d} 个文件")
    print()

    total_to_move = sum(len(files) for files in classification.values())
    print(f"📦 总计需要迁移: {total_to_move} 个文件")
    print()

    # dry-run：只打印清单（含引用改写预估），不动磁盘
    if args.dry_run:
        print("— dry-run 迁移清单（前 20 条）—")
        shown = 0
        rel_pairs: List[Tuple[str, str]] = []
        for category, files in classification.items():
            for source_file, target_path in files:
                try:
                    old_rel = str(source_file.relative_to(ROOT))
                except ValueError:
                    old_rel = source_file.name
                new_rel = target_path
                rel_pairs.append((old_rel, new_rel))
                if shown < 20:
                    print(f"    {old_rel:70s} → {new_rel}")
                    shown += 1
        print(f"  （共 {len(rel_pairs)} 条）")
        print()
        if args.update_refs:
            n = update_references(rel_pairs, ROOT, dry_run=True)
            print(f"  引用重写预估：将触及 **{n}** 个文件")
        else:
            print("  （未加 --update-refs：迁移后引用可能变死链，建议一并开启）")
        print()
        print("✅ dry-run 结束，未改动任何文件。")
        return

    # 询问确认（--yes 跳过）
    if not args.yes:
        response = input("是否执行迁移？(yes/no): ").strip().lower()
        if response not in ['yes', 'y']:
            print("❌ 取消操作")
            return

    print()
    print("🚀 开始迁移...")
    print()

    # 执行迁移
    success_count = 0
    error_count = 0
    moved_pairs: List[Tuple[str, str]] = []

    for category, files in classification.items():
        for source_file, target_path in files:
            target = ROOT / target_path

            try:
                # 创建目标目录
                target.parent.mkdir(parents=True, exist_ok=True)

                try:
                    old_rel = str(source_file.relative_to(ROOT))
                except ValueError:
                    old_rel = source_file.name
                moved_pairs.append((old_rel, target_path))

                # 移动文件
                source_file.rename(target)

                print(f"  ✅ {source_file.name:50s} → {target_path}")
                success_count += 1

            except Exception as e:
                print(f"  ❌ {source_file.name:50s} 失败: {e}")
                error_count += 1

    print()
    print("=" * 60)
    print("迁移完成")
    print("=" * 60)
    print(f"  ✅ 成功: {success_count}")
    print(f"  ❌ 失败: {error_count}")
    print()

    # 引用重写（--update-refs）
    if args.update_refs and moved_pairs:
        touched = update_references(moved_pairs, ROOT, dry_run=False)
        print(f"🔗 引用重写：触及 {touched} 个文件（docs/<旧> → docs/<新>）")
        print()

    # 生成迁移报告（dry-run 已在上面 return，不会走到这里）
    report_path = ROOT / "docs/work-logs" / datetime.now().strftime("%Y-%m") / "document-cleanup-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w') as f:
        f.write(f"# 文档清理报告\n\n")
        f.write(f"**日期**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## 统计\n\n")
        f.write(f"- 总计扫描: {len(md_files)} 个文件\n")
        f.write(f"- 保留: {len(KEEP_FILES)} 个文件\n")
        f.write(f"- 迁移: {success_count} 个文件\n")
        f.write(f"- 失败: {error_count} 个文件\n\n")
        f.write(f"## 分类统计\n\n")
        for category, files in sorted(classification.items()):
            f.write(f"- {category}: {len(files)} 个文件\n")
        f.write(f"\n## 迁移清单\n\n")
        for category, files in sorted(classification.items()):
            f.write(f"### {category}\n\n")
            for source_file, target_path in sorted(files):
                f.write(f"- `{source_file.name}` → `{target_path}`\n")
            f.write(f"\n")

    print(f"📄 迁移报告已生成: {report_path}")
    print()

    # 下一步建议
    print("📋 下一步:")
    print("  1. 检查迁移结果: git status")
    print("  2. 验证文档链接是否需要更新")
    print("  3. 提交变更: git add docs/ && git commit -m 'docs: 清理根目录文档'")
    print()


if __name__ == "__main__":
    # 2026-10-01（t-720861 复核）：必须把 main() 的返回码**传播**为退出码。
    # 初版是裸 `main()`，于是"扫描目录不存在"时虽打印了 ❌，退出码仍是 0
    # —— 在脚本/CI 里会被当成成功（失败不响亮）。
    raise SystemExit(main())
