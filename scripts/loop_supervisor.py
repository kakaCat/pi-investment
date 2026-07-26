#!/usr/bin/env python3
"""盈利闭环统一进程 supervisor（2026-07-24）

管理闭环全部 4 进程的生命周期：
  1. v2-api      Flask REST API (:5001)
  2. v2-daemon   scheduler_daemon（orchestrator + WatchEngine 只在这里启动）
  3. agent-dev   agent 主进程（定时决策任务）
  4. agent-wake  agent wake channel (:3002，接收 v2 推送)

用法:
  python3 scripts/loop_supervisor.py start    # 拉起全部并进入监控循环（前台）
  python3 scripts/loop_supervisor.py stop     # 优雅停止全部
  python3 scripts/loop_supervisor.py status   # 查看状态

边界说明：supervisor 解决"进程活着"，不解决笔记本合盖休眠（物理约束）。
唤醒后由 APScheduler misfire 修复 + agent 早盘兜底检查恢复。
"""
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / 'logs' / 'supervisor'
STATUS_FILE = LOG_DIR / 'status.json'

VENV_PY = ROOT / 'quantsys-v2' / 'venv' / 'bin' / 'python'
if not VENV_PY.exists():
    print(f'⚠️  未找到 {VENV_PY}，回退到当前解释器 {sys.executable}')
    VENV_PY = Path(sys.executable)

PROCESSES = [
    {
        'name': 'v2-api',
        'cwd': str(ROOT / 'quantsys-v2'),
        'cmd': [str(VENV_PY), 'adapters/inbound/api/server.py'],
        'health': {'type': 'http', 'url': 'http://127.0.0.1:5001/api/health'},
    },
    {
        'name': 'v2-daemon',
        'cwd': str(ROOT / 'quantsys-v2'),
        'cmd': [str(VENV_PY), 'scheduler_daemon.py'],
        'health': {'type': 'process'},
    },
    {
        'name': 'agent-dev',
        'cwd': str(ROOT / 'agent-ts'),
        'cmd': ['npm', 'run', 'dev'],
        'health': {'type': 'process'},
    },
    {
        'name': 'agent-wake',
        'cwd': str(ROOT / 'agent-ts'),
        'cmd': ['npm', 'run', 'wake'],
        'health': {'type': 'http', 'url': 'http://127.0.0.1:3002/wake/health'},
    },
]

HEALTH_INTERVAL = 30          # 健康检查间隔（秒）
HEALTH_FAIL_THRESHOLD = 3     # 连续失败 N 次才重启
BACKOFF_STEPS = [60, 300, 900]  # 重启退避（秒），封顶 15min
MAX_CONSECUTIVE_RESTARTS = 3  # 连续重启 N 次仍失败 → 告警并放弃该进程


def next_backoff(restart_count: int) -> int:
    """指数退避：1min → 5min → 15min 封顶"""
    idx = min(restart_count - 1, len(BACKOFF_STEPS) - 1)
    return BACKOFF_STEPS[max(idx, 0)]


def should_restart(consecutive_health_failures: int, process_alive: bool) -> bool:
    """进程死了立即重启；健康检查连续失败达阈值才重启"""
    if not process_alive:
        return True
    return consecutive_health_failures >= HEALTH_FAIL_THRESHOLD


def check_http_health(url: str, timeout: int = 5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def alert(message: str):
    """飞书告警（webhook 未配置则只记日志，绝不静默）"""
    line = f'[loop_supervisor] {message}'
    print(f'🚨 {line}', flush=True)
    webhook = os.getenv('FEISHU_WEBHOOK_URL')
    if not webhook:
        return
    try:
        payload = json.dumps({'msg_type': 'text', 'content': {'text': line}}).encode()
        request = urllib.request.Request(
            webhook, data=payload,
            headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(request, timeout=10)
    except Exception as e:
        print(f'⚠️  飞书告警发送失败: {e}', flush=True)


class ProcessGuard:
    """单进程守护：启动、日志重定向、健康检查、重启退避"""

    def __init__(self, config: dict):
        self.cfg = config
        self.name = config['name']
        self.proc: subprocess.Popen | None = None
        self.restart_count = 0
        self.consecutive_restarts = 0
        self.health_failures = 0
        self.gave_up = False
        self.last_restart_at: float = 0
        self.log_path = LOG_DIR / f'{self.name}.log'

    def start(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = open(self.log_path, 'a')
        log_file.write(f'\n===== {datetime.now().isoformat()} start =====\n')
        log_file.flush()
        self.proc = subprocess.Popen(
            self.cfg['cmd'],
            cwd=self.cfg['cwd'],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # 独立进程组，stop 时整组终止
        )
        self.health_failures = 0
        print(f'✅ [{self.name}] 已启动 pid={self.proc.pid}', flush=True)

    def is_alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def check_health(self) -> bool:
        if not self.is_alive():
            return False
        health = self.cfg['health']
        if health['type'] == 'http':
            return check_http_health(health['url'])
        return True  # type == 'process'：活着即健康

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                self.proc.wait(timeout=10)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        self.proc = None

    def maintain(self):
        """每轮监控调用：按需重启（带退避和放弃机制）"""
        if self.gave_up:
            return

        alive = self.is_alive()
        if alive and self.check_health():
            self.health_failures = 0
            self.consecutive_restarts = 0
            return
        self.health_failures = 0 if not alive else self.health_failures + 1

        if not should_restart(self.health_failures, alive):
            return

        # 退避：距上次重启不足 backoff 时间则等待
        backoff = next_backoff(self.consecutive_restarts + 1)
        if time.time() - self.last_restart_at < backoff:
            return

        self.restart_count += 1
        self.consecutive_restarts += 1
        self.last_restart_at = time.time()
        alert(f'{self.name} 异常（存活={alive}, 健康失败={self.health_failures}），'
              f'第 {self.consecutive_restarts} 次重启')
        self.stop()
        self.start()

        if self.consecutive_restarts >= MAX_CONSECUTIVE_RESTARTS:
            self.gave_up = True
            alert(f'{self.name} 连续 {MAX_CONSECUTIVE_RESTARTS} 次重启仍异常，'
                  f'已放弃自动重启，需要人工介入！日志: {self.log_path}')

    def status_dict(self) -> dict:
        return {
            'pid': self.proc.pid if self.is_alive() else None,
            'alive': self.is_alive(),
            'restart_count': self.restart_count,
            'health_failures': self.health_failures,
            'gave_up': self.gave_up,
            'log': str(self.log_path),
        }


def write_status(guards: list):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        'updated_at': datetime.now().isoformat(),
        'processes': {g.name: g.status_dict() for g in guards},
    }
    STATUS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_start():
    guards = [ProcessGuard(cfg) for cfg in PROCESSES]

    # 按依赖序拉起，等待前一个健康再拉下一个
    for g in guards:
        g.start()
        if g.cfg['health']['type'] == 'http':
            for _ in range(30):  # 最多等 30s
                if g.check_health():
                    break
                time.sleep(1)

    print('\n🔄 进入监控循环（Ctrl-C 停止全部进程）\n', flush=True)
    try:
        while True:
            for g in guards:
                g.maintain()
            write_status(guards)
            time.sleep(HEALTH_INTERVAL)
    except KeyboardInterrupt:
        print('\n🛑 收到中断，停止全部进程...', flush=True)
        for g in reversed(guards):
            g.stop()


def cmd_stop():
    if not STATUS_FILE.exists():
        print('无状态文件，supervisor 未在运行')
        return
    data = json.loads(STATUS_FILE.read_text())
    for name, info in data.get('processes', {}).items():
        pid = info.get('pid')
        if pid:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                print(f'✅ 已停止 {name} (pid={pid})')
            except ProcessLookupError:
                print(f'⊙ {name} (pid={pid}) 已不存在')
            except Exception as e:
                print(f'⚠️  停止 {name} 失败: {e}')
    STATUS_FILE.unlink()


def cmd_status():
    if not STATUS_FILE.exists():
        print('supervisor 未在运行（无状态文件）')
        return
    data = json.loads(STATUS_FILE.read_text())
    print(f"更新时间: {data['updated_at']}\n")
    for name, info in data.get('processes', {}).items():
        state = '💀 已放弃' if info['gave_up'] else ('✅ 运行中' if info['alive'] else '❌ 停止')
        print(f"  {name}: {state} pid={info['pid']} 重启{info['restart_count']}次")
        print(f"    日志: {info['log']}")


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if command == 'start':
        cmd_start()
    elif command == 'stop':
        cmd_stop()
    elif command == 'status':
        cmd_status()
    else:
        print(__doc__)
        sys.exit(1)
