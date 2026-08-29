#!/bin/bash
# quantsys-v2 后端启动脚本（launchd 守护用）
cd /Users/yunpeng/pi-investment/quantsys-v2
source ./activate-py313.sh
exec python adapters/inbound/fastapi_app/main.py
