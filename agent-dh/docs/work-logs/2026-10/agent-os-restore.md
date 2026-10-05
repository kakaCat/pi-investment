---
title: agent-os 在本机重建并挂上守护（2026-10-04）
date: 2026-10-04
kind: work-log
related: REQ-261004202231-bb99
tags: [agent-os, deployment, launchd, tcc, memory]
---

# agent-os 本机重建（2026-10-04）

## 为什么做

REQ-261004202231-bb99 把记忆能力迁到 agent 侧时发现：**agent-os 根本没在跑**——
`curl 127.0.0.1:8080/health` 连接失败、无进程、`agent-os/` 下无构建产物。
而 agent-dh 的 4 个记忆工具（`memory_search`/`memory_write`/`experience_write`/`experience_stats`）
一直在刷 `ECONNREFUSED 127.0.0.1:8080` —— 等于长期空转。用户裁定「可以启动 os」，故重建。

## 做了什么（可复现）

1. **装 Go**：`brew install go`（→ go1.27.1 darwin/arm64）。
2. **建库 + 建表**：`createdb agent_os` → `psql -d agent_os -f schema.sql`（11 表）
   → 再按序跑 `migrations/*.sql`（补齐 `tasks.owner`/`tasks.cron`/`tasks.agent_line` 等）。
   ⚠️ **schema.sql 与 migrations 与代码三方漂移**（见下「坑」）。
3. **配置**：新建 **`config.local.yaml`（gitignored）**——`database.user` 由旧机器的 `yunpeng` 改 `mac`，
   `dbname` 指向独立库 `agent_os`（不把 agent-os 的表混进 v2 的 `quant_investment`）。
4. **构建**：`GOPROXY=https://goproxy.cn,direct go build -o bin/agent-os ./cmd/agent-os`
   （`proxy.golang.org` 经本机 7890 代理被拒；goproxy.cn 直连 200）。
5. **守护**：`~/Library/LaunchAgents/com.pi-investment.agent-os.plist`
   → 入口是 **framework Python 代理** `agent-os/bin/launchd_launcher.py`（gitignored），
   由它 spawn `bin/agent-os --config config.local.yaml serve`。
   ⚠️ **为什么不能直接让 launchd 拉 ~/Documents 里的二进制**：本机 TCC 按二进制授权，
   实测 agent-dh 侧直接拉 bash/二进制退出码 126（参见 `scripts/launchd_launcher.py` 的注释）；
   homebrew 的 Python.framework 已授权，子进程继承。
   `RunAtLoad + KeepAlive`；日志落 `agent-os/logs/agent-os.{out,err}.log`。

## 验证（实测）

| 项 | 结果 |
|---|---|
| `GET /health` | `{"status":"ok",...}` |
| 端口 | 8080（HTTP）+ 8081（WebSocket）LISTEN |
| `POST /api/v1/memory` | 201/成功，返回带 `id`/`created_at` 的记录 |
| `GET /api/v1/memory?category=experience&limit=100` | `{memories:[…],total:N}`（**看板 M6 探针用的正是这个形状**） |
| `GET /api/v1/memory/search?q=…` | 命中冒烟记录 |
| 库里 | `memories` 有 1 行冒烟数据（category=experience） |

## 坑（后人照抄）

1. **`agent-os.sh` 硬编码旧机器路径** `/Users/yunpeng/pi-investment/agent-os` —— 本机不可用；
   plist + launcher 是替代路径。
2. **schema 三方漂移**：`schema.sql` 的 `memories` 是「`namespace_id` + `embedding`」形状，
   而 HTTP 层 `internal/repository/memory_web_repository.go` 要的是「`title` + `tags` + `agent_id`」形状
   （`migrations/002_create_memories_tables.sql`）。`CREATE TABLE IF NOT EXISTS` 让后到的那份**静默跳过**。
   本机按**并集**补齐：`title`/`tags`/`agent_id`/`search_vector` 加列 + `namespace_id DROP NOT NULL`。
   正式修法应是 agent-os 自己出一版对账迁移（本次未改 agent-os 源码）。
3. **`tasks` 表同样落后于代码**：缺 `owner`/`cron`/`webhook_url`/`payload`/`timeout`/`retry_count`/`agent_line`，
   服务启动即 `failed to start scheduler`（**退出码 1，launchd KeepAlive 会无限重启**——注意看 err 日志）。
4. **`proxy.golang.org` 不通**时记得 `GOPROXY=https://goproxy.cn,direct`。
