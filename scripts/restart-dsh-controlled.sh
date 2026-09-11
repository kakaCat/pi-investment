#!/usr/bin/env bash
# 受控重启 DSH 实例（:13080，launchd label com.pi-investment.dsh）
#
# ── 2026-09-11 重写：修复「重启脚本把实例打死」───────────────────────────────
#
# 旧版做的是「kill 监听进程 → launchctl bootout → bootstrap → 兜底 nohup start.sh」。
# 这三步单独看都合理，叠加起来却让「重启」变成「宕机」，当天 02:xx 与 09:xx 两次事故
# （实例被反复杀死、9 小时不可用）根因就是它：
#
#   ① bootout 拆掉了 KeepAlive 安全网 —— 最致命的一条。bootout 成功后实例已无守护，
#      此时若 bootstrap 失败（label 被并发进程占着必然失败），就再没有任何东西会把它
#      拉起来。旧版把「安全网」当成了「需要清理的障碍」。
#   ② 没有并发锁 —— 单次运行最长 ~130s，而调用方（launchctl submit 建出的 keepalive
#      任务，见下）每 25s 就跑一次，于是多个副本并发抢同一个 launchd label，
#      稳定复现 `Bootstrap failed: 5: Input/output error`。
#   ③ 兜底 `nohup start.sh` 跑在 launchd 的精简 PATH 下（/usr/bin:/bin:/usr/sbin:/sbin），
#      找不到 node → 兜底 100% 失败（日志里的 `node: command not found`）。而它是在
#      **旧实例已经被 kill 掉之后**才执行的，所以每一次兜底失败都等于一次真实宕机。
#
# 现在改用 launchd 原生的原子重启，与 scripts/ops/pi-services.sh 对 v2/web 的既有口径一致：
#
#     launchctl kickstart -k gui/501/com.pi-investment.dsh
#
# kickstart -k 由 launchd 内部完成「杀旧 + 起新」：KeepAlive 与 plist 里的 PATH 全程有效，
# 不存在 label 竞争，也不再需要手动 bootstrap。只有 job 压根不在域里时才 bootstrap 一次。
#
# 防复发安全阀（即使再被 keepalive 任务反复调用，也不会把实例打死）：
#   · 并发锁 —— 同一时刻只允许一个重启在跑，后来者直接退出且**不碰实例**
#   · 先确认重启通道可用再动手 —— 通道不可用就绝不 kill，宁可「没重启」也不要「没实例」
#   · 事后健康检查 —— 端口在听 **且** HTTP 有响应才算成功，否则报错退出（不再静默）
#
# 调用方注意：**不要用 `launchctl submit` 来定时调用本脚本**。submit 建的 job 带
# `properties = keepalive`（`launchctl print` 可见），进程退出后会被无限重跑，
# 于是「重启一次」变成「每 25 秒重启一次」。需要定时就用 plist（StartInterval），
# 需要延时单次就 `nohup bash -c 'sleep N; ...' &`。
#
# 用法：
#   ./restart-dsh-controlled.sh              # 重启
#   ./restart-dsh-controlled.sh --dry-run    # 只打印将要执行的动作，不碰实例
set -uo pipefail

PORT=13080
LABEL=com.pi-investment.dsh
PLIST="/Users/yunpeng/Library/LaunchAgents/$LABEL.plist"
PROFILE=/Users/yunpeng/.dsh/profiles/investment
LOG="$PROFILE/state/restart-dsh.log"
LOCK_DIR="$PROFILE/state/restart-dsh.lock"
GUI="gui/$(id -u)"
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

# launchd 的精简 PATH 里没有 node（本机 node 在 ~/.local/bin → hermes node）。
# 旧版兜底路径就死在这里，故显式补齐。
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

mkdir -p "$PROFILE/state"
log() { printf '%s | %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }

port_pid()  { lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1; }
in_domain() { launchctl print "$GUI/$LABEL" >/dev/null 2>&1; }
# 健康 = 端口在听 且 HTTP 有响应。401 也算活着（页面要 token，但服务确实在答）。
healthy() {
  local pid
  pid=$(port_pid)
  [ -n "$pid" ] || return 1
  curl -s -o /dev/null --max-time 5 "http://127.0.0.1:$PORT/" 2>/dev/null
}

# ── 并发锁：mkdir 是原子的（macOS 自带 bash 3.2 没有 flock）─────────────────
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  OWNER=$(cat "$LOCK_DIR/pid" 2>/dev/null || echo "")
  if [ -n "$OWNER" ] && kill -0 "$OWNER" 2>/dev/null; then
    log "已有重启在进行（pid=${OWNER}），本次直接退出，不碰实例"
    exit 0
  fi
  log "发现陈旧锁（pid=${OWNER:-未知} 已不存在），接管"
  rm -rf "$LOCK_DIR"
  mkdir "$LOCK_DIR" 2>/dev/null || { log "FAIL: 无法取得锁，放弃"; exit 1; }
fi
echo $$ > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT INT TERM

OLD=$(port_pid)
log "=== 受控重启开始，旧 pid=${OLD:-无} dry_run=$DRY_RUN ==="

if [ "$DRY_RUN" = "1" ]; then
  log "[dry-run] job 在域内 = $(in_domain && echo yes || echo no)"
  log "[dry-run] 将执行：launchctl kickstart -k $GUI/$LABEL"
  log "[dry-run] 健康判据：端口 $PORT 在听 + curl http://127.0.0.1:$PORT/ 有响应"
  exit 0
fi

# ── 动手前先确保重启通道可用；通道不可用就绝不 kill（避免制造宕机）──────────
if ! in_domain; then
  log "job 不在 launchd 域内 → 先 bootstrap 交还托管"
  if ! launchctl bootstrap "$GUI" "$PLIST" 2>>"$LOG"; then
    log "FAIL: bootstrap 失败。未 kill 任何进程，实例保持原样（宁可没重启，也不要没实例）"
    exit 1
  fi
  sleep 1
fi

# ── launchd 原生原子重启（替代旧版的 kill + bootout + bootstrap）──────────
if ! launchctl kickstart -k "$GUI/$LABEL" 2>>"$LOG"; then
  log "FAIL: kickstart 失败（job 未加载或被禁用）。未制造额外破坏，请查 launchd.err.log"
  exit 1
fi

# ⚠️ 必须等到「监听者换成另一个 pid」再判健康：kickstart 后旧进程不是瞬间消失，
# 只看端口的话，检查可能在**旧实例**上通过、得出假通过（旧写法实测 2s 就报"恢复"，
# 而那一刻新实例未必已经起来）。postrestart-verify.sh 里记过同一坑，这里同样堵上。
UP=0
for n in $(seq 1 60); do
  CUR=$(port_pid)
  if [ -n "$CUR" ] && [ "$CUR" != "$OLD" ] && healthy; then
    UP=1; log "健康：新实例（pid=${CUR}，已非旧 pid）端口 + HTTP 就绪（${n}s）"; break
  fi
  sleep 1
done

NEW=$(port_pid)
if [ "$UP" = "1" ]; then
  log "结果：OK 新 pid=${NEW:-无} 堆上限=$(ps eww -p "${NEW:-0}" 2>/dev/null | tr ' ' '\n' | grep -o 'max-old-space-size=[0-9]*' | head -1)"
else
  log "FAIL: 60s 内未恢复健康（端口 pid=${NEW:-无}）—— 查 $PROFILE/state/launchd.err.log"
  exit 1
fi
