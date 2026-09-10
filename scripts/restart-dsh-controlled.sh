#!/usr/bin/env bash
# 受控重启 DSH（2026-09-11，w-f4aa1f6a）
#
# 背景：本实例此前**不在 launchd 域内**（launchctl print gui/501/com.pi-investment.dsh 报不存在），
# 所以 kickstart -k 返回 113、重启静默失败。本脚本按"kill → bootstrap 交还 launchd 托管 → 校验端口"
# 的顺序重启，失败再直接用 start.sh 兜底；成功后实例重新受 launchd 管理（KeepAlive），后续可 kickstart。
set -uo pipefail

PORT=13080
PLIST=/Users/yunpeng/Library/LaunchAgents/com.pi-investment.dsh.plist
PROFILE=/Users/yunpeng/.dsh/profiles/investment
LOG=$PROFILE/state/restart-w-f4aa1f6a-controlled.log
mkdir -p "$PROFILE/state"
log() { printf '%s | %s\n' "$(date '+%H:%M:%S')" "$*" | tee -a "$LOG"; }

OLD=$(lsof -ti:$PORT -sTCP:LISTEN 2>/dev/null | head -1)
log "=== 受控重启开始，旧 pid=${OLD:-无} ==="

if [ -n "$OLD" ]; then
  kill "$OLD" 2>/dev/null || true
  for n in $(seq 1 20); do
    lsof -ti:$PORT -sTCP:LISTEN >/dev/null 2>&1 || { log "旧实例已退出（${n}×0.5s）"; break; }
    sleep 0.5
  done
  lsof -ti:$PORT -sTCP:LISTEN >/dev/null 2>&1 && { log "旧实例未退出，强杀"; kill -9 "$OLD" 2>/dev/null || true; sleep 2; }
fi

# 交还 launchd 托管（RunAtLoad+KeepAlive），此后 kickstart 可用
launchctl bootout gui/$(id -u)/com.pi-investment.dsh 2>/dev/null || true
if launchctl bootstrap gui/$(id -u) "$PLIST" 2>>"$LOG"; then
  log "bootstrap 成功（launchd 托管）"
else
  log "bootstrap 失败，改用 start.sh 直接拉起"
  nohup bash "$PROFILE/start.sh" $PORT >>"$LOG" 2>&1 &
fi

UP=0
for n in $(seq 1 60); do
  if lsof -ti:$PORT -sTCP:LISTEN >/dev/null 2>&1; then UP=1; log "端口在 ${n}s 内恢复"; break; fi
  sleep 1
done
if [ "$UP" != "1" ]; then
  log "launchd 拉起失败，兜底走 start.sh"
  nohup bash "$PROFILE/start.sh" $PORT >>"$LOG" 2>&1 &
  for n in $(seq 1 60); do
    lsof -ti:$PORT -sTCP:LISTEN >/dev/null 2>&1 && { UP=1; log "兜底成功（${n}s）"; break; }
    sleep 1
  done
fi
NEW=$(lsof -ti:$PORT -sTCP:LISTEN 2>/dev/null | head -1)
log "结果：${UP} 新 pid=${NEW:-无} 堆上限命中=$(ps eww -p "${NEW:-0}" 2>/dev/null | tr ' ' '\n' | grep -c max-old-space-size)"
