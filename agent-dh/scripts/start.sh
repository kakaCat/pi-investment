#!/bin/bash
# Agent-DH 启动脚本（仓库内入口）
# 使用 DeepSeek Harness 框架，但配置在项目内管理。
#
# ── 2026-09-12（w-f9c9a5c1）加固说明 ─────────────────────────────────────────
# 本脚本被定位为 agent-dh 实例的**统一启动入口**，取代散落在仓库外的两份 profile 副本：
#   ~/.dsh/profiles/investment/start.sh          （launchd 作业执行的就是这份）
#   ~/.dsh-agent-dh/profiles/investment/start.sh （自我重启 restarter 拉起的是这份）
# 那两份已经内容分叉（一份有 launchd 互斥段、一份没有；DSH_VERSION 一份读实际值、一份写死
# 0.1.2-alpha.4），且都不在版本控制内。统一到本脚本后，开机自启（launchd）与自我重启
# （lifecycle restarter，经 config.startScript 指定）指向同一入口，不会再各拉一份。
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SELF="$SCRIPT_DIR/$(basename "$0")"

# ── 参数解析 ────────────────────────────────────────────────────────
PORT=13080
FORCE_CONFIG=0
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    --port|-p)
      PORT="$2"
      shift 2
      ;;
    --)
      # pnpm 会把 `pnpm start -- 13081` 的分隔符一并传进来，忽略它
      shift
      ;;
    --force-config)
      # 强制用 config/ 覆盖 profile 配置（缺省只补缺失项，见下方 _ensure_from）
      FORCE_CONFIG=1
      shift
      ;;
    [0-9]*)
      # 纯数字参数视为端口
      PORT="$1"
      shift
      ;;
    *)
      # 其他参数传递给 DSH
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

# ── 环境变量 ────────────────────────────────────────────────────────
if [ -f "$PROJECT_ROOT/.env" ]; then
  echo "加载环境变量: .env"
  export $(cat "$PROJECT_ROOT/.env" | grep -v '^#' | xargs)
fi

if [ -z "$DEEPSEEK_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
  echo "警告: 未设置 DEEPSEEK_API_KEY / OPENAI_API_KEY"
fi

# ── launchd 托管互斥（自 ~/.dsh/profiles/investment/start.sh 移植）──────────────
# 背景（2026-09-11 事故）：launchd 作业 KeepAlive + ThrottleInterval 从"上次拉起"起算，
# 对一个长跑实例等于立即重启。此时 `kill $(lsof -ti:PORT) && ./start.sh` **必然** EADDRINUSE
# ——手工进程抢不到端口，"启动失败"其实是被 launchd 抢回去了。
#
# 规则：当端口由 launchd 作业托管、且该作业执行的**就是本脚本**时，
#   ① 本进程不是 launchd 拉起的 → 把"重启"意图转交 launchctl kickstart -k（先杀后拉，唯一正确入口）
#   ② 本进程就是 launchd 拉起的 → 绝不能再走 kickstart，否则 KeepAlive 下无限重跑（自我重启死循环）
# "我是 launchd 拉起的"用双保险判定：PPID=1（launchd 直接 fork+exec，exec node 不改 PID/PPID）
# 或 launchd 记录的作业 pid == $$。
#
# 作业尚未指向本脚本时（迁移未完成）本段不介入——只走下面的端口占用告警，绝不误接管别人的端口。
LAUNCHD_LABEL="${DSH_LAUNCHD_LABEL:-com.pi-investment.dsh}"
LAUNCHD_PLIST="$HOME/Library/LaunchAgents/$LAUNCHD_LABEL.plist"
LAUNCHD_TARGET="gui/$(id -u)/$LAUNCHD_LABEL"

_launchd_loaded() { launchctl print "$LAUNCHD_TARGET" >/dev/null 2>&1; }
_launchd_job_pid() {
  launchctl print "$LAUNCHD_TARGET" 2>/dev/null \
    | awk -F'= ' '/[[:space:]]pid = /{print $2; exit}' | tr -d '[:space:]'
}
# 作业 ProgramArguments 里的启动脚本路径（判定该作业是否就是本脚本）
_launchd_script() {
  /usr/libexec/PlistBuddy -c "Print :ProgramArguments" "$LAUNCHD_PLIST" 2>/dev/null \
    | awk '/^[[:space:]]+\/.*start\.sh[[:space:]]*$/{gsub(/^[[:space:]]+|[[:space:]]+$/,""); print; exit}'
}
# 作业 ProgramArguments 里第一个纯数字参数 = 托管端口
_launchd_port() {
  local p
  p=$(/usr/libexec/PlistBuddy -c "Print :ProgramArguments" "$LAUNCHD_PLIST" 2>/dev/null \
      | awk '/^[[:space:]]+[0-9]+[[:space:]]*$/{gsub(/[^0-9]/,""); print; exit}')
  printf '%s' "${p:-13080}"
}
_is_launchd_child() {
  if [ "${PPID:-0}" = "1" ]; then
    return 0
  fi
  local jp
  jp="$(_launchd_job_pid)"
  if [ -n "$jp" ] && [ "$jp" = "$$" ]; then
    return 0
  fi
  return 1
}

if _launchd_loaded && [ "$(_launchd_script)" = "$SELF" ]; then
  MANAGED_PORT="$(_launchd_port)"
  if [ "$PORT" = "$MANAGED_PORT" ] && ! _is_launchd_child; then
    echo "注意: :$PORT 由 launchd 作业 $LAUNCHD_LABEL 托管（KeepAlive），且该作业执行的就是本脚本。"
    echo "      手工 bind 会与 launchd 抢端口（必然 EADDRINUSE），已改为请求 launchctl 重启。"
    echo "      如确实要脱离 launchd 手工接管: ./stop.sh   （内部走 launchctl bootout）"
    exec launchctl kickstart -k "$LAUNCHD_TARGET"
  fi
fi

# ── 端口占用预检（比 EADDRINUSE 可读，并吸收"旧进程未释放端口"的竞态）────────────
# 自我重启链路里 restarter 先 SIGTERM 旧进程、再 spawn 本脚本，端口回收可能滞后几秒。
# 故先等最多 20s；仍被占用才退出（此时无论如何也起不来，只是把天书换成可操作的诊断）。
_wait_port_free() {
  local n=0
  while [ "$n" -lt 20 ]; do
    lsof -ti:"$PORT" -sTCP:LISTEN >/dev/null 2>&1 || return 0
    n=$((n + 1))
    sleep 1
  done
  return 1
}
if ! _wait_port_free; then
  # xargs（无命令）= 用 /bin/echo 回显、把换行并成空格；比 tr 少一层转义歧义
  OCCUPIED="$(lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null | xargs)"
  echo "错误: :$PORT 已被占用（pid=${OCCUPIED:-未知}），等待 20s 仍未释放。" >&2
  echo "      换端口: ./start.sh --port 1308X    或先停旧实例: ./stop.sh $PORT" >&2
  if _launchd_loaded && [ "$(_launchd_script)" != "$SELF" ]; then
    echo "      提示: launchd 作业 $LAUNCHD_LABEL 当前执行的是 $(_launchd_script)" >&2
    echo "            （尚未指向本脚本）。要统一入口需把 plist 的 ProgramArguments 改成本脚本。" >&2
  fi
  exit 1
fi

# ── DSH 配置：项目内托管 / 外部 home 两种模式 ──────────────────────────
# 运行身份（profile 名）可配置：默认 agent-dh（项目内 profile）；
# 兼容现役旧布局时由 launchd 显式传 DSH_PROFILE=investment。
DSH_PROFILE="${DSH_PROFILE:-agent-dh}"

# 托管模式（未显式传 DSH_HOME）：用项目内 .dsh-home，本脚本负责生成 profile 脚手架，
#   数据落项目内 .dsh-data。
# 外部模式（显式传了 DSH_HOME 且不是项目内的 .dsh-home，如回滚到旧 home 时）：
#   本脚本**只负责启动**，绝不创建/覆盖/改链那份 home 的任何内容。
#   理由：外部 home 下有 sessions、genome/、dsh-reqboard.json、skills/、attachments/
#   等全部活数据；脚手架里的 rm -rf + 符号链接会把它们静默搬走 = 数据丢失。
#   （2026-09-13 起 launchd 不再传 DSH_HOME，走下面的托管模式。）
if [ -n "${DSH_HOME:-}" ] && [ "$DSH_HOME" != "$PROJECT_ROOT/.dsh-home" ]; then
  MANAGED_HOME=0
else
  MANAGED_HOME=1
  export DSH_HOME="$PROJECT_ROOT/.dsh-home"
fi
mkdir -p "$DSH_HOME"

# 项目内数据/簿记目录：pidfile、以及托管模式下的 sessions/storages 都在这儿（已 gitignore）
export DSH_DATA_DIR="${DSH_DATA_DIR:-$PROJECT_ROOT/.dsh-data}"
mkdir -p "$DSH_DATA_DIR/state"

# 非破坏性目录链接：已是指向同处的符号链接 → 跳过；已是有内容的真实目录 → **拒绝替换**并告警。
# （2026-09-12 立：原实现无条件 rm -rf + ln -s，遇到含 67 项活 state 的真实目录会直接抹掉。）
_link_dir() {  # $1=目标路径  $2=源路径  $3=说明
  local dst="$1" src="$2" label="$3"
  if [ -L "$dst" ]; then
    [ "$(readlink "$dst")" = "$src" ] || \
      echo "  警告: $label 已是指向 $(readlink "$dst") 的符号链接（预期 ${src}），保持不变" >&2
    return 0
  fi
  if [ -e "$dst" ] && [ -n "$(ls -A "$dst" 2>/dev/null)" ]; then
    echo "  警告: $label 是含内容的真实目录（$(ls -A "$dst" | wc -l | tr -d ' ') 项），拒绝替换为符号链接。" >&2
    echo "        如确要迁到项目数据目录，请先人工归档：mv <dst> <dst>.bak-<时间戳> 后再启动。" >&2
    return 0
  fi
  rm -rf "$dst"
  ln -s "$src" "$dst"
}

# 单文件版的非破坏性链接。文件不存在则跳过（不建悬空链接）；已是同处符号链接则跳过；
# 已是有内容的真实文件则**拒绝替换**并告警（与 _link_dir 同一策略，防静默丢数据）。
_link_file() {  # $1=目标路径  $2=源路径  $3=说明
  local dst="$1" src="$2" label="$3"
  [ -e "$src" ] || return 0
  if [ -L "$dst" ]; then
    [ "$(readlink "$dst")" = "$src" ] || \
      echo "  警告: $label 已是指向 $(readlink "$dst") 的符号链接（预期 ${src}），保持不变" >&2
    return 0
  fi
  if [ -e "$dst" ] && [ -s "$dst" ]; then
    echo "  警告: $label 是含内容的真实文件，拒绝替换为符号链接。" >&2
    echo "        如确要迁到项目数据目录，请先人工归档：mv <dst> <dst>.bak-<时间戳> 后再启动。" >&2
    return 0
  fi
  rm -f "$dst"
  ln -s "$src" "$dst"
}

if [ "$MANAGED_HOME" = "1" ]; then
  echo "运行模式: 项目内托管（DSH_HOME=${DSH_HOME} profile=${DSH_PROFILE}）"
  mkdir -p "$DSH_DATA_DIR/data"

  # 在 DSH_HOME 创建配置文件符号链接，让 DSH 读取项目内的配置
  if [ -f "$DSH_DATA_DIR/settings.yaml" ]; then
    ln -sf "$DSH_DATA_DIR/settings.yaml" "$DSH_HOME/settings.yaml"
  fi

  if [ -f "$DSH_DATA_DIR/.credentials.yaml" ]; then
    ln -sf "$DSH_DATA_DIR/.credentials.yaml" "$DSH_HOME/.credentials.yaml"
  fi

  # ── agent preset 分发（2026-09-13 加固）────────────────────────────────
  # 拷入自建 agent preset。仓库 config/agent-presets/ 是**唯一来源**：
  #   investment —— 内置 standard 去掉 delegation 组（内置 standard 含 delegation，
  #                 会因 host 层 modelSelectionSettings 缺失而整体挂载失败）
  #   liangshen  —— 梁神模式（phase1 双工具锚定，晋升后切 PTC Mode）
  # 发现规则（dsh-agent-presets）：preset = $DSH_HOME/.agent-presets/<id>/agent.cordis.yml，
  # **目录名即 id，且只允许 ^[a-z0-9][a-z0-9-]*$**（大写/下划线/点的目录不会被发现）。
  # 缺 preset 不是"降级"而是硬失败：新建会话、恢复记录了该 preset 的老会话都会报
  #   agent-presets: preset "<id>" not found (available: …)
  # （2026-09-13 事故：settings.yaml 的默认 preset 还是 liangshen，而迁移后的
  #   DSH_HOME 里只拷了 investment —— 老会话与新建会话全部 resume failed。）
  # 这里是**拷贝**而非符号链接：改仓库 preset 需重启实例才生效（discovery 在进程内热读
  # 文件，但 DSH_HOME 下这份副本只在启动时刷新）。目标下已有的其它 preset 一律保留。
  if [ -d "$PROJECT_ROOT/config/agent-presets" ]; then
    mkdir -p "$DSH_HOME/.agent-presets"
    for _preset_dir in "$PROJECT_ROOT"/config/agent-presets/*/; do
      [ -d "$_preset_dir" ] || continue
      _preset_src="${_preset_dir%/}"
      _preset_id="$(basename "$_preset_src")"
      if [ ! -f "$_preset_src/agent.cordis.yml" ]; then
        echo "  警告: 仓库 preset ${_preset_id} 缺 agent.cordis.yml，跳过（实例发现不了它）" >&2
        continue
      fi
      # id 合法性：框架只认 ^[a-z0-9][a-z0-9-]*$（大写/下划线/点/前导横线都不行）。
      # 不合法的目录拷了也白拷——discovery 直接不把它当 preset 槽位，而引用它的
      # 会话/默认值会拿到 not-found。这里提前点破，别让"目录明明在"骗过眼睛。
      case "$_preset_id" in
        [!a-z0-9]*|*[!a-z0-9-]*)
          echo "  警告: 仓库 preset 目录名 ${_preset_id} 不是合法 preset id" >&2
          echo "        （只允许小写字母/数字/横线，且首位是字母或数字）——实例永远不会发现它。" >&2
          echo "        处置：改名成合法 id（如 liangshen），并同步改引用它的默认值与老会话。" >&2
          ;;
      esac
      if cp -R "$_preset_src" "$DSH_HOME/.agent-presets/"; then
        echo "  分发 preset: ${_preset_id}"
      else
        echo "  警告: preset ${_preset_id} 拷入 $DSH_HOME/.agent-presets 失败" >&2
      fi
    done

    # 落地校验：实例真正会引用的 preset 是否都在
    #   ① 仓库分发的每一个（上面刚拷）
    #   ② profile 补丁的默认值（config/cordis.yml 的 agent-presets.config.default）
    #   ③ 用户设置的默认值（$DSH_DATA_DIR/settings.yaml 的 agent-presets.default，
    #      优先于 ②；settings 是可写切片，defaultId = settings.default ?? config.default）
    # 缺 = 新建/恢复会话直接 not-found，所以在启动时就喊出来，别等 UI 上报错。
    _yaml_default() {  # $1=文件 $2=awk 程序；文件缺失或解析失败一律静默返回空（不触发 set -e）
      [ -f "$1" ] || return 0
      awk "$2" "$1" 2>/dev/null || true
    }
    _wanted_presets=""
    for _preset_dir in "$PROJECT_ROOT"/config/agent-presets/*/; do
      [ -d "$_preset_dir" ] && _wanted_presets="$_wanted_presets $(basename "${_preset_dir%/}")"
    done
    # settings.yaml：块键在行首，块内取第一个 default:
    _wanted_presets="$_wanted_presets $(_yaml_default "$DSH_DATA_DIR/settings.yaml" '
      /^agent-presets:/{inblock=1; next}
      inblock && /^[^[:space:]]/{inblock=0}
      inblock && /^[[:space:]]+default:/{print $2; exit}')"
    # config/cordis.yml：定位 `- id: agent-presets` 行，取其后的第一个 default:
    _wanted_presets="$_wanted_presets $(_yaml_default "$PROJECT_ROOT/config/cordis.yml" '
      /^- id: agent-presets[[:space:]]*$/{found=1; next}
      found && /^- id: /{exit}
      found && /^[[:space:]]+default:/{print $2; exit}')"
    for _preset_id in $(printf '%s\n' $_wanted_presets | sort -u); do
      if [ ! -f "$DSH_HOME/.agent-presets/${_preset_id}/agent.cordis.yml" ]; then
        echo "  警告: preset \"${_preset_id}\" 被配置引用，但 $DSH_HOME/.agent-presets/ 下没有它。" >&2
        echo "        后果：新建会话、以及恢复记录该 preset 的会话会以" >&2
        echo "              agent-presets: preset \"${_preset_id}\" not found 失败。" >&2
        echo "        处置：把该 preset 放进 config/agent-presets/<id>/ 后重启，" >&2
        echo "              或改 settings.yaml 的 agent-presets.default 指向已有的 preset。" >&2
      fi
    done
  fi

  # 会话与 storages 常驻项目数据目录（.dsh-data），DSH_HOME 内用符号链接指过去。
  # 这样 .dsh-home 被重建时，历史会话与工作区登记不会丢。
  mkdir -p "$DSH_DATA_DIR/sessions" "$DSH_DATA_DIR/storages"
  _link_dir "$DSH_HOME/sessions" "$DSH_DATA_DIR/sessions" "sessions"
  _link_dir "$DSH_HOME/storages" "$DSH_DATA_DIR/storages" "storages"

  # DSH_HOME 顶层其余状态项：插件与框架按 `$DSH_HOME/<名字>` 取数，不挂 = 实例读到空数据。
  #   dsh-reqboard.json —— dsh-pmboard 的台账（LEDGER_FILE，按 DSH_HOME 解析）
  #   skills/ · attachments/ —— skill 根与附件对象库
  #   pet.json —— 实例图标状态
  # （2026-09-13 立：DSH_HOME 迁入项目内时只挂了 sessions/storages，
  #   导致 pmboard 台账在运行实例里消失——数据在 .dsh-data 里，实例却看不见。）
  _link_file "$DSH_HOME/dsh-reqboard.json" "$DSH_DATA_DIR/dsh-reqboard.json" "dsh-reqboard.json"
  _link_file "$DSH_HOME/pet.json"          "$DSH_DATA_DIR/pet.json"          "pet.json"
  _link_dir  "$DSH_HOME/skills"            "$DSH_DATA_DIR/skills"            "skills"
  _link_dir  "$DSH_HOME/attachments"       "$DSH_DATA_DIR/attachments"       "attachments"
else
  echo "运行模式: 外部 DSH_HOME（只启动，不生成 profile 脚手架）: $DSH_HOME"
fi

# 确保 DSH 已安装
DSH_BIN="$PROJECT_ROOT/node_modules/@deepseek-ai/dsh/lib/bin.js"
if [ ! -f "$DSH_BIN" ]; then
  echo "错误: 未找到 @deepseek-ai/dsh，请先运行 pnpm install"
  exit 1
fi

DSH_VERSION=$(node -p "require('$PROJECT_ROOT/node_modules/@deepseek-ai/dsh/package.json').version")

echo "========================================"
echo "  Agent-DH 启动"
echo "========================================"
echo "项目目录: $PROJECT_ROOT"
echo "端口: $PORT"
echo "DSH 版本: $DSH_VERSION"
echo "DSH_HOME: $DSH_HOME"
echo ""

# ── Node 配置 ────────────────────────────────────────────────────────
# 堆内存限制（默认 8GB）
DSH_MAX_OLD_SPACE="${DSH_MAX_OLD_SPACE:-8192}"
export NODE_OPTIONS="--max-old-space-size=${DSH_MAX_OLD_SPACE}${NODE_OPTIONS:+ $NODE_OPTIONS}"

# 设置 NODE_PATH，让 Node.js 能从项目根目录解析模块
export NODE_PATH="$PROJECT_ROOT/node_modules:${NODE_PATH:-}"

# ── 创建 profile 配置 ────────────────────────────────────────────────
# DSH 需要 profile 配置，我们在 DSH_HOME 下创建一个
PROFILE_DIR="$DSH_HOME/profiles/$DSH_PROFILE"
mkdir -p "$PROFILE_DIR"

# 外部 DSH_HOME：profile 配置由人工管理，本脚本不生成、不覆盖
if [ "$MANAGED_HOME" = "1" ]; then

# 2026-09-12 加固：原先每次启动**无条件覆盖** profile 配置（heredoc + cp），于是任何人就地
# 手改（例如启用 lifecycle、调端口）都会在下次启动被静默冲掉——而自我重启链路依赖 profile
# 里的 cordis.patch.yml，丢掉它等于自我重启指向错的插件集合。
# 现在：已存在的一律保留，只有缺失才生成，--force-config 才覆盖（覆盖前先备份）。
_ensure_from() {  # $1=源文件  $2=目标文件  $3=说明
  local src="$1" dst="$2" label="$3"
  if [ ! -e "$dst" ]; then
    cp "$src" "$dst"
    echo "  生成 $label → $dst"
    return 0
  fi
  if [ "$FORCE_CONFIG" = "1" ]; then
    local bak="$dst.bak-$(date +%Y%m%d-%H%M%S)"
    cp "$dst" "$bak"
    cp "$src" "$dst"
    echo "  --force-config: 已备份 $label → $(basename "$bak")，再用 config/ 覆盖"
    return 0
  fi
  echo "  保留已有 $label: $dst"
}

# cordis.yml（profile 根 = 空入口列表，树由 package.json 的 bundles + cordis.patch.yml 组合）
if [ ! -f "$PROFILE_DIR/cordis.yml" ] || [ "$FORCE_CONFIG" = "1" ]; then
  cat > "$PROFILE_DIR/cordis.yml" <<'EOF'
# Agent-DH profile root — an empty entry list. The tree is composed as patches:
# each bundle in package.json's dsh.profile.bundles, then cordis.patch.yml.
[]
EOF
  echo "  生成 cordis.yml"
fi

# cordis.patch.yml（实际插件配置，单一来源是仓库 config/cordis.yml）
if [ -f "$PROJECT_ROOT/config/cordis.yml" ]; then
  _ensure_from "$PROJECT_ROOT/config/cordis.yml" "$PROFILE_DIR/cordis.patch.yml" "cordis.patch.yml"
else
  echo "  警告: 缺少 $PROJECT_ROOT/config/cordis.yml，profile 将没有插件配置" >&2
fi

# agents.json / dsh.config.yml（项目数据目录为单一来源）
if [ -f "$DSH_DATA_DIR/agents.json" ]; then
  _ensure_from "$DSH_DATA_DIR/agents.json" "$PROFILE_DIR/agents.json" "agents.json"
fi

if [ -f "$DSH_DATA_DIR/dsh.config.yml" ]; then
  _ensure_from "$DSH_DATA_DIR/dsh.config.yml" "$PROFILE_DIR/dsh.config.yml" "dsh.config.yml"
fi

# 创建 package.json（DSH profile 需要，包含 bundles 配置）
if [ ! -f "$PROFILE_DIR/package.json" ] || [ "$FORCE_CONFIG" = "1" ]; then
  cat > "$PROFILE_DIR/package.json" <<'EOF'
{
  "name": "agent-dh-profile",
  "private": true,
  "dsh": {
    "profile": {
      "bundles": [
        "@deepseek-ai/dsh-base",
        "@deepseek-ai/dsh-web-app"
      ]
    }
  }
}
EOF
  echo "  生成 package.json"
fi

# 创建 state 目录的符号链接，指向项目数据目录
if [ ! -L "$PROFILE_DIR/state" ]; then
  rm -rf "$PROFILE_DIR/state"
  ln -s "$DSH_DATA_DIR/state" "$PROFILE_DIR/state"
fi

# 创建 data 目录的符号链接
if [ ! -L "$PROFILE_DIR/data" ]; then
  rm -rf "$PROFILE_DIR/data"
  ln -s "$DSH_DATA_DIR/data" "$PROFILE_DIR/data"
fi

fi  # end: MANAGED_HOME=1 的 profile 配置脚手架

# ── 多实例隔离：写 pidfile（exec 保持 PID 不变，$$ 即最终 node 进程 PID）─────────
# 停机只能走 ./stop.sh（pidfile + 端口双重校验）；禁止 pkill -f 模糊匹配（会误杀同机其他实例）。
echo $$ > "$DSH_DATA_DIR/state/server.pid"
echo "$PORT" > "$DSH_DATA_DIR/state/server.port"

# ── 启动 DSH ────────────────────────────────────────────────────────
cd "$PROJECT_ROOT"

# 不使用符号链接，改为在项目根目录直接启动 DSH
# DSH 会从当前目录解析 node_modules
exec node --import tsx/esm "$DSH_BIN" \
  --profile "$DSH_PROFILE" \
  --port "$PORT" \
  "${EXTRA_ARGS[@]}"
