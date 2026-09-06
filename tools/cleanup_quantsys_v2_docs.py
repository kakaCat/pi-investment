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

import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# quantsys-v2 根目录
ROOT = Path(__file__).parent.parent / "quantsys-v2"

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


def classify_file(filename: str) -> tuple[str, str]:
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


def main():
    """执行文档清理"""
    print("=" * 60)
    print("quantsys-v2 文档清理脚本")
    print("=" * 60)
    print()

    # 扫描根目录 MD 和 TXT 文件
    md_files = list(ROOT.glob("*.md")) + list(ROOT.glob("*.txt"))
    md_files = [f for f in md_files if f.is_file()]

    print(f"📂 扫描到 {len(md_files)} 个文档文件")
    print()

    # 分类统计
    classification: Dict[str, List[tuple[Path, str]]] = {}

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

    # 询问确认
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

    for category, files in classification.items():
        for source_file, target_path in files:
            target = ROOT / target_path

            try:
                # 创建目标目录
                target.parent.mkdir(parents=True, exist_ok=True)

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

    # 生成迁移报告
    report_path = ROOT / "docs/work-logs/2026-09/document-cleanup-report.md"
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
    main()
