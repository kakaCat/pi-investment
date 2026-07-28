#!/bin/bash
# PreToolUse(Bash) 钩子：在主工作区的 feature 分支上执行 git 写操作时强制确认
# （worktree 内、main 分支上不受影响；非 git 写命令直接放行）
input=$(cat)
cmd=$(echo "$input" | jq -r '.tool_input.command // empty')

echo "$cmd" | grep -qE 'git +(commit|checkout +(-b|-B)|switch +(-c|-C)|merge|rebase|reset +--hard)' || { echo '{}'; exit 0; }

common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || { echo '{}'; exit 0; }
main_root=$(dirname "$common")
top=$(git rev-parse --show-toplevel 2>/dev/null)
branch=$(git branch --show-current 2>/dev/null)

if [ "$top" = "$main_root" ] && [ "$branch" != "main" ]; then
  jq -n --arg b "$branch" --arg c "$cmd" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "ask",
      permissionDecisionReason: ("主工作区当前在 feature 分支（" + $b + "）上，即将执行 git 写操作: " + $c + "。仓库规则要求 feature 工作在独立 worktree 进行（git worktree add .claude/worktrees/<name>）。确认继续？")
    }
  }'
else
  echo '{}'
fi
