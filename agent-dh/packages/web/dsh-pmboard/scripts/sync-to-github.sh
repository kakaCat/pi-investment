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
#
# 单向同步的两类例外（2026-09-29 定：镜像侧曾直接在 GitHub 上做发布形态修复，
# 裸 rsync 会把它们覆盖/删除，故显式声明）：
#   1) 镜像专属文件：pnpm-lock.yaml / pnpm-workspace.yaml 只存在于发布仓库（见 EXCLUDES）
#   2) 镜像专属字段：package.json 的 dsh-tools 版本与 exports."." 的 default 条件
#      （见下方 MIRROR_OVERRIDES —— rsync 后按此处声明打回并校验）
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

# 只发布项目本体（源码/测试/脚本/模板/包元数据/README/LICENSE/CHANGELOG）。
# 以下为本地开发产物或内部材料，不进公开仓库（镜像 kakaCat/dsh-pmboard 是 public）：
EXCLUDES=(
  --exclude node_modules --exclude dist --exclude lib
  --exclude .DS_Store --exclude .git --exclude '*.log'
  --exclude 'scripts/.probe'            # 本地取证脚本/截图（含本地 cookie 脚本），仅本机用
  --exclude 'CONFLICT-REPORT.md'        # 内部事故复盘报告
  --exclude 'FIX-REPORT.md'             # 内部修复记录
  --exclude '*redesign.html'            # 设计探索稿（非交付物）
  --exclude 'stage-modals-*.html'       # 同上（stage-modals-alpine 为源码注释引用的设计基线，仍在源目录保留）
  --exclude 'workflow-stage-modal.html'
  # 内部分析/设计稿与调试残留（同 CONFLICT/FIX-REPORT 口径：非交付物，只发代码）
  # 注意：rsync 模式大小写敏感（git 因 core.ignoreCase 不是），RTM/summary 等
  # 在源目录里大小写混写，故用 [Rr][Tt][Mm] 字符类覆盖，勿简化成 [Rr]TM
  --exclude '[Rr][Tt][Mm]-*.md' --exclude '*[Rr][Tt][Mm]-*.md'   # RTM 设计/分析/对比稿（含名称中段含 RTM 的）
  --exclude '*-ANALYSIS.md' --exclude '*-analysis.md'
  --exclude '*-SUMMARY.md' --exclude '*-summary.md'
  --exclude '*-COMPARISON.md' --exclude '*-comparison.md'
  --exclude '*-STRATEGY.md' --exclude '*-strategy.md'
  --exclude '*-VS-*.md'                 # 内部 A/B 对比稿（如 BOARD-VS-NODE-PANEL）
  --exclude '*report.md'                # 内部修复/验收/联调报告（小写；大写版见上方两条显式）
  --exclude '*-mock.html'               # 界面草稿（同 *redesign.html 口径）
  --exclude 'tmp-*.mts'                 # 临时调试脚本
  --exclude '.worktrees'                # 误建在包目录内的 git 工作树（含内部需求资料）
  --exclude '/docs'                     # 指向包外 monorepo 文档的符号链接（镜像内必然悬空）
  # 镜像专属的打包元数据：源目录没有、只存在于发布仓库（独立安装时锁版本用）。
  # 被 exclude 的文件不会被 --delete 删除，故这两个文件在镜像里是持久保留的。
  --exclude 'pnpm-lock.yaml' --exclude 'pnpm-workspace.yaml'
  --exclude '[[]^' --exclude '[]]*'     # shell glob 事故留下的空文件，勿发布
)

echo "==> 源:      $SRC"
echo "==> 镜像:    $MIRROR"

if [ "$DRY_RUN" = "1" ]; then
  rsync -ain --delete --stats "${EXCLUDES[@]}" "$SRC" "$MIRROR/" | head -200
  exit 0
fi

rsync -a --delete "${EXCLUDES[@]}" "$SRC" "$MIRROR/"

# ── 镜像专属字段覆盖（rsync 后打回，见文件头「两类例外」）─────────────────────
# 这两处是「发布形态」而非「开发形态」的差异，所以不写在 monorepo 源目录里：
#   · dsh-tools 0.2.0-rc.1 —— 镜像作为独立包装进他人 DSH 时按新一代框架解析；
#     agent-dh 全仓插件仍钉 0.1.6-alpha.2 一代（本仓有混代 Symbol 分裂史），源目录不动
#   · exports."." 的 default 条件 —— DSH 的 resolveBundleDir 用 createRequire（CJS）
#     解析插件入口，只写 import 条件会 ERR_PACKAGE_PATH_NOT_EXPORTED
# 改版本 / 加条件只改下面 WANT，每次同步自动打回，不会再被 rsync 覆盖。
PMBOARD_MIRROR_PKG="$MIRROR/package.json" node <<'MIRROR_OVERRIDES'
const fs = require('fs')
const p = process.env.PMBOARD_MIRROR_PKG
const WANT = { dshTools: '0.2.0-rc.1', entryDefault: './dist/index.mjs' }
const j = JSON.parse(fs.readFileSync(p, 'utf8'))
let dirty = false
j.dependencies ??= {}
if (j.dependencies['@deepseek-ai/dsh-tools'] !== WANT.dshTools) {
  j.dependencies['@deepseek-ai/dsh-tools'] = WANT.dshTools
  dirty = true
}
j.exports ??= {}
j.exports['.'] ??= {}
if (j.exports['.'].default !== WANT.entryDefault) {
  j.exports['.'].default = WANT.entryDefault
  dirty = true
}
if (dirty) {
  fs.writeFileSync(p, JSON.stringify(j, null, 2) + '\n')
  console.log('==> 已打镜像专属覆盖: dsh-tools ' + WANT.dshTools + ' + exports."." default')
}
// 写后校验：宁可不发布，也不推一个入口解析不了的包
const got = [j.dependencies['@deepseek-ai/dsh-tools'], j.exports['.'].default]
if (JSON.stringify(got) !== JSON.stringify([WANT.dshTools, WANT.entryDefault])) {
  console.error('❌ 镜像专属覆盖未生效: ' + JSON.stringify(got))
  process.exit(1)
}
MIRROR_OVERRIDES

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
