#!/bin/bash
# PreToolUse(Bash) 钩子：主工作区的 git 写操作硬阻断（deny）
# （worktree 内不受影响；main 分支上的 commit 放行；非 git 写命令直接放行）
# 规则：feature 工作必须在独立 worktree 进行（git worktree add .claude/worktrees/<name>）
input=$(cat)
cmd=$(echo "$input" | jq -r '.tool_input.command // empty')

# 只关心 git 写/建分支命令，其余直接放行
echo "$cmd" | grep -qE 'git +(commit|checkout|switch|branch|merge|rebase|reset +--hard)' || { echo '{}'; exit 0; }

# 目标目录判定：命令以 cd <dir> 开头、或 git -C <dir> 形式时，以该目录的 git 状态为准
# （否则钩子看到的是会话 cwd，会误伤在 worktree 里的合法操作）
target_dir=$(echo "$cmd" | sed -En 's/^ *cd +"?([^ "&;|]+)"? *&&.*/\1/p')
[ -z "$target_dir" ] && target_dir=$(echo "$cmd" | sed -En 's/.*git +-C +"?([^ "&;|]+)"? +.*/\1/p')
GIT="git"
[ -n "$target_dir" ] && GIT="git -C $target_dir"

common=$($GIT rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || { echo '{}'; exit 0; }
main_root=$(dirname "$common")
top=$($GIT rev-parse --show-toplevel 2>/dev/null)
branch=$($GIT branch --show-current 2>/dev/null)

# 只约束主工作区；worktree 内全部放行
[ "$top" = "$main_root" ] || { echo '{}'; exit 0; }

deny() {
  jq -n --arg b "$branch" --arg c "$cmd" --arg r "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ("[主工作区保护] " + $r + " 当前分支: " + $b + "；命令: " + $c)
    }
  }'
  exit 0
}

# 1) 建分支/切支：主工作区一律禁止（无论在哪个分支上——这是违规工作线的第一步）
#    覆盖 checkout -b/-B、switch -c/-C、git branch <name>（不含 -d/-D/-m 等管理操作）
if echo "$cmd" | grep -qE 'git +(checkout +-[^ ]*[bB]|switch +-[^ ]*[cC]|branch +[^- ])'; then
  deny "禁止在主工作区创建分支。请改用 worktree：git worktree add .claude/worktrees/<name> -b <branch>（或 EnterWorktree）。"
fi

# 2) 普通 checkout/switch 切到非 main 分支：主工作区禁止（防止他人分支被切进来干活）
if echo "$cmd" | grep -qE 'git +(checkout|switch) +[^- ]' && \
   ! echo "$cmd" | grep -qE 'git +(checkout|switch) +(main|master)( *$| *)'; then
  deny "禁止在主工作区切换到 feature 分支。如需在该分支工作，请建 worktree：git worktree add .claude/worktrees/<name> <branch>。"
fi

# 3) 写操作：主工作区的非 main 分支上禁止 commit/merge/rebase/reset --hard
if [ "$branch" != "main" ] && [ -n "$branch" ] && \
   echo "$cmd" | grep -qE 'git +(commit|merge +[^-]|rebase( +|$)|reset +--hard)'; then
  deny "禁止在主工作区的 feature 分支上执行 git 写操作。请把该分支迁到 worktree：git worktree add .claude/worktrees/<name> $branch，或先切回 main。"
fi

echo '{}'
