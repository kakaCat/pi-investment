#!/usr/bin/env bash
# url.sh —— 打印 :13080 上「当前运行实例」的可用登录 URL
#
# 为什么需要它：
#   dsh web 的 URL token 是**进程级**的，每次重启换一个；而 launchd 的 stdout 日志
#   是追加写的，同一个文件里积了几十个历史 token（实测 105 个）。肉眼从日志里
#   tail 出来的那个往往属于已经死掉的进程 —— 打开就是 401。
#
#   本脚本不猜：先读活进程 **自己的 stdout 文件**取最后一个 token，再用 HTTP 实测，
#   失败就回退到「扫全部候选、逐个实测」。实测通过的才打印。
#
# 用法：
#   ./url.sh                  # 打印可用 URL
#   ./url.sh --open           # 打印并打开默认浏览器
#   ./url.sh --quiet          # 只输出 URL（给脚本用）
#   ./url.sh --port 13081     # 指定端口
#
# 提示：cookie 有效期 30 天且跨重启有效。用下面的 URL 打开一次之后，
#       书签请改存**裸地址** http://127.0.0.1:13080/ —— 从此不必再管 token。
#       地址要固定用 127.0.0.1：cookie 绑定 authority，localhost / 局域网 IP
#       各自独立（局域网 IP 还会被 /api 的 browser-trust 围栏挡成 403）。

set -uo pipefail

PORT=13080
HOST="${DSH_URL_HOST:-127.0.0.1}"
DO_OPEN=0
QUIET=0

while [ $# -gt 0 ]; do
  case "$1" in
    --open)  DO_OPEN=1; shift ;;
    --quiet) QUIET=1; shift ;;
    --port)  PORT="${2:?--port 需要一个端口号}"; shift 2 ;;
    -h|--help) sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数: $1（用 --help 看用法）" >&2; exit 2 ;;
  esac
done

say() { [ "$QUIET" = 1 ] || echo "$@" >&2; }

BASE="http://${HOST}:${PORT}"

# ── 1. 谁在监听这个端口 ────────────────────────────────────────────
PID="$(lsof -ti:"$PORT" -sTCP:LISTEN 2>/dev/null | head -1)"
if [ -z "$PID" ]; then
  echo "错误: :$PORT 上没有监听进程（服务没起？./start.sh 或 launchctl kickstart -k）" >&2
  exit 1
fi
say "监听进程: pid=$PID  $(ps -o command= -p "$PID" | cut -c1-90)"

# ── 2. 取这个进程自己的 stdout 文件（token 就印在里面） ────────────
SELF_LOG="$(lsof -p "$PID" -a -d 1 -Fn 2>/dev/null | sed -n 's/^n//p' | head -1)"
case "$SELF_LOG" in
  /dev/null|"") SELF_LOG="" ;;
esac
[ -n "$SELF_LOG" ] && say "该进程 stdout: $SELF_LOG"

# ── 3. 收集候选 token（先本进程日志，再退到所有已知日志，去重保序） ──
collect_tokens() { # $1... = 日志文件
  local f
  for f in "$@"; do
    [ -f "$f" ] || continue
    grep -ho 'token=[A-Za-z0-9_-]*' "$f" 2>/dev/null | cut -d= -f2
  done
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${DSH_DATA_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)/.dsh-data}"

CAND=""
[ -n "$SELF_LOG" ] && CAND="$(collect_tokens "$SELF_LOG" | tail -1)"
# 回退/补充：所有已知日志，倒序（新的在后）
ALL_LOG_TOKENS="$(collect_tokens \
  "$DATA_DIR/state/launchd.out.log" \
  "$DATA_DIR/state/launchd.err.log" \
  /tmp/dsh-"$PORT"-restart*.log 2>/dev/null | awk '!seen[$0]++' | tail -r)"

# ── 4. 逐个实测，第一个被接受的即当前 token ────────────────────────
probe() { # $1 = token → 输出 HTTP 状态码
  curl -s -o /dev/null -w '%{http_code}' --max-time 4 "${BASE}/?token=$1" 2>/dev/null
}

LIVE=""
TRIED=0
for t in $CAND $ALL_LOG_TOKENS; do
  [ -z "$t" ] && continue
  TRIED=$((TRIED + 1))
  code="$(probe "$t")"
  # 303 = token 被接受并下发 cookie；200 = 已经有有效 cookie，直接放行
  if [ "$code" = "303" ] || [ "$code" = "200" ]; then LIVE="$t"; break; fi
done

if [ -z "$LIVE" ]; then
  echo "错误: 试了 $TRIED 个候选 token 全被拒绝。" >&2
  echo "      token 只在**进程启动时**打印一次；若刚重启而日志里没有新 token，说明" >&2
  echo "      启动输出去了别处（不是 $DATA_DIR/state/launchd.out.log）。" >&2
  echo "      排查: lsof -p $PID -a -d 1,2 看 stdout/stderr 指向哪个文件。" >&2
  exit 1
fi

URL="${BASE}/?token=${LIVE}"
[ "$QUIET" = 1 ] && echo "$URL" || {
  echo "$URL"
  say ""
  say "已试 $TRIED 个候选（其余 $((TRIED - 1)) 个属于已退出的进程，全部 401）。"
  say "打开一次后，书签请改存裸地址： ${BASE}/"
}

if [ "$DO_OPEN" = 1 ]; then
  say ""
  say "打开浏览器…"
  open "$URL"
fi
