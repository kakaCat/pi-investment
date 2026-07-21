# 六边形架构迁移指南

**适用对象**: quantsys-v2 项目团队成员  
**生效日期**: 2026-06-15  
**Git Commit**: e056a59 (master)

---

## 📋 概述

quantsys-v2 已从混合目录结构重构为标准的**六边形架构（Hexagonal Architecture）**。本指南帮助团队成员快速适应新架构。

## 🔄 导入路径映射表

| 旧路径 | 新路径 |
|--------|--------|
| `from services.*` | `from application.services.*` |
| `from api.*` | `from adapters.inbound.api.*` |
| `from cli.*` | `from adapters.inbound.cli.*` |
| `from repositories.*` | `from adapters.outbound.repositories.*` |
| `from data_sources.*` | `from adapters.outbound.datasources.*` |
| `from brokers.*` | `from domain.brokers.*` |
| `from quantlib.*` | `from domain.quantlib.*` |
| `from strategies.*` | `from domain.strategies.*` |
| `from config.*` | `from infrastructure.config.*` |
| `from infrastructure.database.*` | `from infrastructure.persistence.database.*` |

## 🚀 快速开始

### 启动服务

**API 服务器：**
```bash
python adapters/inbound/api/server.py
```

**CLI 命令：**
```bash
python adapters/inbound/cli/main.py stock search --q 平安
```

## 📂 新架构分层

### domain/ - 领域层
核心业务逻辑：brokers, chan, quantlib, strategies, benchmarks

### application/ - 应用层
用例编排：services

### adapters/ - 适配器层
- **inbound/**: API, CLI
- **outbound/**: Repositories, DataSources

### infrastructure/ - 基础设施层
技术支撑：persistence, cache, events, scheduler, jobs, config

## 🛠️ 常见问题

### Q: 如何更新我的脚本？
```bash
sed -i 's/from services\./from application.services./g' your_script.py
```

### Q: IDE 无法识别导入？
- VSCode: `Cmd+Shift+P` → "Python: Restart Language Server"
- PyCharm: `File` → `Invalidate Caches / Restart`

## 📝 开发指南

### 新增功能放哪里？
- API 接口 → `adapters/inbound/api/routes/`
- CLI 命令 → `adapters/inbound/cli/commands/`
- 业务逻辑 → `application/services/`
- 领域模型 → `domain/`
- 数据访问 → `adapters/outbound/repositories/`

## ✅ 迁移检查清单

- [ ] 已拉取最新 master 分支
- [ ] 已更新脚本导入路径
- [ ] IDE 可正确识别导入
- [ ] 本地测试通过
- [ ] 理解各层职责

---

详见：[六边形架构重构报告](./hexagonal-architecture-refactor-report.md)
