#!/usr/bin/env bash
# sync-to-github.sh — 把 monorepo 内的 dsh-pmboard 单向同步到 GitHub 独立仓库
#
# 开发主阵地：agent-dh/packages/web/dsh-pmboard（本脚本所在目录，绝不改动）
# 发布镜像：  https://github.com/kakaCat/dsh-pmboard
# 本地克隆：  $PMBOARD_MIRROR（默认 ~/dsh-pmboard）
#
# 用法：
#   ./scripts/sync-to-github.sh "commit message"   # 同步并推送
#   ./scripts/sync-to-github.sh --dry-run          # 只看差异，不提交不推送
#
# 认证（镜像仓库 origin 已配置为 SSH git@github.com:kakaCat/dsh-pmboard.git）：
#   1) 默认走 SSH key（~/.ssh/id_ed25519，已验证可用），无需任何 token
#   2) 备选：GH_TOKEN=<token> ./scripts/sync-to-github.sh ...（临时 https 推送，不落盘）
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)/"          # monorepo 包目录（尾带 /）
MIRROR="${PMBOARD_MIRROR:-$HOME/dsh-pmboard}"     # 镜像克隆目录
DRY_RUN=0
MSG=""

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    *) MSG="$arg" ;;
  esac
done

if [ ! -d "$MIRROR/.git" ]; then
  echo "❌ 镜像目录不存在或不是 git 仓库: $MIRROR"
  echo "   先执行: git clone https://github.com/kakaCat/dsh-pmboard.git $MIRROR"
  exit 1
fi

EXCLUDES=(--exclude node_modules --exclude dist --exclude lib --exclude .DS_Store --exclude .git --exclude '*.log')

echo "==> 源:      $SRC"
echo "==> 镜像:    $MIRROR"

if [ "$DRY_RUN" = "1" ]; then
  rsync -ain --delete "${EXCLUDES[@]}" "$SRC" "$MIRROR/" | head -50
  exit 0
fi

rsync -a --delete "${EXCLUDES[@]}" "$SRC" "$MIRROR/"

cd "$MIRROR"
if [ -z "$(git status --porcelain)" ]; then
  echo "✅ 无变化，无需推送"
  exit 0
fi

# 默认提交信息带 monorepo 溯源信息
if [ -z "$MSG" ]; then
  SRC_COMMIT="$(git -C "$(cd "$SRC" && git rev-parse --show-toplevel)" log -1 --format='%h %s' -- agent-dh/packages/web/dsh-pmboard 2>/dev/null || echo unknown)"
  MSG="sync: from pi-investment monorepo ($SRC_COMMIT)"
fi

git add -A
git commit -m "$MSG"

# GH_TOKEN 存在则临时嵌入 URL 推送（不落盘），否则走系统 credential helper
if [ -n "${GH_TOKEN:-}" ]; then
  git push "https://x-access-token:${GH_TOKEN}@github.com/kakaCat/dsh-pmboard.git" main
else
  git push origin main
fi

echo "✅ 已推送到 https://github.com/kakaCat/dsh-pmboard"
