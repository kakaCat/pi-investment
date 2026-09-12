# Agent-DH 数据迁移说明

## 迁移概述

原 DSH profile 数据已从 `~/.dsh/profiles/investment/` 迁移到 agent-dh 项目内的 `.dsh-data/` 目录。

## 迁移的数据

### 1. 会话状态数据
- **源目录**: `~/.dsh/profiles/investment/state/`
- **目标目录**: `.dsh-data/state/`
- **内容**: 
  - 会话状态和历史记录
  - 日志文件（launchd.err.log, launchd.out.log）
  - 调度器状态（native-scheduler.json）
  - 重启计数器和恢复状态

### 2. 数据文件
- **源目录**: `~/.dsh/profiles/investment/data/`
- **目标目录**: `.dsh-data/data/`
- **内容**: 应用数据和缓存

### 3. 配置文件
- **agents.json**: Agent 身份和角色配置
  - 投资顾问实例配置
  - agent-dh 工程脑配置
- **dsh.config.yml**: DSH 插件禁用配置

## 目录结构

```
agent-dh/
├── .dsh-data/              # 运行时数据（已迁移）
│   ├── state/              # 会话状态
│   ├── data/               # 数据文件
│   ├── agents.json         # Agent 配置
│   └── dsh.config.yml      # DSH 配置
├── .dsh-home/              # DSH profile（自动生成）
│   └── profiles/agent-dh/
│       ├── state -> ../../.dsh-data/state/  # 符号链接
│       ├── data -> ../../.dsh-data/data/    # 符号链接
│       ├── agents.json     # 启动时复制
│       └── dsh.config.yml  # 启动时复制
└── config/
    └── cordis.yml          # 插件配置
```

## 启动行为

启动脚本 `scripts/start.sh` 会：

1. 创建 `.dsh-home/profiles/agent-dh/` profile 目录
2. 复制 `agents.json` 和 `dsh.config.yml` 到 profile 目录
3. 创建符号链接：
   - `profile/state/` → `.dsh-data/state/`
   - `profile/data/` → `.dsh-data/data/`
4. 所有运行时数据写入 `.dsh-data/`，与 profile 隔离

## 数据持久化

- ✅ `.dsh-data/` 包含所有持久化数据，应该加入版本控制或定期备份
- ✅ `.dsh-home/` 是临时 profile 目录，可以安全删除并重新生成
- ✅ 数据通过符号链接共享，避免重复

## 与原 DSH Profile 的关系

- **原 profile**: `~/.dsh/profiles/investment/`（保留作为备份）
- **新 profile**: 项目内 `.dsh-home/profiles/agent-dh/`
- **数据已迁移**: 可以继续使用原 profile，或完全切换到项目内启动

## 回滚方案

如果需要回滚到原 DSH profile：

```bash
# 停止项目内的 agent-dh
pkill -f "dsh.*agent-dh"

# 使用原 DSH profile 启动
cd ~/.dsh/profiles/investment
./start.sh
```

## 版本控制建议

建议将 `.dsh-data/` 添加到 `.gitignore`（运行时数据），但保留 `agents.json` 的模板版本在 `config/` 目录中。
