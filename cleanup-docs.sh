#!/bin/bash

# 文档整理脚本
# 生成时间: 2026-06-26
# 功能: 整理根目录的临时文档到合适的位置

set -e  # 遇到错误立即退出

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "文档整理脚本"
echo "========================================"
echo ""

# 创建必要的目录
echo "1. 创建目标目录..."
mkdir -p .archive/2026-06-reports
mkdir -p docs/architecture
mkdir -p docs/features
mkdir -p docs/setup
mkdir -p docs/guides
mkdir -p docs/plans
echo "   ✓ 目录创建完成"
echo ""

# 移动到 docs/architecture/
echo "2. 移动架构文档到 docs/architecture/..."
mv -v AUTONOMY_GAP_ANALYSIS.md docs/architecture/autonomy-gap-analysis.md 2>/dev/null || true
mv -v CORRECT_SYSTEM_ARCHITECTURE.md docs/architecture/correct-system-architecture.md 2>/dev/null || true
mv -v SCHEDULING_ARCHITECTURE.md docs/architecture/scheduling-architecture.md 2>/dev/null || true
mv -v WORKFLOW_DESIGN_FOR_V2.md docs/architecture/workflow-design-for-v2.md 2>/dev/null || true
echo "   ✓ 架构文档移动完成"
echo ""

# 移动到 docs/features/
echo "3. 移动功能文档到 docs/features/..."
mv -v GAME_INTELLIGENCE_MODULE_SUMMARY.md docs/features/game-intelligence-module-summary.md 2>/dev/null || true
echo "   ✓ 功能文档移动完成"
echo ""

# 移动到 docs/setup/
echo "4. 移动设置文档到 docs/setup/..."
mv -v CRONTAB_SETUP.md docs/setup/crontab-setup.md 2>/dev/null || true
echo "   ✓ 设置文档移动完成"
echo ""

# 移动到 docs/guides/
echo "5. 移动指南文档到 docs/guides/..."
mv -v ENTERPRISE_WORKFLOW_RECOMMENDATION.md docs/guides/enterprise-workflow-recommendation.md 2>/dev/null || true
mv -v NEXT_STEPS_AUTONOMY.md docs/guides/next-steps-autonomy.md 2>/dev/null || true
echo "   ✓ 指南文档移动完成"
echo ""

# 移动到 docs/plans/
echo "6. 移动计划文档到 docs/plans/..."
mv -v SCHEDULER_REFACTOR_PLAN.md docs/plans/scheduler-refactor-plan.md 2>/dev/null || true
mv -v TASK_4_WORKFLOW_PLAN.md docs/plans/task-4-workflow-plan.md 2>/dev/null || true
echo "   ✓ 计划文档移动完成"
echo ""

# 归档临时报告
echo "7. 归档临时报告到 .archive/2026-06-reports/..."

# 日常工作总结类
mv -v DAILY_WORK_SUMMARY_2026-06-26.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v FINAL_WORK_SUMMARY_2026-06-26.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v MEMORY_UPDATE_SUMMARY.md .archive/2026-06-reports/ 2>/dev/null || true

# 状态检查类
mv -v COMPLETE_STATUS_REPORT.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v CURRENT_STATUS_CHECK.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v DATA_STATUS_CHECK.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v IMPLEMENTATION_STATUS_CHECK.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v IMPLEMENTATION_STATUS_REPORT.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v QUANTSYS_V2_SCHEDULER_CHECK.md .archive/2026-06-reports/ 2>/dev/null || true

# 任务完成报告类
mv -v TASK_100_PERCENT_COMPLETE.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v TASK_COMPLETION_STATUS.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v TASK_3_NOTIFICATION_SERVICE.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v TASK_3_NOTIFICATION_SERVICE_COMPLETION.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v TASK_CONFIGURE_SCHEDULER.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v TASK_CONFIGURE_SCHEDULER_REPORT.md .archive/2026-06-reports/ 2>/dev/null || true

# Scheduler重构系列
mv -v SCHEDULER_REFACTOR_COMPLETION_REPORT.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v SCHEDULER_REFACTOR_FINAL_COMPLETION.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v SCHEDULER_REFACTOR_FINAL_STATUS.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v SCHEDULER_REVIEW_AND_TEST_REPORT.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v SCHEDULER_BUSINESS_LOGIC_IMPLEMENTATION_REPORT.md .archive/2026-06-reports/ 2>/dev/null || true

# 最终总结类
mv -v FINAL_ANSWER.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v FINAL_COMPLETION_REPORT_2026-06-26.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v FINAL_IMPLEMENTATION_CHECKLIST.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v FINAL_REVIEW_AND_TEST_REPORT.md .archive/2026-06-reports/ 2>/dev/null || true
mv -v FINAL_STATUS_SUMMARY.md .archive/2026-06-reports/ 2>/dev/null || true

# 其他报告
mv -v CLAUDE_UPDATE_REPORT.md .archive/2026-06-reports/ 2>/dev/null || true

echo "   ✓ 临时报告归档完成"
echo ""

# 显示最终结果
echo "========================================"
echo "整理完成！"
echo "========================================"
echo ""
echo "根目录剩余的 .md 文件:"
ls -1 *.md 2>/dev/null || echo "   (无)"
echo ""
echo "归档的文件数量:"
echo "   .archive/2026-06-reports/: $(ls -1 .archive/2026-06-reports/*.md 2>/dev/null | wc -l | tr -d ' ')"
echo ""
echo "移动到 docs/ 的文件数量:"
echo "   docs/architecture/: $(ls -1 docs/architecture/*.md 2>/dev/null | grep -E '(autonomy-gap|correct-system|scheduling|workflow-design)' | wc -l | tr -d ' ')"
echo "   docs/features/: $(ls -1 docs/features/*.md 2>/dev/null | grep game-intelligence | wc -l | tr -d ' ')"
echo "   docs/setup/: $(ls -1 docs/setup/*.md 2>/dev/null | grep crontab | wc -l | tr -d ' ')"
echo "   docs/guides/: $(ls -1 docs/guides/*.md 2>/dev/null | grep -E '(enterprise-workflow|next-steps)' | wc -l | tr -d ' ')"
echo "   docs/plans/: $(ls -1 docs/plans/*.md 2>/dev/null | grep -E '(scheduler-refactor-plan|task-4)' | wc -l | tr -d ' ')"
echo ""
