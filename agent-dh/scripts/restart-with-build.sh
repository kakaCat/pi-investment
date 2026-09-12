#!/bin/bash
# Agent-DH 发版/重启脚本（校验链接 + 构建全部 dist 包 + 重启 + 四层体检）
# 用法:
#   ./scripts/restart-with-build.sh                完整发版：停服 → 构建 → 产物校验 → relink → 启动 → 四层体检
#   ./scripts/restart-with-build.sh --build-only   只构建 + 校验（不停服不重启）
#   ./scripts/restart-with-build.sh --check        只列出需构建的包并体检产物新鲜度（只读）
#   ./scripts/restart-with-build.sh --verify-only  只跑四层体检：依赖/产物/**进程加载新鲜度**/留痕
#
# 2026-09-11 两轮修正：
# ① 原实现 kill + start.sh 在 launchd（KeepAlive）下顺序错：kill 会被 launchd 用**旧代码**
#    立刻拉起，构建发生在之后 ⇒ "编译了但没部署"。正确顺序：bootout → 构建 → bootstrap。
# ② pnpm build 从来就不等于部署：profile 依赖曾被 pnpm 换成硬链接副本，编辑即断链、静默停在
#    旧版本（2026-09-11 全天 RFC 015 工作未生效）。故加入 relink 校验步骤。
#
# 2026-09-12 修正（w-adb088f2，两次实证"部署成功但未生效"）：
# ③ 硬编码只构建两个 client ⇒ 实测 19 个包 main 指向 dist。改为 dist-packages.py 按 main 自动
#    判定 + 产物严格校验。
# ④ tsdown 在 dts 报错（如 TS2742）时会**先清空 dist 再失败** ⇒ 加逐包构建前备份、失败即还原。
# ⑤ **先重启后构建** ⇒ 进程加载旧产物。收尾加入 deploy-verify.py 四层体检，其中 L3 断言
#    「进程启动时间必须晚于所有插件代码 mtime」，违反即失败退出（这才是"是否真加载了最新包"的判据）。
# ⑥ PROFILE_DIR 修正为**真实运行**的 profile（~/.dsh-agent-dh），原值是主实例 :3080 的配置。

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# 真实运行 profile（DSH_HOME=~/.dsh-agent-dh，start.sh 隔离）；可用 DSH_INVESTMENT_PROFILE 覆盖
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

echo "========================================"
echo "  Agent-DH 发版（模式：$MODE）"
echo "  profile: $PROFILE_DIR"
echo "========================================"

echo "[0/6] 检查工作区..."
DIRTY=$(git -C "$PROJECT_ROOT" status --porcelain -- packages/ || true)
if [ -n "$DIRTY" ]; then
  echo "⚠️  packages/ 下有未提交的改动 —— 它们重启后会**直接生效**："
  echo "$DIRTY" | sed 's/^/      /'
  echo ""
fi

if [ "$MODE" = "verify" ]; then
  echo ""
  echo "[verify] 发版四层体检（依赖 / 产物 / 进程加载新鲜度 / 留痕）..."
  python3 "$SCRIPT_DIR/deploy-verify.py" --profile "$PROFILE_DIR" --port "$PORT"
  exit $?
fi

DIST_LIST=$(python3 "$SCRIPT_DIR/dist-packages.py" list "$PROJECT_ROOT" 2>/dev/null | grep -v '^#' || true)
DIST_COUNT=$(printf '%s\n' "$DIST_LIST" | grep -c . || true)
echo "发现 $DIST_COUNT 个包 main 指向 dist/（需构建）"

if [ "$MODE" = "check" ]; then
  echo ""
  echo "[check] 产物新鲜度（只读；git 操作会碰 mtime，故仅作提示）..."
  python3 "$SCRIPT_DIR/dist-packages.py" verify "$PROJECT_ROOT" || true
  echo ""
  echo "提示：正式发版（无参数）会重建全部 $DIST_COUNT 个 dist 包并严格校验。"
  exit 0
fi

MANAGED=0
if [ "$MODE" = "full" ]; then
  echo ""
  echo "[1/6] 停止 Agent-DH 服务..."
  if launchctl print "$LAUNCHD_TARGET" >/dev/null 2>&1; then
    MANAGED=1
    launchctl bootout "$LAUNCHD_TARGET"
    echo "✓ 服务已停止（launchd 作业已卸载）"
  else
    if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
      lsof -ti:"$PORT" -sTCP:LISTEN | xargs kill 2>/dev/null || true
      echo "✓ 服务已停止"
    else
      echo "✓ 服务未运行"
    fi
  fi
  for _ in $(seq 1 40); do
    lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || break
    sleep 0.5
  done
  if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
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
      rm -rf "$dir/dist"
      cp -R "$DIST_BAK_ROOT/$name" "$dir/dist"
      echo "  ↩️ 已从备份还原 $name/dist"
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
  echo "❌ 构建失败：$FAILED（未重启，服务保持原状；失败包 dist 已还原）"
  echo "   dist 备份目录：$DIST_BAK_ROOT"
  echo "   常见原因：tsdown --dts 报 TS2742（static Config 推断类型不可移植；根因常为依赖被装两份）"
  exit 1
fi
rm -rf "$DIST_BAK_ROOT"

echo ""
echo "[3/6] 校验 dist 产物..."
if ! python3 "$SCRIPT_DIR/dist-packages.py" verify "$PROJECT_ROOT"; then
  echo ""
  echo "❌ 产物校验未通过：仍有包产物缺失或落后于源码 —— 拒绝以此状态发版"
  exit 1
fi

if [ "$MODE" = "full" ]; then
  echo ""
  echo "[4/6] 校验 DSH profile 插件链接..."
  if python3 "$SCRIPT_DIR/relink-profile.py" --check --profile "$PROFILE_DIR"; then
    echo "✓ 依赖均为指向仓库的符号链接"
  else
    echo "  发现漂移，正在修复（旧副本备份到 $PROFILE_DIR/.deploy-backup/）..."
    python3 "$SCRIPT_DIR/relink-profile.py" --profile "$PROFILE_DIR"
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
  echo "   如需生效：./scripts/restart-with-build.sh"
  exit 0
fi

echo ""
echo "[5/6] 启动 Agent-DH 服务..."
if [ "$MANAGED" = "1" ]; then
  launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_PLIST"
else
  cd "$PROFILE_DIR"
  ./start.sh &
fi
sleep 3
if ! lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo ""
  echo "❌ 启动失败，请检查日志: $PROFILE_DIR/state/launchd.err.log"
  exit 1
fi

echo ""
echo "[6/6] 发版四层体检..."
if ! python3 "$SCRIPT_DIR/deploy-verify.py" --profile "$PROFILE_DIR" --port "$PORT"; then
  echo ""
  echo "❌ 四层体检未通过 —— 服务虽已启动，但**不能判定已加载最新代码**"
  echo "   （最常见：L3 进程比产物还老 ⇒ 需要再次重启）"
  exit 1
fi

echo ""
echo "✅ Agent-DH 已发版并通过四层体检"
echo "   端口: $PORT   日志: tail -f $PROFILE_DIR/state/launchd.out.log"
