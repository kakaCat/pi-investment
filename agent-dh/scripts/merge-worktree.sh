#!/bin/bash
# 合并 worktree 到 main

set -e

TASK_NAME=${1:-}

if [ -z "$TASK_NAME" ]; then
  echo "❌ 请提供任务名称"
  echo "用法: ./scripts/merge-worktree.sh <任务名>"
  exit 1
fi

WORKTREE_PATH=".claude/worktrees/$TASK_NAME"
BRANCH_NAME="feat/$TASK_NAME"

# 检查 worktree 是否存在
if [ ! -d "$WORKTREE_PATH" ]; then
  echo "❌ Worktree 不存在: $WORKTREE_PATH"
  exit 1
fi

echo "🔄 合并 $BRANCH_NAME 到 main..."

# 切换到 main
git checkout main

# 合并
git merge --no-ff "$BRANCH_NAME" -m "Merge $BRANCH_NAME"

# 推送
git push origin main

# 删除 worktree
git worktree remove "$WORKTREE_PATH"

# 删除分支
git branch -d "$BRANCH_NAME"

echo ""
echo "✅ 任务完成！"
echo "🗑️  已删除 worktree 和分支"
