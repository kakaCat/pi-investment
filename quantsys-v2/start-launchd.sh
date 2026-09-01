#!/bin/bash
# quantsys-v2 后端启动脚本（launchd 守护用）
cd /Users/yunpeng/pi-investment/quantsys-v2
source ./activate-py313.sh

# ADR-002（2026-09-01）：调度权按执行体拆分——数据任务归 v2 APScheduler 主调度。
# false = v2 APScheduler 接管 31 个业务任务（JobRegistry 全覆盖，已验证）。
# 回退：改回 true 或删除本行，重启即恢复 Agent OS 主调度。
# agent 提醒类任务（agent_turn 等）仍由 Agent OS 管理，待 Phase 2 迁 DSH。
export AGENT_OS_ENABLED=false

exec python adapters/inbound/fastapi_app/main.py

