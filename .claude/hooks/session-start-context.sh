#!/bin/bash
# SessionStart 钩子：让每个窗口立刻知道自己的分支/worktree 归属
# 输出 additionalContext 注入会话上下文
cd "${CLAUDE_PROJECT_DIR:-$PWD}" 2>/dev/null || exit 0

branch=$(git branch --show-current 2>/dev/null)
common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || exit 0
main_root=$(dirname "$common")
top=$(git rev-parse --show-toplevel 2>/dev/null)
dirty=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
others=$(git worktree list 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')

if [ "$top" = "$main_root" ]; then
  location="主工作区"
  if [ "$branch" != "main" ]; then
    warn="⚠️ 你在主工作区的 feature 分支 [${branch}] 上——违反仓库 worktree 隔离规则。若这条工作线不是你的，停手；若要做新工作，先用 EnterWorktree 建自己的隔离工作区。"
  else
    warn="规则提醒：修改代码必须先用 EnterWorktree 建隔离 worktree，完成并合并后再删。"
  fi
else
  location="worktree: $top"
  warn=""
fi

ctx="[工作区归属] $location | 分支: ${branch:-detached} | 未提交文件: ${dirty}个 | 共存 worktree: ${others}个。${warn}"
jq -n --arg c "$ctx" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$c}}'
