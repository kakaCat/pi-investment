#!/bin/bash
# REQ-81aabd 发版编排 v2：停进程 → 台账 v6→v7 迁移 → 起进程 → 抓设计节点 → 起后复核
#
# v1 为什么中止（2026-09-19 17:21）：v1 停进程只走 launchctl bootout，但本机该作业**根本没被加载**
#   （launchctl print gui/501/com.pi-investment.dsh → Could not find service），于是 bootout 必然
#   "Boot-out failed: 3: No such process"，端口永不释放 → 编排在迁移前安全退出（台账未被动）。
#   现场：现役实例 pid 3956 由交互式登录 shell（login→zsh）拉起，不是 launchd 子进程；
#   launchd.err.log 最后一次写入 10:37（node 3273），manual.out.log 自 10:39 起是现役实例 stdout。
#
# v2 的停/起两路（都留痕）：
#   停：先 bootout（忽略失败——作业在册时会顺手解除托管）→ 端口仍被占则 kill 监听进程（SIGTERM→SIGKILL）
#   起：优先 launchctl bootstrap 恢复文档规定的 KeepAlive 托管；≤40s 未起则回退 detached start.sh
#       （复现 10:39 那次手工启动的形态），两条路都写日志并在结尾标注走的是哪条
#   环境差异已核实：plist 只带 HOME/PATH，但手工实例同样没有 DEEPSEEK_API_KEY（manual.out.log 首行
#   即该警告）→ 凭证来自 .dsh-data 内的凭证库，两条起法都不依赖环境变量；node 在 plist PATH 内
#   （/Users/yunpeng/.local/bin/node → hermes/node/bin/node v22.23.2）
#
# 为什么迁移必须夹在「停与起之间」：
#   JsonLedgerRepository 是 load-once（private loaded，load() 早退）+ 每次 mutate 全量重写
#   （persistAtomic：tmp+fsync+rename），且没有任何 reload API。进程存活期间对台账做外部迁移，
#   会被该进程内存里的旧快照在下一次写入时静默覆盖（2026-09-19 实测：--apply 后文件回到 v6）。
#
# 用法：detached 运行（停机会杀掉旧进程，编排必须脱离该进程组）：
#   python3 -c "import subprocess;subprocess.Popen(['/bin/bash','scripts/req81aabd-restart-and-migrate.sh'],start_new_session=True,stdin=subprocess.DEVNULL,stdout=open('/dev/null','wb'),stderr=subprocess.STDOUT)"
# 日志：.dsh-data/req81aabd-restart.log
set -u
set -o pipefail

REPO=/Users/yunpeng/pi-investment/agent-dh
LOG="$REPO/.dsh-data/req81aabd-restart.log"
LEDGER="$REPO/.dsh-data/dsh-reqboard.json"
DESIGN_OUT="$REPO/.dsh-data/req81aabd-design-stage.json"
MANUAL_LOG="$REPO/.dsh-data/state/manual-start-req81aabd.log"
MIG="packages/pages/dsh-pmboard/scripts/migrate-ledger.ts"
LABEL=com.pi-investment.dsh
DOMAIN="gui/$(id -u)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PORT=13080
SLEEP_BEFORE=${REQ81_SLEEP_BEFORE:-30}

exec >>"$LOG" 2>&1
say() { echo "[$(date '+%H:%M:%S')] $*"; }
port_pid() { lsof -ti:$PORT -sTCP:LISTEN 2>/dev/null | xargs; }
schema_v() { node -e 'const fs=require("fs");process.stdout.write(String(JSON.parse(fs.readFileSync(process.argv[1],"utf8")).schemaVersion))' "$LEDGER"; }
mig() { node --import tsx/esm "$MIG" --file "$LEDGER" "$@" 2>&1 | sed 's/^/      /'; }
req_field() { node -e 'const fs=require("fs");const L=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));const r=(L.requirements||[]).find(x=>x.id==="REQ-81aabd");if(!r){process.stdout.write("(缺)");process.exit(0)};const a=(r.artifacts||[]).filter(x=>String(x.path||"").includes("/design/"));process.stdout.write("status="+r.status+" 设计产物="+a.length+" 条: "+a.map(x=>String(x.path).split("/").pop()+":"+x.stage).join(", "))' "$LEDGER"; }

say "=== REQ-81aabd 发版编排 v2 开始（先等 ${SLEEP_BEFORE}s，让发起会话收尾）==="
sleep "$SLEEP_BEFORE"
cd "$REPO" || { say "!! 进不了 $REPO"; exit 1; }

say "[1/8] 停机前快照"
say "      监听 pid=$(port_pid)（空=未监听）；schemaVersion=$(schema_v)"
if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then say "      launchd 作业在册=yes"; else say "      launchd 作业在册=no（故停/起都要有 kill / start.sh 兜底）"; fi

say "[2/8] 停：先 bootout ${LABEL}（作业不在册时会报 No such process，属预期）"
launchctl bootout "$DOMAIN/$LABEL" 2>&1 | sed 's/^/      /'
for i in $(seq 1 40); do [ -z "$(port_pid)" ] && break; sleep 0.5; done
if [ -n "$(port_pid)" ]; then
  say "      bootout 后端口仍被占（pid $(port_pid)）→ SIGTERM"
  kill $(port_pid) 2>&1 | sed 's/^/      /'
  for i in $(seq 1 40); do [ -z "$(port_pid)" ] && break; sleep 0.5; done
fi
if [ -n "$(port_pid)" ]; then
  say "      SIGTERM 未果 → SIGKILL $(port_pid)"
  kill -9 $(port_pid) 2>&1 | sed 's/^/      /'
  for i in $(seq 1 20); do [ -z "$(port_pid)" ] && break; sleep 0.5; done
fi
if [ -n "$(port_pid)" ]; then say "!! 端口 $PORT 最终未释放（仍有 pid $(port_pid)）——中止迁移以免被覆盖"; exit 1; fi
say "[2/8] 端口 $PORT 已释放，旧进程已停"

say "[3/8] migrate --apply（趁进程不在）"
mig --apply; MIG_APPLY_RC=$?
say "      --apply rc=$MIG_APPLY_RC"
say "[4/8] migrate --verify（停进程期间）"
mig --verify; MIG_VERIFY_RC=$?
say "      --verify rc=${MIG_VERIFY_RC}；schemaVersion(停进程期间)=$(schema_v)"

say "[5/8] 起：优先 launchctl bootstrap ${LABEL}（恢复 KeepAlive 托管）"
START_VIA=none
launchctl bootstrap "$DOMAIN" "$PLIST" 2>&1 | sed 's/^/      /'
for i in $(seq 1 80); do [ -n "$(port_pid)" ] && break; sleep 0.5; done
if [ -n "$(port_pid)" ]; then
  START_VIA=launchd
else
  say "      bootstrap 后 40s 端口未监听 → 回退 detached start.sh（复现手工启动形态）"
  python3 -c "import subprocess;subprocess.Popen(['/bin/bash','$REPO/scripts/start.sh','$PORT'],start_new_session=True,stdin=subprocess.DEVNULL,stdout=open('$MANUAL_LOG','ab'),stderr=subprocess.STDOUT)"
  for i in $(seq 1 120); do [ -n "$(port_pid)" ] && break; sleep 0.5; done
  [ -n "$(port_pid)" ] && START_VIA=manual
fi
say "[5/8] 端口 $PORT 监听=$([ -n "$(port_pid)" ] && echo yes || echo no)（pid $(port_pid)）启动路径=$START_VIA"
launchctl print "$DOMAIN/$LABEL" 2>/dev/null | grep -E '^[[:space:]]+(state|pid) = ' | sed 's/^/      launchd: /'
say "      start.sh 日志尾：$MANUAL_LOG"

say "[6/8] 抓 design 节点数据（GET 会触发新进程的产物自动发现/归类 → 逼它写一次台账）"
HTTP=000
for i in $(seq 1 12); do
  HTTP=$(curl -s -o "$DESIGN_OUT" -w '%{http_code}' "http://127.0.0.1:$PORT/dashboard/api/reqboard/requirements/REQ-81aabd/stage/design")
  if [ "$HTTP" = "200" ] && node -e 'const fs=require("fs");const j=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));const b=(j&&j.data)||j;process.exit(Array.isArray(b.designDocs)?0:1)' "$DESIGN_OUT" 2>/dev/null; then break; fi
  sleep 3
done
say "      HTTP=$HTTP"
node -e '
const fs=require("fs");
try{
  const j=JSON.parse(fs.readFileSync(process.argv[1],"utf8"));
  const b=(j&&j.data)||j;
  const docs=b&&b.designDocs;
  if(!Array.isArray(docs)){console.log("      designDocs 缺失，顶层键=" + Object.keys(b||{}).join(",") + " 原始=" + JSON.stringify(j).slice(0,180));process.exit(0);}
  for(const d of docs) console.log("      " + (d.submitted?"[已交]":"[未交]") + " " + d.path);
}catch(e){console.log("      !! 解析失败：" + e.message);}
' "$DESIGN_OUT"

say "[7/8] 起后复核：新进程是否把迁移覆盖回去（上一步已逼它写过一次盘）"
mig --verify; say "      --verify(起后) rc=$?"
say "      schemaVersion(起后)=$(schema_v)"
say "      REQ-81aabd $(req_field)"
say "[8/8] 编排结束：启动路径=${START_VIA}，迁移 apply rc=${MIG_APPLY_RC} verify rc=${MIG_VERIFY_RC}，design 节点快照=${DESIGN_OUT}"
