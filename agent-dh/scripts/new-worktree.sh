#!/bin/bash
# 快速创建 worktree 的脚本

set -e

TASK_NAME=${1:-}

if [ -z "$TASK_NAME" ]; then
  echo "❌ 请提供任务名称"
  echo "用法: ./scripts/new-worktree.sh <任务名>"
  echo "例如: ./scripts/new-worktree.sh req-123"
  exit 1
fi

WORKTREE_PATH=".claude/worktrees/$TASK_NAME"
BRANCH_NAME="feat/$TASK_NAME"

# 检查分支是否已存在
if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
  echo "❌ 分支 $BRANCH_NAME 已存在"
  echo "💡 使用不同的任务名，或删除旧分支: git branch -D $BRANCH_NAME"
  exit 1
fi

# 检查 worktree 目录是否已存在
if [ -d "$WORKTREE_PATH" ]; then
  echo "❌ 目录 $WORKTREE_PATH 已存在"
  exit 1
fi

# 创建 worktree
git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME"

echo ""
echo "✅ Worktree 创建成功！"
echo "📂 路径: $WORKTREE_PATH"
echo "🌿 分支: $BRANCH_NAME"
echo ""
echo "🚀 下一步:"
echo "   cd $WORKTREE_PATH"
echo "   # 开始你的工作..."
echo "   git add ."
echo "   git commit -m 'feat: 第一次提交'"
