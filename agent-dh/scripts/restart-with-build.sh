#!/bin/bash
# Agent-DH 发版/重启脚本（校验链接 + 构建全部 dist 包 + 重启 + 四层体检）
# 用法:
#   ./scripts/restart-with-build.sh                完整发版：暂存构建 → 停服 → 原子换装 → 产物校验 → relink → 启动 → 四层体检
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
# 2026-09-16（w-restart-window）：
#   ⑬**构建挪到停服之前 + 暂存换装**。实测（19 包 tsdown 全量 16.5s、页面 client 约 2s、
#      dsh 启动约 14s）：原顺序把停服窗口拉到约 33s，而窗口内浏览器任何一次 /api 读取失败
#      都会在控制台留下一条 "Failed to fetch"（ui-cordis 面板读清单；2026-09-16 排查确认
#      这是纯网络层症状，不是鉴权/协议/插件契约问题）。现改为在**服务仍在运行**时把各包构建到
#      包内暂存目录（全程不碰 dist/），停服后只做 mv 换装（毫秒级），窗口降到约 17s。
#      附带修掉一个失败面：原顺序 bootout 在前，构建失败 = 服务已停 + 各包 dist 新旧混合。
#   ⑭ 暂存构建**不能**用 `pnpm build -- -d <目录>`：pnpm 会把 `--` 原样插进命令行，tsdown 收到
#      `tsdown ... -- -d <目录>` 后把 `-d` 当**位置参数**⇒ 静默忽略、照旧写回 dist/（实测 19 包
#      全报成功、暂存目录为空 —— 而当时的实例正在运行，正是本文档头部警告的就地重建窗口）。
#      故改为从 package.json 读 build 命令、剥掉 tsdown 前缀后用 `pnpm exec tsdown ... -d <暂存>`，
#      并**事后断言暂存目录里确有产物**（把"静默写错地方"变成硬失败）；命令形状不符合
#      （非 tsdown 直调 / 含 shell 元字符）的包回退为原「停服后就地构建」路径，最坏等于改动前。

set -e
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# 项目内托管布局（2026-09-13 起 :13080 的现役布局）：从脚本自身位置反推，不硬编码 home。
# 原来写死 ~/.dsh-agent-dh/profiles/investment —— 切换后那份已是历史副本，本脚本会去
# relink/体检一个没人跑的 home，再用它那份旧 start.sh 去撞 13080 端口。
# 2026-09-14 合并：.dsh-home 已并入 .dsh-data（DSH_HOME 即数据目录），profile 随之下沉；
# profile 名与 start.sh 保持同一规则（DSH_PROFILE，缺省 agent-dh）。
PROFILE_DIR="${DSH_INVESTMENT_PROFILE:-$PROJECT_ROOT/.dsh-data/profiles/${DSH_PROFILE:-agent-dh}}"

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
# ⑬ 暂存换装的记账（供退出钩子清理与回滚）：
#   STAGE_LIST   预构建到暂存的包目录（每行一个）
#   SWAP_LIST    已开始换装的包目录（每行一个；换装前先记账，故"换到一半"也能被还原）
#   INPLACE_LIST 形状不匹配、仍需停服后就地构建的包
STAGE_LIST=""
SWAP_LIST=""
INPLACE_LIST=""
BUILD_LOG=""

# ⑬ 换装/构建中途异常：把"换到一半"的 dist 用保留的旧目录还原，并清掉暂存目录。
# 判定：dist 不存在且 .dist-old-$$ 存在 ⇒ 只 mv 走了一半。
# 注意：本函数在 EXIT 陷阱里跑，任何失败都不能让 set -e 提前终止（否则会跳过后面的服务拉回）。
recover_dist_and_stages() {
  local d
  if [ -n "$SWAP_LIST" ] && [ -f "$SWAP_LIST" ]; then
    while IFS= read -r d; do
      [ -n "$d" ] || continue
      if [ ! -d "$d/dist" ] && [ -d "$d/.dist-old-$$" ]; then
        if mv "$d/.dist-old-$$" "$d/dist" 2>/dev/null; then
          echo "   ↩️ 已还原 $d/dist（换装中断）"
        else
          echo "   ❌ $d/dist 还原失败 —— 旧目录仍在 $d/.dist-old-$$"
        fi
      fi
    done < "$SWAP_LIST"
  fi
  if [ -n "$STAGE_LIST" ] && [ -f "$STAGE_LIST" ]; then
    while IFS= read -r d; do
      [ -n "$d" ] || continue
      rm -rf "$d/.dist-stage-$$"
    done < "$STAGE_LIST"
  fi
  rm -f "$STAGE_LIST" "$SWAP_LIST" "$INPLACE_LIST" "$BUILD_LOG" 2>/dev/null || true
}

# ⑥ H1：bootout 会卸载 launchd 作业（KeepAlive 随之失效），异常退出必须把服务拉回来
restore_service_if_down() {
  local rc=$?
  recover_dist_and_stages
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
echo "  Agent-DH 发版（模式：${MODE}）"
echo "  profile: $PROFILE_DIR"
echo "========================================"

echo "[0/7] 检查工作区..."
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
  echo "❌ 解析出 0 个需构建的 dist 包 —— 无可构建对象不等于通过（检查 PROJECT_ROOT=${PROJECT_ROOT}）"
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

# ── [1/7] 预构建到暂存（服务保持运行）────────────────────────────────────────────
# ⑬ 这一步在**服务仍在运行**时执行，且只写各包的 .dist-stage-$$，全程不碰 dist/。
#    原顺序是"先 bootout 再构建"，于是整个构建期（实测 19 包约 16.5s）都是客户端可见的停机窗口。
BUILD_LOG=$(mktemp -t agent-dh-build.XXXXXX)
STAGE_LIST=$(mktemp -t agent-dh-stage-list.XXXXXX)
SWAP_LIST=$(mktemp -t agent-dh-swap-list.XXXXXX)
INPLACE_LIST=$(mktemp -t agent-dh-inplace-list.XXXXXX)

echo ""
echo "[1/7] 预构建 $DIST_COUNT 个 dist 包到暂存（服务保持运行，不碰 dist/）..."
while IFS=$'\t' read -r dir main; do
  [ -n "$dir" ] || continue
  name=$(basename "$dir")
  if [ ! -f "$dir/package.json" ]; then
    echo "  ⚠️ 跳过 ${name}（无 package.json）"
    continue
  fi
  # ⑭ 只接受 `tsdown <参数>` 这类直调形状（当前 19 包全部如此），才谈得上安全追加 -d。
  build_cmd=$(python3 -c 'import json,sys
try:
    print((json.load(open(sys.argv[1])).get("scripts") or {}).get("build", ""))
except Exception:
    print("")' "$dir/package.json" 2>/dev/null) || build_cmd=""
  case "$build_cmd" in
    tsdown\ *) ;;
    *)
      echo "  ⚠️ ${name}：build 不是 tsdown 直调（'$build_cmd'）—— 该包改在停服后就地构建"
      printf '%s\n' "$dir" >> "$INPLACE_LIST"
      continue
      ;;
  esac
  case "$build_cmd" in
    *'&'*|*'|'*|*';'*|*'<'*|*'>'*|*'$'*|*'`'*|*'*'*)
      echo "  ⚠️ ${name}：build 含 shell 元字符（'$build_cmd'）—— 该包改在停服后就地构建"
      printf '%s\n' "$dir" >> "$INPLACE_LIST"
      continue
      ;;
  esac
  stage="$dir/.dist-stage-$$"
  rm -rf "$stage"
  printf '  → %s\n' "$name"
  # shellcheck disable=SC2086  # ${build_cmd#tsdown } 需要按词拆分（entry 列表 + --dts）
  if ! (cd "$dir" && pnpm exec tsdown ${build_cmd#tsdown } -d "$stage" >"$BUILD_LOG" 2>&1); then
    echo "  ❌ 构建失败：$name"
    tail -20 "$BUILD_LOG" | sed 's/^/      /'
    echo ""
    echo "❌ 预构建失败：$name"
    echo "   ✓ 服务未受影响（此刻尚未停服，dist/ 也从未被改动）"
    exit 1
  fi
  # ⑭ 断言产物确实落在暂存目录 —— 把"tsdown 静默忽略 -d、又写回 dist/"变成硬失败
  if [ ! -f "$stage/$(basename "$main")" ]; then
    echo "  ❌ 暂存目录里没有产物：$stage/$(basename "$main")"
    echo "     tsdown 很可能没接受 -d（见脚本头 ⑭ 的 pnpm 传参坑）—— 拒绝继续"
    exit 1
  fi
  printf '%s\n' "$dir" >> "$STAGE_LIST"
done <<< "$DIST_LIST"
STAGE_N=$(grep -c . "$STAGE_LIST" || true)
INPLACE_N=$(grep -c . "$INPLACE_LIST" || true)
echo "  ✓ 已暂存 ${STAGE_N:-0} 个包；${INPLACE_N:-0} 个待停服后就地构建"

# ── [2/7] 停止服务 ─────────────────────────────────────────────────────────────
if [ "$MODE" = "full" ]; then
  echo ""
  echo "[2/7] 停止 Agent-DH 服务..."
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
  echo "[2/7] 跳过停服（--build-only）"
  echo "  ⚠️  服务保持运行中：接下来的换装只是 mv 重命名（毫秒级），比原来「清空 dist 再写」的窗口小得多；"
  echo "      但若运行中的实例恰好在此瞬间重载插件，仍会报 Cannot find module '.../dist/index.mjs'"
  echo "      （2026-09-12 15:54-15:57 的 15 条 loader 失败即此窗口）。"
  echo "      生产发版请走完整路径（不带 --build-only），它会先停服再换装。"
fi

# ── [3/7] 换装 dist（+ 无法暂存的包就地构建）──────────────────────────────────────
echo ""
echo "[3/7] 换装 dist（暂存 → dist）..."
# 3a 形状不匹配的包：保留原「停服后就地构建 + 逐包备份/失败还原」路径。当前 19 包全可暂存，
#    此分支为空；留着是为了将来出现非 tsdown 构建的包时，发版不至于卡死。
if [ "${INPLACE_N:-0}" -gt 0 ]; then
  DIST_BAK_ROOT=$(mktemp -d -t agent-dh-distbak.XXXXXX)
  FAILED=""
  while IFS= read -r dir; do
    [ -n "$dir" ] || continue
    name=$(basename "$dir")
    if ! grep -q '"build"' "$dir/package.json"; then
      echo "  ⚠️ 跳过 ${name}（无 build 脚本）"
      continue
    fi
    [ -d "$dir/dist" ] && cp -R "$dir/dist" "$DIST_BAK_ROOT/$name" 2>/dev/null || true
    printf '  → %s（就地）\n' "$name"
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
  done < "$INPLACE_LIST"
  if [ -n "$FAILED" ]; then
    echo ""
    echo "❌ 就地构建失败：$FAILED"
    echo "   ⚠️ 服务当前处于已停止状态（第 2 步 bootout 已生效）—— 退出钩子会自动重新拉起；"
    echo "      若上方出现自动恢复失败，请手动：launchctl bootstrap gui/$(id -u) $LAUNCHD_PLIST"
    echo "   失败包 dist 已还原；备份目录：$DIST_BAK_ROOT"
    exit 1
  fi
  rm -rf "$DIST_BAK_ROOT"
fi

# 3b 暂存换装：同目录 mv 重命名（同文件系统，毫秒级）。旧 dist 先改名保留，供校验失败时人工回滚。
if [ "${STAGE_N:-0}" -gt 0 ]; then
  while IFS= read -r dir; do
    [ -n "$dir" ] || continue
    name=$(basename "$dir")
    stage="$dir/.dist-stage-$$"
    if [ ! -d "$stage" ]; then
      echo "  ❌ 暂存目录不存在：$stage —— 拒绝继续（dist/ 未被改动）"
      exit 1
    fi
    printf '%s\n' "$dir" >> "$SWAP_LIST"   # 先记账再 mv：换到一半也能被退出钩子还原
    # 注意：此处不能用 `[ -d x ] && mv`——条件为假时该命令列表返回非 0，set -e 会直接终止脚本
    if [ -d "$dir/dist" ]; then mv "$dir/dist" "$dir/.dist-old-$$"; fi
    mv "$stage" "$dir/dist"
    printf '  ✓ %s\n' "$name"
  done < "$STAGE_LIST"
  echo "  ✓ 已换装 ${STAGE_N} 个包（旧 dist 保留为 .dist-old-$$，产物校验通过后清理）"
fi

# 页面插件的 client bundle（lib/client.js）不在 main→dist 机制内，必须显式构建，
# 否则浏览器会长期加载已提交的旧包（2026-09-15「样式全丢」事故的根因之一）。
# 它留在停机窗口内：lib/client.js 是浏览器直接取的固定路径（包名→路径映射），
# 没法像 dist/ 那样"先构建、再 mv 换装"；5 个包合计约 2s，代价可接受。
echo ""
echo "[4/7] 构建页面插件 client bundle..."
CLIENT_FAILED=""
for pkgdir in "$PROJECT_ROOT"/packages/web/*/; do
  [ -f "$pkgdir/package.json" ] || continue
  if grep -q '"build:client"' "$pkgdir/package.json"; then
    name=$(basename "$pkgdir")
    printf '  → %s\n' "$name"
    if ! (cd "$pkgdir" && pnpm build:client >"$BUILD_LOG" 2>&1); then
      echo "  ❌ client 构建失败：$name"
      tail -20 "$BUILD_LOG" | sed 's/^/      /'
      CLIENT_FAILED="$CLIENT_FAILED $name"
    fi
  fi
done
rm -f "$BUILD_LOG"
if [ -n "$CLIENT_FAILED" ]; then
  echo "❌ client bundle 构建失败：$CLIENT_FAILED —— 拒绝发版（避免旧包被继续供应）"
  exit 1
fi

# ── [5/7] 校验 dist 产物 + profile 链接 ────────────────────────────────────────
echo ""
echo "[5/7] 校验 dist 产物..."
if ! python3 "$SCRIPT_DIR/dist-packages.py" verify "$PROJECT_ROOT"; then
  echo ""
  echo "❌ 产物校验未通过 —— 拒绝以此状态发版（服务已停，退出钩子会拉回）"
  echo "   本次换装前的旧 dist 仍保留在各包 .dist-old-$$，可人工回滚"
  exit 1
fi
# 校验通过 ⇒ 换装前的旧 dist 备份可以清理（未通过时留着供回滚）
if [ "${STAGE_N:-0}" -gt 0 ]; then
  while IFS= read -r dir; do
    if [ -n "$dir" ]; then rm -rf "$dir/.dist-old-$$"; fi
  done < "$SWAP_LIST"
fi

if [ "$MODE" = "full" ]; then
  echo ""
  echo "[5/7] 校验 DSH profile 插件链接..."
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
  echo "[5/7] 跳过 relink（--build-only）"
fi

if [ "$MODE" = "build" ]; then
  echo ""
  echo "[6/7] 跳过启动（--build-only）"
  echo ""
  echo "[7/7] 体检 L1/L2（跳过进程层：服务未重启）..."
  python3 "$SCRIPT_DIR/deploy-verify.py" --profile "$PROFILE_DIR" --port "$PORT" --skip-process || exit 1
  echo ""
  echo "✅ 仅构建完成：$DIST_COUNT 个 dist 包已重建且校验通过（未重启）"
  exit 0
fi

echo ""
echo "[6/7] 启动 Agent-DH 服务..."
if [ "$MANAGED" = "1" ]; then
  launchctl bootstrap "gui/$(id -u)" "$LAUNCHD_PLIST"
else
  # 托管布局的 profile 目录里**没有 start.sh**（只有配置与 state/data 链接），
  # cwd 取 PROJECT_ROOT 与 launchd 拉起的实例一致（config 里 cwd 是 process.cwd()）。
  (cd "$PROJECT_ROOT" && "$SCRIPT_DIR/start.sh" &)
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
echo "[7/7] 发版四层体检..."
if ! python3 "$SCRIPT_DIR/deploy-verify.py" --profile "$PROFILE_DIR" --port "$PORT"; then
  echo ""
  echo "❌ 四层体检未通过 —— 服务虽已启动，但不能判定已加载最新代码"
  echo "   （最常见：L3 进程比产物还老 ⇒ 需要再次发版）"
  exit 1
fi

echo ""
echo "✅ Agent-DH 已发版并通过四层体检"
while read -r lp; do [ -n "$lp" ] && echo "   日志: $lp"; done < <(launchd_log_paths)
