#!/bin/bash
# quantsys-v2 WebSocket 启动脚本（launchd 守护用，com.pi-investment.v2-ws）
# 2026-10-20 立：5003 WS 历来无守护、死亡不自动复活（台账：pkg-boundaries §S11-B-1 重启闭环登记）。
# KeepAlive+RunAtLoad 与 v2-api 同型；Agent OS 开关与 v2-api 保持一致（ADR-004）。
cd /Users/yunpeng/pi-investment/quantsys-v2
source ./activate-py313.sh

export AGENT_OS_ENABLED=false
export QUANTSYS_API_HOST=127.0.0.1
export QUANTSYS_WS_PORT=5003

exec python adapters/inbound/fastapi_app/websocket_server.py
