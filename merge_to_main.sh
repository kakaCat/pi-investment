#!/bin/bash
# Merge worktree-v2-architecture-audit into main

set -e

echo "正在合并 P1-2 架构迁移到 main 分支..."

# 获取主仓库路径
MAIN_REPO="/Users/yunpeng/pi-investment"

cd "$MAIN_REPO"

echo "1. 确保 main 分支是最新的"
git checkout main
git pull origin main

echo "2. 合并 worktree-v2-architecture-audit 分支"
git merge --no-ff worktree-v2-architecture-audit -m "Merge branch 'worktree-v2-architecture-audit': P1-2 Data Access Architecture Migration

完成 P1-2 数据访问架构迁移，消除应用层对 akshare/tushare 的直接依赖

## 迁移成果
- 违规文件: 23 → 0 (100% 清零)
- 迁移文件: 7 个 (6 个服务层 + 1 个基础设施层)
- 迁移导入: 15+ 处

## 验证
- ✅ 违规检测: 0 个违规
- ✅ 语法检查: 所有文件通过
- ✅ 架构合规: 正确使用 provider_manager

## 文档
- 迁移报告: docs/superpowers/migration-reports/2026-08-15-p1-2-data-access-migration.md
- 审计进度: docs/superpowers/architecture-audit-progress.md
"

echo "3. 推送到远程"
git push origin main

echo "✅ 合并完成！"
