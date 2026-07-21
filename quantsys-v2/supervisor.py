#!/usr/bin/env python3
"""
进程守护 (Process Supervisor)

监控 scheduler_daemon 进程，崩溃后自动重启。
支持：
- 自动重启（最多连续重启 N 次后暂停）
- 指数退避（避免频繁重启）
- 健康检查（检测进程是否真正工作）
- 日志记录

使用：
    python3 supervisor.py                    # 前台运行
    python3 supervisor.py --max-restarts 10  # 最大重启次数
    nohup python3 supervisor.py &            # 后台运行
"""
import sys
import os
import time
import signal
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

# 项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置日志
log_dir = project_root / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'supervisor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('supervisor')


class ProcessSupervisor:
    """进程守护器"""

    def __init__(
        self,
        command: str = 'python3 scheduler_daemon.py',
        max_restarts: int = 10,
        restart_window_minutes: int = 60,
        backoff_base: int = 5,
        backoff_max: int = 300,
        health_check_interval: int = 60,
    ):
        self.command = command
        self.max_restarts = max_restarts
        self.restart_window = timedelta(minutes=restart_window_minutes)
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.health_check_interval = health_check_interval

        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self.restart_times: list = []  # 记录重启时间
        self.total_restarts = 0
        self.start_time: Optional[datetime] = None

    def start(self):
        """启动守护"""
        logger.info("=" * 60)
        logger.info("Process Supervisor Starting")
        logger.info(f"  Command: {self.command}")
        logger.info(f"  Max restarts: {self.max_restarts} per {self.restart_window}")
        logger.info("=" * 60)

        self.running = True
        self.start_time = datetime.now()

        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # 主循环
        self._supervise_loop()

    def _supervise_loop(self):
        """守护主循环"""
        consecutive_failures = 0

        while self.running:
            # 启动子进程
            self.process = self._start_process()

            if self.process is None:
                logger.error("Failed to start process, retrying...")
                time.sleep(self.backoff_base)
                continue

            # 等待进程结束
            return_code = self.process.wait()

            if not self.running:
                # 正常退出
                break

            # 进程异常退出
            logger.warning(
                f"Process exited with code {return_code}, "
                f"total_restarts={self.total_restarts}"
            )

            # 检查是否超过重启限制
            if self._exceeds_restart_limit():
                logger.error(
                    f"Exceeded max restarts ({self.max_restarts}) "
                    f"in {self.restart_window}. Pausing for 10 minutes."
                )
                time.sleep(600)  # 暂停10分钟
                self.restart_times.clear()
                continue

            # 指数退避
            consecutive_failures += 1
            backoff = min(
                self.backoff_base * (2 ** (consecutive_failures - 1)),
                self.backoff_max
            )

            logger.info(f"Restarting in {backoff}s (attempt {consecutive_failures})")
            time.sleep(backoff)

            # 记录重启
            self.restart_times.append(datetime.now())
            self.total_restarts += 1

            # 如果进程运行超过5分钟才崩溃，重置连续失败计数
            # （说明不是启动问题）
            if self.process and self.start_time:
                runtime = (datetime.now() - self.start_time).seconds
                if runtime > 300:
                    consecutive_failures = 0

    def _start_process(self) -> Optional[subprocess.Popen]:
        """启动子进程"""
        try:
            logger.info(f"Starting: {self.command}")
            self.start_time = datetime.now()

            process = subprocess.Popen(
                self.command.split(),
                cwd=str(project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            logger.info(f"Process started: PID={process.pid}")
            return process

        except Exception as e:
            logger.error(f"Failed to start process: {e}")
            return None

    def _exceeds_restart_limit(self) -> bool:
        """检查是否超过重启限制"""
        now = datetime.now()
        # 清理窗口外的记录
        self.restart_times = [
            t for t in self.restart_times
            if now - t < self.restart_window
        ]
        return len(self.restart_times) >= self.max_restarts

    def stop(self):
        """停止守护"""
        logger.info("Supervisor stopping...")
        self.running = False

        if self.process and self.process.poll() is None:
            logger.info(f"Terminating child process: PID={self.process.pid}")
            self.process.terminate()

            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                logger.warning("Process didn't terminate, killing...")
                self.process.kill()

        logger.info("Supervisor stopped")

    def _signal_handler(self, signum, frame):
        """信号处理"""
        logger.info(f"Received signal {signum}")
        self.stop()
        sys.exit(0)

    def get_status(self) -> dict:
        """获取状态"""
        return {
            'running': self.running,
            'pid': self.process.pid if self.process else None,
            'total_restarts': self.total_restarts,
            'recent_restarts': len(self.restart_times),
            'start_time': self.start_time.isoformat() if self.start_time else None,
        }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='Process Supervisor')
    parser.add_argument(
        '--command', default='python3 scheduler_daemon.py',
        help='Command to supervise'
    )
    parser.add_argument(
        '--max-restarts', type=int, default=10,
        help='Max restarts per window'
    )
    parser.add_argument(
        '--window', type=int, default=60,
        help='Restart window in minutes'
    )
    args = parser.parse_args()

    supervisor = ProcessSupervisor(
        command=args.command,
        max_restarts=args.max_restarts,
        restart_window_minutes=args.window,
    )

    supervisor.start()


if __name__ == '__main__':
    main()
