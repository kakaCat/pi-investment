#!/bin/bash
# =============================================================================
# REQ-260927202051-f6df 投产切换：打包 → 备份 → 停机 → 迁移 v8→v9 → 校验 → 起服务
#
# 用法：
#   bash agent-dh/scripts/cutover-queue-v9.sh            # 正常切换
#   bash agent-dh/scripts/cutover-queue-v9.sh --rollback # 回滚到 v8（同样先停机）
#
# 为什么必须在**你自己的终端**里跑（不要交给 agent 进程）：
#   迁移要求服务停机，而 launchctl 只能从**登录用户的 GUI 会话**操作该作业。
#   实测从 agent 进程里调 bootout 无效、bootstrap 报 "Bootstrap failed: 5: Input/output error"
#   —— 此时迁移脚本的服务运行守卫会正确拒绝 --apply，什么都不会发生（安全失败）。
#
# 安全设计：
#   · 每步失败即中止，且**只有停机成功后才动台账**；
#   · 迁移前做二次人工备份；任何异常退出都尝试把服务拉回来（trap）；
#   · 迁移脚本自身：先写全部 queue.json 再改台账（反序会双向丢数据）、白名单校验、幂等。
# =============================================================================
set -uo pipefail

AD="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LED="$AD/.dsh-data/dsh-reqboard.json"
PKG="$AD/packages/web/dsh-pmboard"
LABEL="${DSH_LAUNCHD_LABEL:-com.pi-investment.dsh}"
TARGET="gui/$(id -u)/$LABEL"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
MODE="${1:-apply}"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '\033[32m✅ %s\033[0m\n' "$*"; }
warn() { printf '\033[33m⚠️  %s\033[0m\n' "$*"; }
die()  { printf '\033[31m❌ %s\033[0m\n' "$*" >&2; exit 1; }

[ -f "$LED" ] || die "台账不存在：$LED"
[ -d "$PKG" ] || die "包目录不存在：$PKG"

start_service() {
  if launchctl print "$TARGET" >/dev/null 2>&1; then
    launchctl kickstart -k "$TARGET" && return 0
  else
    launchctl bootstrap "gui/$(id -u)" "$PLIST" && return 0
  fi
  warn "launchctl 起服务失败，回退手工 start.sh"
  "$AD/scripts/start.sh" || return 1
}
# 任何异常退出都尝试把服务拉回来，避免"停了没起"
trap 'warn "异常退出 —— 兜底拉起服务"; start_service || true' EXIT

say "== 0/6 迁移前指纹 =="
md5 -q "$LED"; wc -c < "$LED"
node -e "const l=require('$LED');console.log('schemaVersion='+l.schemaVersion+'  hasTasks='+('tasks' in l))"

BK="$LED.pre-v9-$(date +%Y%m%d-%H%M%S)"
cp "$LED" "$BK" && ok "1/6 二次备份 → $BK"

if [ "$MODE" != "--rollback" ]; then
  say "== 2/6 打包（改源码必须重打包：运行时加载 dist/index.mjs，不是 TS 源码）=="
  ( cd "$PKG" && pnpm build ) || die "打包失败，已中止（服务未动、台账未动）"
  ok "打包完成"
  say "-- 产物新鲜度 + 依赖链接体检（只读）--"
  bash "$AD/scripts/restart-with-build.sh" --check || warn "体检未全绿（不阻断切换，请自行判断）"
fi

say "== 3/6 停机（launchctl bootout；kill 会被 KeepAlive 立刻拉起）=="
bash "$AD/scripts/stop.sh" || warn "stop.sh 返回非 0，继续等端口"
for i in $(seq 1 30); do lsof -ti:13080 -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 1; done
N=$(lsof -ti:13080 -sTCP:LISTEN 2>/dev/null | wc -l | tr -d ' ')
[ "$N" = "0" ] || die "端口 13080 仍有 $N 个监听者 —— 停机未成功；已中止（台账未被触碰）"
ok "已停机"

cd "$PKG" || die "进不了 $PKG"
if [ "$MODE" = "--rollback" ]; then
  say "== 4/6 回滚 --rollback =="
  node --import tsx/esm scripts/migrate-ledger.ts --file "$LED" --root "$AD" --rollback || die "回滚失败"
else
  say "== 4/6 迁移 --apply（先写 51 份 queue.json，再改台账）=="
  node --import tsx/esm scripts/migrate-ledger.ts --file "$LED" --root "$AD" --apply \
    || die "迁移失败：台账未被替换。先看上面输出，必要时 bash $0 --rollback"
  ok "迁移完成"
  say "== 5/6 校验 --verify =="
  node --import tsx/esm scripts/migrate-ledger.ts --file "$LED" --root "$AD" --verify || die "校验失败（队列与台账不一致）"
  node -e "const l=require('$LED');console.log('schemaVersion='+l.schemaVersion+'  hasTasks='+('tasks' in l)+'  末条 migration='+JSON.stringify((l.migrations||[]).slice(-1)))"
  echo "queue.json 份数：$(find "$AD/docs/requirements" -name queue.json 2>/dev/null | wc -l | tr -d ' ')"
fi

say "== 6/6 起服务（加载最新 dist：v9 读方）=="
trap - EXIT
start_service || die "起服务失败：手工执行 launchctl bootstrap gui/$(id -u) $PLIST"
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 http://127.0.0.1:13080/ 2>/dev/null || true)
  [ "$code" = "200" ] && { ok ":13080 就绪（http $code，用时 ${i}s）"; break; }
  sleep 1
done
echo "端口监听者：$(lsof -ti:13080 -sTCP:LISTEN 2>/dev/null | wc -l | tr -d ' ') 个"
ok "完成。刷新 http://127.0.0.1:13080/ 即为新插件。"
echo "   备份：$BK"
echo "   回滚：bash $0 --rollback（同样先停机；备份与 $LED.migrate-manifest-* 不要删）"
