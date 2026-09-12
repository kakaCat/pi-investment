#!/bin/bash
# Agent-DH 发版/重启脚本（校验插件链接 + 构建全部 dist 包 + 重启）
# 用法:
#   ./scripts/restart-with-build.sh                完整发版：停服 → 构建 → 校验产物 → relink → 启动 → 健康检查
#   ./scripts/restart-with-build.sh --build-only   只构建 + 校验产物（不停服不重启，用于验证/预构建）
#   ./scripts/restart-with-build.sh --check        只列出需构建的包并校验产物新鲜度（只读）
#
# 2026-09-11 两轮修正：
#
# ① 原实现 `lsof -ti:13080 | xargs kill -9` + `./start.sh &` 在 launchd 托管
#    （KeepAlive）下有两处错：kill 只触发 launchd 立刻重生（ThrottleInterval 从"上次
#    拉起"起算），旧实例被杀的瞬间新实例已经起来，后续 start 必然 EADDRINUSE；更要命
#    的是顺序错了 —— kill 之后 launchd 立刻用**旧代码**把服务拉起来，构建发生在之后，
#    等于"编译了但没部署"。正确顺序：bootout（真正停）→ 构建 → bootstrap（再拉起）。
#    另：`lsof -ti:13080` 缺 -sTCP:LISTEN，会把持有连接的浏览器进程也算进来（stop.sh 铁律②）。
#
# ② `pnpm build` 从来就不等于部署。profile 的插件依赖由 pnpm 装成**硬链接副本**，
#    文件一旦被编辑就断链、静默停在旧版本（2026-09-11 事故：全天 RFC 015 工作全部没生效）。
#    本脚本的 relink 步骤把依赖统一成指向仓库的符号链接。
#
# 2026-09-12 修正（w-adb088f2，实证事故）：
#
# ③ 原脚本**硬编码只构建两个 client 包**，注释还断言"其余包 tsx 直载 TS，无需构建"——
#    与事实不符：实测有 **19 个包**的 package.json main 指向 ./dist/index.mjs
#    （investment / genome / lifecycle / risk / intelligence / data-manager …）。
#    后果：只改 src 不构建 ⇒ 重启后仍是旧代码，且**没有任何报错**。当天 5 项修复里
#    有 3 项就是因此静默未生效。
#    现在改为 `scripts/dist-packages.py` **按 main 字段自动判定**需构建的包，并在构建后
#    做**产物严格校验**（产物存在 + 不比 src/ 陈旧）——构建成功但产物陈旧同样报错退出。

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROFILE_DIR="$HOME/.dsh/profiles/investment"

LAUNCHD_LABEL="com.pi-investment.dsh"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/$LAUNCHD_LABEL.plist"
LAUNCHD_TARGET="gui/$(id -u)/$LAUNCHD_LABEL"
PORT=13080

MODE="full"
case "${1:-}" in
  --check) MODE="check" ;;
  --build-only) MODE="build" ;;
  "") ;;
  -h|--help)
    sed -n '2,8p' "$0"
    exit 0
    ;;
  *)
    echo "❌ 未知参数：$1（可用：--check / --build-only / 无参数）"
    exit 2
    ;;
esac

echo "========================================"
echo "  Agent-DH 发版（模式：$MODE）"
echo "========================================"

# 0. 前置告警：依赖是符号链接，工作区里**未提交**的改动重启后就会直接上线
echo "[0/5] 检查工作区..."
DIRTY=$(git -C "$PROJECT_ROOT" status --porcelain -- packages/ || true)
if [ -n "$DIRTY" ]; then
  echo "⚠️  packages/ 下有未提交的改动 —— 它们重启后会**直接生效**（依赖是符号链接）："
  echo "$DIRTY" | sed 's/^/      /'
  echo "      如果某个包正在被别的会话改动、不该发布，先把它隔离出去再重启。"
  echo ""
fi

# 需构建的包 = main 指向 dist/ 的包（不再硬编码）
DIST_LIST=$(python3 "$SCRIPT_DIR/dist-packages.py" list "$PROJECT_ROOT" 2>/dev/null | grep -v '^#' || true)
DIST_COUNT=$(printf '%s\n' "$DIST_LIST" | grep -c . || true)
echo "发现 $DIST_COUNT 个包 main 指向 dist/（需构建）"

if [ "$MODE" = "check" ]; then
  echo ""
  echo "[check] 产物新鲜度（只读；git 操作会碰 mtime，故仅作提示）..."
  python3 "$SCRIPT_DIR/dist-packages.py" verify "$PROJECT_ROOT" || true
  echo ""
  echo "提示：正式发版（无参数）会**重建全部 $DIST_COUNT 个 dist 包**并严格校验，无需自行挑选。"
  exit 0
fi

# 1. 停止服务（仅完整发版；托管时必须 bootout，kill 会被 KeepAlive 立刻拉起）
MANAGED=0
if [ "$MODE" = "full" ]; then
  echo ""
  echo "[1/5] 停止 Agent-DH 服务..."
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

  # 等端口真正释放（条件等待，替代拍脑袋 sleep）
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
  echo "[1/5] 跳过停服（--build-only：服务保持运行）"
fi

# 2. 构建全部 dist 包
echo ""
echo "[2/5] 构建 $DIST_COUNT 个 dist 包..."
BUILD_LOG=$(mktemp -t agent-dh-build.XXXXXX)
# 2026-09-12（w-adb088f2）：**构建前逐包备份 dist，失败即还原**。
# 实证事故：tsdown 在 dts 报错（如 TS2742）时会**先清空 dist 再失败**，导致该插件
# 下次重启直接消失。仅"中止发版"不足以保护——必须还原产物。
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
    echo "  ⚠️ 跳过 $name（无 build 脚本），但其 main 指向 $main —— 产物无法由本脚本保证"
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
      echo "  ↩️ 已从备份还原 $name/dist（该包产物未被破坏）"
    else
      echo "  ⚠️ $name 原本没有 dist，无法还原"
    fi
    FAILED="$FAILED $name"
    continue   # 继续构建其余包，最后统一判定
  fi
done <<< "$DIST_LIST"
rm -f "$BUILD_LOG"
if [ -n "$FAILED" ]; then
  echo ""
  echo "❌ 构建失败：$FAILED（未重启，服务保持原状；失败包 dist 已还原）"
  echo "   dist 备份目录：$DIST_BAK_ROOT"
  echo "   常见原因：tsdown --dts 报 TS2742（static Config 推断类型不可移植）"
  echo "   → 修法：给该包的 static Config 加显式类型注解（如 static Config: any = z.object({...})）"
  exit 1
fi
rm -rf "$DIST_BAK_ROOT"

# 3. 产物严格校验（构建后必须全部通过：产物存在 + 不比 src 陈旧）
echo ""
echo "[3/5] 校验 dist 产物..."
if ! python3 "$SCRIPT_DIR/dist-packages.py" verify "$PROJECT_ROOT"; then
  echo ""
  echo "❌ 产物校验未通过：仍有包产物缺失或落后于源码 —— 拒绝以此状态发版"
  echo "   （典型原因：包无 build 脚本、构建被跳过、或构建失败但退出码为 0）"
  exit 1
fi

# 4. 校验并修复 profile 插件链接
if [ "$MODE" = "full" ]; then
  echo ""
  echo "[4/5] 校验 DSH profile 插件链接..."
  if python3 "$SCRIPT_DIR/relink-profile.py" --check; then
    echo "✓ 依赖均为指向仓库的符号链接"
  else
    echo "  发现漂移，正在修复（旧副本备份到 $PROFILE_DIR/.deploy-backup/）..."
    python3 "$SCRIPT_DIR/relink-profile.py"
  fi
else
  echo ""
  echo "[4/5] 跳过 relink（--build-only）"
fi

if [ "$MODE" = "build" ]; then
  echo ""
  echo "✅ 仅构建完成：$DIST_COUNT 个 dist 包已重建且产物校验通过"
  echo "   （未重启；如需生效：./scripts/restart-with-build.sh 或 launchctl kickstart -k $(id -u)/$LAUNCHD_LABEL）"
  exit 0
fi

# 5. 启动服务
echo ""
echo "[5/5] 启动 Agent-DH 服务..."
if [ "$MANAGED" = "1" ]; then
  launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_PLIST"
else
  cd "$PROFILE_DIR"
  ./start.sh &
fi

sleep 3

if lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo ""
  echo "✅ Agent-DH 已重启"
  echo "   端口: $PORT"
  echo "   日志: tail -f $PROFILE_DIR/state/launchd.out.log"
else
  echo ""
  echo "❌ 启动失败，请检查日志: $PROFILE_DIR/state/launchd.err.log"
  exit 1
fi
