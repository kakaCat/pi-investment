#!/usr/bin/env python3
"""launchd 入口代理（2026-10-04 立）。

为什么需要它 —— 本机实测：macOS 的 TCC 会把 **~/Documents 下的读取按二进制授权**。
launchd 直接拉 /bin/bash 时被拒：
    shell-init: error retrieving current directory: getcwd: Operation not permitted
    /bin/bash: .../scripts/start.sh: Operation not permitted      （launchctl 里退出码 126）
而 homebrew 的 Python.framework（Python.app）**已获得授权**，且**子进程继承**该授权
（实测：framework python → /bin/bash 子进程可正常读 ~/Documents）。

所以本代理的职责只有三件：framework python 常驻 → 以子进程方式跑 scripts/start.sh
→ 把信号与退出码如实透传，让 launchd 的 KeepAlive 语义保持原样。
"""
import os
import signal
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # agent-dh
SCRIPT = os.path.join(BASE, "scripts", "start.sh")


def main() -> int:
    os.chdir(BASE)
    child = subprocess.Popen(["/bin/bash", SCRIPT], cwd=BASE)

    def forward(sig, _frame):
        try:
            child.send_signal(sig)
        except Exception:
            pass

    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, forward)
    return child.wait()


if __name__ == "__main__":
    sys.exit(main())
