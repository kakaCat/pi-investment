#!/bin/bash
# dsh-watchdog.sh — DSH 实例（:13080）存活看护
#
# 背景（2026-10-19 诊断，窗口 w-8e45ad2a）：
#   Agent OS 调度器（:8080）全天候运行，但 DSH（:13080）多次在早盘时段不在线，
#   导致 09:00-10:15 的盈利发现类 Agent 任务 webhook 全部 connection refused 静默失败
#   （10-15/10-16/10-19 连续三个交易日）。scheduler_watchdog.py 只盯 v2/os，不盯 DSH。
#
# 行为：
#   - 探活 http://127.0.0.1:13080/（401 也算活——有 HTTP 响应即进程在听）
#   - 端口无响应且 launchd 无 pid  → launchctl kickstart（不带 -k，只拉起不杀）
#   - 端口无响应但 launchd 有 pid  → 进程卡死，kickstart -k 强制重启
#   - 探活正常 → 静默退出
#
# 由 ~/Library/LaunchAgents/com.pi-investment.dsh-watchdog.plist 每 300 秒触发。

set -u
LABEL="com.pi-investment.dsh"
PORT=13080
LOG="/Users/yunpeng/pi-investment/logs/dsh-watchdog.log"
UID_NUM="$(id -u)"

log() { echo "[dsh-watchdog] $(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

# ── 产物一致性巡检（2026-10-21 React #130 事故的第三道防线）────────────────────
# 依赖换版本但前端 dist 没重建时，start.sh 会拒绝启动（第二道防线）。若这里仍按原逻辑
# kickstart，就会变成每 5 分钟一次的"启动失败→拉起→再失败"死循环。所以先查指纹：
#   - 指纹不一致：记录一次（同签名只记一次），本轮不 kickstart，静默等待人工发版；
#   - 指纹缺失（退出码 2）：旧产物，按原逻辑探活/拉起；
#   - 一致：正常探活/拉起。
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP_SCRIPT="${REPO_ROOT}/agent-dh/scripts/verify-artifact-stamp.mjs"
STAMP_STATE="${REPO_ROOT}/agent-dh/.dsh-data/state/artifact-stamp-mismatch"
if [ -f "$STAMP_SCRIPT" ]; then
    stamp_out="$(node "$STAMP_SCRIPT" 2>&1)"
    stamp_rc=$?
    if [ "$stamp_rc" = "1" ]; then
        sig="$(printf '%s' "$stamp_out" | shasum -a 256 | awk '{print $1}')"
        if [ ! -f "$STAMP_STATE" ] || [ "$(cat "$STAMP_STATE" 2>/dev/null)" != "$sig" ]; then
            log "ARTIFACT MISMATCH：前端产物与当前框架版本不一致 —— 不重启（否则 start.sh 会拒绝启动）"
            printf '%s\n' "$stamp_out" | while IFS= read -r line; do log "  $line"; done
            log "  处置：cd ${REPO_ROOT}/agent-dh && ./scripts/restart-with-build.sh"
            printf '%s' "$sig" > "$STAMP_STATE"
        fi
        exit 0
    fi
    [ -f "$STAMP_STATE" ] && rm -f "$STAMP_STATE"
fi

# 探活：任何 HTTP 响应码（含 401）都视为存活；只有连接失败/超时才判定死亡
http_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${PORT}/" 2>/dev/null)"
if [ "$http_code" != "000" ] && [ -n "$http_code" ]; then
    exit 0
fi

# 端口死了，查 launchd 是否认为它有 pid
pid="$(launchctl list 2>/dev/null | awk -v l="$LABEL" '$3==l {print $1}')"

if [ -z "$pid" ] || [ "$pid" = "-" ]; then
    log "端口 ${PORT} 无响应且 launchd 无 pid → kickstart 拉起"
    launchctl kickstart "gui/${UID_NUM}/${LABEL}" 2>&1 | while read -r line; do log "kickstart: $line"; done
else
    log "端口 ${PORT} 无响应但 pid=${pid} 存在（进程卡死）→ kickstart -k 强制重启"
    launchctl kickstart -k "gui/${UID_NUM}/${LABEL}" 2>&1 | while read -r line; do log "kickstart -k: $line"; done
fi

# 60 秒后复核一次并记录结果
sleep 60
http_code2="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${PORT}/" 2>/dev/null)"
if [ "$http_code2" != "000" ] && [ -n "$http_code2" ]; then
    log "复核：已恢复（HTTP ${http_code2}）"
else
    log "复核：仍未恢复（连续两次探活失败），下次运行再试"
fi
