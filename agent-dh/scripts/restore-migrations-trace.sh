#!/bin/bash
# =============================================================================
# 补回台账的 `migrations` 迁移留痕（REQ-260927202051-f6df 验收项②）
#
# 背景（实测）：迁移脚本确实写了 `migrations: [{from:8,to:9,at,by}]`，但
# `JsonLedgerRepository.load()` 只重建 4 个字段 ⇒ 丢掉 `migrations`，而 `mutate` 落盘整个 draft
# ⇒ **新进程启动后的第一次写入就把留痕永久抹掉**（现场：台账顶层键无 migrations，而 manifest 里有）。
# 该 bug 已在源码修好（load 现在原样带过 migrations，并补了往返回归测试），
# 但**已经丢掉的那份留痕需要补一次**——事实依据是迁移脚本自己写的 manifest 文件。
#
# 用法：bash agent-dh/scripts/restore-migrations-trace.sh
# 幂等：已有正确留痕则直接起服务，不改台账。
# =============================================================================
set -uo pipefail

AD="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LED="$AD/.dsh-data/dsh-reqboard.json"
LABEL="${DSH_LAUNCHD_LABEL:-com.pi-investment.dsh}"
TARGET="gui/$(id -u)/$LABEL"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '\033[32m✅ %s\033[0m\n' "$*"; }
die()  { printf '\033[31m❌ %s\033[0m\n' "$*" >&2; exit 1; }

start_service() {
  if launchctl print "$TARGET" >/dev/null 2>&1; then
    launchctl kickstart -k "$TARGET" && return 0
  else
    launchctl bootstrap "gui/$(id -u)" "$PLIST" && return 0
  fi
  "$AD/scripts/start.sh" || return 1
}
trap 'printf "\n\033[33m⚠️  异常退出 —— 兜底拉起服务\033[0m\n"; start_service || true' EXIT

[ -f "$LED" ] || die "台账不存在：$LED"

MAN="$(ls -t "$AD"/.dsh-data/dsh-reqboard.json.migrate-manifest-*.json 2>/dev/null | head -1)"
[ -n "$MAN" ] || die "找不到迁移 manifest（$AD/.dsh-data/dsh-reqboard.json.migrate-manifest-*.json）—— 无事实依据，拒绝凭空写留痕"
say "事实依据（manifest）：$MAN"

say "== 1/4 停机 =="
bash "$AD/scripts/stop.sh" || printf '（stop.sh 返回非 0，继续等端口）\n'
for i in $(seq 1 30); do lsof -ti:13080 -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 1; done
N=$(lsof -ti:13080 -sTCP:LISTEN 2>/dev/null | wc -l | tr -d ' ')
[ "$N" = "0" ] || die "端口 13080 仍有 $N 个监听者 —— 停机未成功；已中止（台账未动）"
ok "已停机"

BK="$LED.pre-trace-$(date +%Y%m%d-%H%M%S)"
cp "$LED" "$BK" && ok "备份 → $BK"

say "== 2/4 从 manifest 补写 migrations 留痕（幂等）=="
node -e '
const fs = require("node:fs");
const [led, man] = process.argv.slice(1);
const m = JSON.parse(fs.readFileSync(man, "utf8"));
const entry = { from: m.from, to: m.to, at: m.at, by: m.by };
if (typeof entry.from !== "number" || typeof entry.to !== "number" || typeof entry.at !== "number") {
  console.error("manifest 里 from/to/at 不完整，拒绝写"); process.exit(1);
}
const l = JSON.parse(fs.readFileSync(led, "utf8"));
l.migrations = Array.isArray(l.migrations) ? l.migrations : [];
const last = l.migrations[l.migrations.length - 1];
if (last && last.from === entry.from && last.to === entry.to) {
  console.log("已存在相同留痕，跳过写入：", JSON.stringify(last));
} else {
  l.migrations.push(entry);
  fs.writeFileSync(led, JSON.stringify(l));
  console.log("已补写：", JSON.stringify(entry));
}
' "$LED" "$MAN" || die "补写失败（台账已被备份，可自行还原 $BK）"

say "== 3/4 复核台账 =="
node -e '
const l = require(process.argv[1]);
console.log("schemaVersion =", l.schemaVersion, "| hasTasks =", ("tasks" in l));
console.log("migrations =", JSON.stringify(l.migrations));
' "$LED" || true

say "== 4/4 起服务 =="
trap - EXIT
start_service || die "起服务失败：手工执行 launchctl bootstrap gui/$(id -u) $PLIST"
for i in $(seq 1 60); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 http://127.0.0.1:13080/ 2>/dev/null || true)
  [ "$code" = "200" ] && { ok ":13080 就绪（http $code，用时 ${i}s）"; break; }
  [ "$code" = "401" ] && { ok ":13080 已就绪（http 401 = 需登录，属正常）"; break; }
  sleep 1
done
ok "完成。台账留痕已补，且新 dist 会把它一直带下去（load 修复已打包）。"
echo "   备份：$BK"
