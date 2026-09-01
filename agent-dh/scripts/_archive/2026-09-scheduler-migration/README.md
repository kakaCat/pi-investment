# 调度迁移退役脚本归档（2026-09-01）

ADR-002 落地后退役的 shell 桥接脚本：

- **os-remind-bridge.sh**（A-1）：Agent OS cron → shell → OS memory 信箱 → lifecycle 轮询的三层桥。
  替代：lifecycle 插件 native-scheduler.ts（DSH 原生 cron + followup 直投），
  Agent OS 侧任务 command 已改 /bin/true 无害化，payload.executor='dsh-native'。
- **signal-perf-backfill.sh**（A-2）：curl 直连后端回填信号表现。
  替代：v2 SignalPerfBackfillJob（scheduler_tasks id=311，每日 15:45）。
- **signal-perf-verify.sh**（A-3）：一次性验证脚本（含硬编码飞书 webhook）。
  9/3 验证任务已由 dsh-native 接管；webhook 硬编码随本文件退役消除。

保留仅为历史参考。勿再被任何任务引用。
