#!/usr/bin/env bash
# 服务日志轮转（2026-09-11 建立，窗口 w-f4aa1f6a / REQ-a42aa4）
#
# 背景：v2 launchd-stdout.log 已涨到 203MB 且无任何轮转机制（agent-os stderr 1.5MB+），
#       单文件无限增长既拖慢巡检读取，也让磁盘处于无预警增长状态。
#
# 策略：先 gzip 归档完整内容，再【就地截断】live 文件（不用 rename）。
#   为什么不能 rename：launchd 持有的 fd 指向 inode，rename 后进程会继续写进归档文件，
#   live 路径永久为空。就地截断下 fd 不变，进程照常写（launchd 以 O_APPEND 打开）。
#   为什么先归档再截断：任何时刻都不存在"内容只在内存里"的窗口，最坏情况是重复归档一次。
#
# 与 error collector 的兼容（agent-os/internal/worker/error_event_worker.go:636）：
#   游标满足 offset > size 时自动回退到末窗口；截断后 size≈0 → 下一轮从 0 重扫新内容，
#   不会漏采也不会重复采（同一行有 fingerprint 去重）。
#
# 用法：MAX_BYTES=67108864 KEEP_DAYS=14 ./rotate-logs.sh   （可用环境变量覆盖）
set -uo pipefail

MAX_BYTES=${MAX_BYTES:-67108864}   # 单文件阈值，默认 64MB
KEEP_DAYS=${KEEP_DAYS:-14}         # 归档保留天数
LOCK_DIR=/tmp/pi-rotate-logs.lock
TS=$(date +%Y%m%d-%H%M%S)

# 目标：服务日志目录 + 重启器日志（DSH 两个 profile 路径都覆盖）
TARGET_DIRS=(
  "/Users/yunpeng/pi-investment/quantsys-v2/logs"
  "/Users/yunpeng/pi-investment/agent-os/logs"
  "/Users/yunpeng/.dsh-agent-dh/profiles/investment/state"
  "/Users/yunpeng/.dsh/profiles/investment/state"
)

# 并发保护：mkdir 原子；陈旧锁（>30min）自动接管
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  if [ -n "$(find "$LOCK_DIR" -maxdepth 0 -mmin +30 2>/dev/null)" ]; then
    echo "[rotate-logs] 接管陈旧锁 $LOCK_DIR"
    rm -rf "$LOCK_DIR"
    mkdir "$LOCK_DIR" 2>/dev/null || { echo "[rotate-logs] 取锁失败，退出"; exit 0; }
  else
    echo "[rotate-logs] 已有轮转在跑（$LOCK_DIR），跳过本轮"
    exit 0
  fi
fi
trap 'rm -rf "$LOCK_DIR"' EXIT

rotated=0
skipped=0
for dir in "${TARGET_DIRS[@]}"; do
  [ -d "$dir" ] || continue
  for f in "$dir"/*.log; do
    [ -f "$f" ] || continue
    size=$(stat -f%z "$f" 2>/dev/null || echo 0)
    if [ "$size" -lt "$MAX_BYTES" ]; then
      skipped=$((skipped + 1))
      continue
    fi
    archive="$f.$TS.gz"
    if gzip -c "$f" > "$archive" 2>/dev/null; then
      : > "$f"   # 就地截断：fd 不变，进程继续写
      rotated=$((rotated + 1))
      printf '[rotate-logs] %s %s -> %s (阈值 %s 字节)\n' \
        "$(basename "$f")" "$size" "$(basename "$archive")" "$MAX_BYTES"
    else
      rm -f "$archive"
      echo "[rotate-logs] 归档失败，保持原文件不截断: $f"
    fi
  done
done

# 归档清理（只删本脚本命名的 *.log.<ts>.gz，绝不触碰 live 文件与 offset 状态文件）
pruned=0
for dir in "${TARGET_DIRS[@]}"; do
  [ -d "$dir" ] || continue
  while IFS= read -r old; do
    [ -n "$old" ] || continue
    rm -f "$old" && pruned=$((pruned + 1))
  done < <(find "$dir" -maxdepth 1 -name '*.log.*.gz' -mtime +"$KEEP_DAYS" 2>/dev/null)
done

echo "[rotate-logs] 完成：轮转 ${rotated} 个，未达阈值 ${skipped} 个，清理归档 ${pruned} 个（保留 ${KEEP_DAYS} 天）"
