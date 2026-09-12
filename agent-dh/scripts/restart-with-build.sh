#!/bin/bash
# Agent-DH 发版/重启脚本（校验链接 + 构建全部 dist 包 + 重启 + 四层体检）
# 用法:
#   ./scripts/restart-with-build.sh                完整发版：停服 → 构建 → 产物校验 → relink → 启动 → 四层体检
#   ./scripts/restart-with-build.sh --build-only   只构建 + 校验（不停服不重启）
#   ./scripts/restart-with-build.sh --check        只读体检（产物新鲜度 + 依赖链接；异常则退出码 1）
#   ./scripts/restart-with-build.sh --verify-only  只跑四层体检（依赖/产物/进程/留痕）
#
# 2026-09-11：① kill 会被 launchd 用旧代码立刻拉起 ⇒ 改 bootout→构建→bootstrap；
#             ② pnpm build ≠ 部署（硬链接副本会断链）⇒ 加 relink 校验。
# 2026-09-12（w-adb088f2）：③ 构建清单按 main 自动判定（实测 19 包）；④ 逐包备份 dist、失败还原；
#             ⑤ 收尾四层体检（L3 断言进程启动晚于代码）。
# 2026-09-13（w-adb088f2，来自**独立只读审阅**）：
#   ⑥【H1】**停服后任何失败都会把实例留在停止状态，而原文案写"服务保持原状"（假）**。
#      现加 trap：异常退出且端口无监听时自动 bootstrap 拉回，文案改为实情。
#   ⑦【M1】DIST_COUNT=0 直接失败（原来 lister 失败被 2>/dev/null 吞掉 → "什么都没构建"也报成功）。
#   ⑧【M4】--check 透传退出码（原来恒 0，不能当闸门）。
#   ⑨【L1】失败提示的日志路径改为从 plist 读真实路径（原来指向不存在的文件）。
#   ⑩【L2】启动改轮询等待（≤30s），慢启动不再被误报失败而跳过体检。
#   ⑪【L8】脏检查纳入两个顶层 client（它们同样会被构建并直接生效）。
#   ⑫【L9】dist 还原改为"先还原到临时名再原子替换"，并校验 cp 返回码。

set -e
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROFILE_DIR="${DSH_INVESTMENT_PROFILE:-$HOME/.dsh-agent-dh/profiles/investment}"

LAUNCHD_LABEL="com.pi-investment.dsh"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/$LAUNCHD_LABEL.plist"
LAUNCHD_TARGET="gui/$(id -u)/$LAUNCHD_LABEL"
PORT=13080

MODE="full"
case "${1:-}" in
  --check) MODE="check" ;;
  --build-only) MODE="build" ;;
  --verify-only) MODE="verify" ;;
  "") ;;
  -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
  *) echo "❌ 未知参数：$1（可用：--check / --build-only / --verify-only / 无参数）"; exit 2 ;;
esac

port_listening() { lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; }

launchd_log_paths() {
  [ -f "$LAUNCHD_PLIST" ] || return 0
  sed -n 's/.*<key>Standard\(Out\|Error\)Path<\/key>[[:space:]]*<string>\([^<]*\)<\/string>.*/\2/p' "$LAUNCHD_PLIST" 2>/dev/null | head -2
}

MANAGED=0
restored=0
# ⑥ H1：bootout 会卸载 launchd 作业（KeepAlive 随之失效），异常退出必须把服务拉回来
restore_service_if_down() {
  local rc=$?
  if [ "$MANAGED" = "1" ] && [ "$restored" = "0" ] && ! port_listening; then
    restored=1
    echo ""
    echo "↩️ 异常退出且端口 $PORT 无监听 —— 正在重新拉起服务（launchctl bootstrap）..."
    if launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_PLIST" 2>/dev/null; then
      for _ in $(seq 1 60); do port_listening && break; sleep 0.5; done
      if port_listening; then
        echo "   ✓ 服务已恢复（端口 $PORT 已监听）"
      else
        echo "   ❌ 自动恢复失败：请手动执行 launchctl bootstrap gui/$(id -u) $LAUNCHD_PLIST"
      fi
    else
      echo "   ❌ bootstrap 调用失败：请手动执行 launchctl bootstrap gui/$(id -u) $LAUNCHD_PLIST"
    fi
  fi
  exit $rc
}
trap restore_service_if_down EXIT
trap 'echo "⏹️ 收到中断信号"; exit 130' INT TERM

echo "========================================"
echo "  Agent-DH 发版（模式：$MODE）"
echo "  profile: $PROFILE_DIR"
echo "========================================"

echo "[0/6] 检查工作区..."
DIRTY=$(git -C "$PROJECT_ROOT" status --porcelain -- packages/ ../quantsys-v2-client ../agent-os-client 2>/dev/null || true)
if [ -n "$DIRTY" ]; then
  echo "⚠️  有下列未提交改动 —— 会被构建/重启后直接生效："
  echo "$DIRTY" | sed 's/^/      /'
  echo ""
fi

if [ "$MODE" = "verify" ]; then
  echo ""
  echo "[verify] 发版四层体检（依赖 / 产物 / 进程加载新鲜度 / 留痕）..."
  python3 "$SCRIPT_DIR/deploy-verify.py" --profile "$PROFILE_DIR" --port "$PORT"
  exit $?
fi

if ! DIST_LIST=$(python3 "$SCRIPT_DIR/dist-packages.py" list "$PROJECT_ROOT"); then
  echo "❌ 无法解析 dist 包清单（dist-packages.py list 失败）——拒绝继续"
  exit 1
fi
DIST_LIST=$(printf '%s\n' "$DIST_LIST" | grep -v '^#')
DIST_COUNT=$(printf '%s\n' "$DIST_LIST" | grep -c . || true)
if [ "${DIST_COUNT:-0}" -lt 1 ]; then
  echo "❌ 解析出 0 个需构建的 dist 包 —— 无可构建对象不等于通过（检查 PROJECT_ROOT=$PROJECT_ROOT）"
  exit 1
fi
echo "发现 $DIST_COUNT 个包 main 指向 dist/（需构建）"

if [ "$MODE" = "check" ]; then
  echo ""
  echo "[check] 产物新鲜度 + 依赖链接（只读）..."
  rc=0
  python3 "$SCRIPT_DIR/dist-packages.py" verify "$PROJECT_ROOT" || rc=1
  python3 "$SCRIPT_DIR/relink-profile.py" --check --profile "$PROFILE_DIR" || rc=1
  exit $rc
fi

if [ "$MODE" = "full" ]; then
  echo ""
  echo "[1/6] 停止 Agent-DH 服务..."
  if launchctl print "$LAUNCHD_TARGET" >/dev/null 2>&1; then
    MANAGED=1
    launchctl bootout "$LAUNCHD_TARGET"
    echo "✓ 服务已停止（launchd 作业已卸载；异常退出时本脚本会自动拉回）"
  else
    if port_listening; then
      lsof -ti:"$PORT" -sTCP:LISTEN | xargs kill 2>/dev/null || true
      echo "✓ 服务已停止"
    else
      echo "✓ 服务未运行"
    fi
  fi
  for _ in $(seq 1 40); do port_listening || break; sleep 0.5; done
  if port_listening; then
    lsof -ti:"$PORT" -sTCP:LISTEN | xargs kill -9 2>/dev/null || true
    sleep 1
  fi
else
  echo ""
  echo "[1/6] 跳过停服（--build-only）"
fi

echo ""
echo "[2/6] 构建 $DIST_COUNT 个 dist 包..."
BUILD_LOG=$(mktemp -t agent-dh-build.XXXXXX)
DIST_BAK_ROOT=$(mktemp -d -t agent-dh-distbak.XXXXXX)
FAILED=""
while IFS=$'\t' read -r dir main; do
  [ -n "$dir" ] || continue
  name=$(basename "$dir")
  if [ ! -f "$dir/package.json" ]; then
    echo "  ⚠️ 跳过 $name（无 package.json）"
    continue
  fi
  if ! grep -q '"build"' "$dir/package.json"; then
    echo "  ⚠️ 跳过 $name（无 build 脚本），但其 main 指向 $main"
    continue
  fi
  [ -d "$dir/dist" ] && cp -R "$dir/dist" "$DIST_BAK_ROOT/$name" 2>/dev/null || true
  printf '  → %s\n' "$name"
  if ! (cd "$dir" && pnpm build >"$BUILD_LOG" 2>&1); then
    echo "  ❌ 构建失败：$name"
    tail -20 "$BUILD_LOG" | sed 's/^/      /'
    if [ -d "$DIST_BAK_ROOT/$name" ]; then
      TMP_RESTORE="${dir}/.dist-restore-$$"
      if cp -R "$DIST_BAK_ROOT/$name" "$TMP_RESTORE" 2>/dev/null; then
        rm -rf "$dir/dist" && mv "$TMP_RESTORE" "$dir/dist" && echo "  ↩️ 已还原 $name/dist（原子替换）"
      else
        echo "  ❌ $name/dist 还原失败（cp 非 0）—— 备份在 $DIST_BAK_ROOT/$name"
      fi
    else
      echo "  ⚠️ $name 原本没有 dist，无法还原"
    fi
    FAILED="$FAILED $name"
    continue
  fi
done <<< "$DIST_LIST"
rm -f "$BUILD_LOG"
if [ -n "$FAILED" ]; then
  echo ""
  echo "❌ 构建失败：$FAILED"
  echo "   ⚠️ 服务当前处于已停止状态（第 1 步 bootout 已生效）—— 退出钩子会自动重新拉起；"
  echo "      若上方出现自动恢复失败，请手动：launchctl bootstrap gui/$(id -u) $LAUNCHD_PLIST"
  echo "   失败包 dist 已还原；备份目录：$DIST_BAK_ROOT"
  exit 1
fi
rm -rf "$DIST_BAK_ROOT"

echo ""
echo "[3/6] 校验 dist 产物..."
if ! python3 "$SCRIPT_DIR/dist-packages.py" verify "$PROJECT_ROOT"; then
  echo ""
  echo "❌ 产物校验未通过 —— 拒绝以此状态发版（服务已停，退出钩子会拉回）"
  exit 1
fi

if [ "$MODE" = "full" ]; then
  echo ""
  echo "[4/6] 校验 DSH profile 插件链接..."
  if python3 "$SCRIPT_DIR/relink-profile.py" --check --profile "$PROFILE_DIR"; then
    echo "✓ 依赖均为指向仓库的符号链接（且非副本）"
  else
    echo "  发现漂移，正在修复（旧副本备份到 $PROFILE_DIR/.deploy-backup/）..."
    if ! python3 "$SCRIPT_DIR/relink-profile.py" --profile "$PROFILE_DIR"; then
      echo "❌ 修复后仍存在漂移 —— 拒绝以此为基线重启（服务已停，退出钩子会拉回）"
      exit 1
    fi
  fi
else
  echo ""
  echo "[4/6] 跳过 relink（--build-only）"
fi

if [ "$MODE" = "build" ]; then
  echo ""
  echo "[5/6] 体检 L1/L2（跳过进程层：服务未重启）..."
  python3 "$SCRIPT_DIR/deploy-verify.py" --profile "$PROFILE_DIR" --port "$PORT" --skip-process || exit 1
  echo ""
  echo "✅ 仅构建完成：$DIST_COUNT 个 dist 包已重建且校验通过（未重启）"
  exit 0
fi

echo ""
echo "[5/6] 启动 Agent-DH 服务..."
if [ "$MANAGED" = "1" ]; then
  launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_PLIST"
else
  (cd "$PROFILE_DIR" && ./start.sh &)
fi
STARTED_OK=0
for _ in $(seq 1 60); do
  if port_listening; then STARTED_OK=1; break; fi
  sleep 0.5
done
if [ "$STARTED_OK" != "1" ]; then
  echo ""
  echo "❌ 启动失败（等待 30s 端口仍未监听）"
  while read -r lp; do [ -n "$lp" ] && echo "   日志: $lp"; done < <(launchd_log_paths)
  exit 1
fi
restored=1

echo ""
echo "[6/6] 发版四层体检..."
if ! python3 "$SCRIPT_DIR/deploy-verify.py" --profile "$PROFILE_DIR" --port "$PORT"; then
  echo ""
  echo "❌ 四层体检未通过 —— 服务虽已启动，但不能判定已加载最新代码"
  echo "   （最常见：L3 进程比产物还老 ⇒ 需要再次发版）"
  exit 1
fi

echo ""
echo "✅ Agent-DH 已发版并通过四层体检"
while read -r lp; do [ -n "$lp" ] && echo "   日志: $lp"; done < <(launchd_log_paths)
