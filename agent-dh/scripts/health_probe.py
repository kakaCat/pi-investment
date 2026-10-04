#!/usr/bin/env python3
"""agent-dh 外部存活探针 —— 跑在被监控进程**之外**（launchd 直接拉起），进程死了它照样告警。

判据（默认口径）：
  ① 端口 :13080 有监听
  ② state/server.pid 存在、且该 pid 真的在跑（pidfile 与端口双证，避免"pid 复用"假阳性）
  ③ HTTP GET / 返回 < 500（401 也算活：token 门需要鉴权，不是故障）
附带（只报不判，除非 AGENT_DH_STRICT_LOG=1）：
  ④ 输出日志最近一次写入的年龄 —— 抓"进程在、但已经不干活"

告警：FEISHU_WEBHOOK_URL（读 agent-dh/.env 与 .dsh-data/.env）；**只在状态翻转时发一次**，
      状态存 .dsh-data/state/agent-dh-probe-state.json，避免反复刷屏。
退出码：0=健康，2=不健康（launchctl 列表里一眼可见）。

背景：本系统历史上三次"静默死亡"（盯盘消失一周 / 调度死讯静默 8 天 / 服务停摆 18 天），
      共同点都是监控跑在被监控进程里面。本探针与 v2 的 tools/health_probe.py 同一套路。
"""
import json, os, socket, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # agent-dh
STATE_DIR = os.path.join(BASE, ".dsh-data", "state")
PORT = int(os.environ.get("AGENT_DH_PORT", "13080"))
STRICT_LOG = os.environ.get("AGENT_DH_STRICT_LOG", "0") == "1"
LOG_STALE_MIN = int(os.environ.get("AGENT_DH_LOG_STALE_MIN", "30"))
STATE_FILE = os.path.join(STATE_DIR, "agent-dh-probe-state.json")
LOGS = [os.path.join(STATE_DIR, "launchd.out.log"), os.path.join(STATE_DIR, "agent-dh.stdout.log")]


def load_env():
    """把两个本地 env 层里的键值读进 os.environ（已有的不覆盖）。"""
    for rel in (".env", ".dsh-data/.env"):
        path = os.path.join(BASE, rel)
        if not os.path.exists(path):
            continue
        for line in open(path, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def check_port():
    s = socket.socket()
    s.settimeout(3)
    try:
        s.connect(("127.0.0.1", PORT))
        return True, "port %d: listening" % PORT
    except Exception as e:
        return False, "port %d: %s" % (PORT, type(e).__name__)
    finally:
        s.close()


def check_pid():
    pf = os.path.join(STATE_DIR, "server.pid")
    if not os.path.exists(pf):
        return False, "server.pid: missing"
    try:
        pid = int(open(pf).read().strip())
    except Exception:
        return False, "server.pid: unreadable"
    try:
        os.kill(pid, 0)
        return True, "pid %d: alive" % pid
    except ProcessLookupError:
        return False, "pid %d: gone" % pid
    except PermissionError:
        return True, "pid %d: alive(other-owner)" % pid


def check_http():
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/" % PORT, timeout=5) as r:
            code = r.status
    except urllib.error.HTTPError as e:          # 401/403 = 服务在，只是要鉴权
        code = e.code
    except Exception as e:
        return False, "http: %s" % type(e).__name__
    return code < 500, "http: %d" % code


def log_age_min():
    newest = 0.0
    for p in LOGS:
        if os.path.exists(p):
            newest = max(newest, os.path.getmtime(p))
    return None if newest == 0 else (time.time() - newest) / 60.0


def notify(text):
    url = os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
    if not url:
        return "no webhook configured (FEISHU_WEBHOOK_URL empty)"
    body = json.dumps({"msg_type": "text", "content": {"text": text}}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return "feishu: http %d" % r.status
    except Exception as e:
        return "feishu: %s: %s" % (type(e).__name__, e)


def main():
    load_env()
    checks = [check_port(), check_pid(), check_http()]
    ok = all(c[0] for c in checks)
    age = log_age_min()
    if STRICT_LOG and age is not None and age > LOG_STALE_MIN:
        ok = False
        checks.append((False, "log stale: %.1f min > %d" % (age, LOG_STALE_MIN)))

    ts = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    lines = ["[%s] agent-dh probe:" % ts]
    for c in checks:
        lines.append("  %s %s" % ("OK  " if c[0] else "FAIL", c[1]))
    if age is not None:
        lines.append("  (info) log age %.1f min%s" % (age, "" if age <= LOG_STALE_MIN else "  <- over threshold, info only"))
    report = "\n".join(lines)
    print(report, flush=True)

    prev = {}
    if os.path.exists(STATE_FILE):
        try:
            prev = json.load(open(STATE_FILE))
        except Exception:
            prev = {}
    was_ok = prev.get("ok")
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump({"ok": ok, "at": ts}, open(STATE_FILE, "w"))

    if not ok and was_ok is not False:            # 翻转或首次即失败 -> 告警一次
        r = notify("agent-dh 存活探针判定不健康\n" + report)
        print("  -> alerted: " + r, flush=True)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
