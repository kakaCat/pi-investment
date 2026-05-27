# PI Investment 项目索引

最后整理日期：2026-05-24

## 入口导航

| 位置 | 说明 |
| --- | --- |
| [README.md](README.md) | 项目总览、启动方式和常用配置 |
| [src/](src/) | TypeScript Agent 核心、工具、服务和脚本 |
| [quant/](quant/) | Python QuantSys 后端和量化核心库 |
| [quantsys-v2/](quantsys-v2/) | 重构后的量化 API、CLI、WebSocket 和业务模块 |
| [web-frontend/](web-frontend/) | Vue 3 前端控制台 |
| [skills/](skills/) | 投资分析、风控、组合复盘等 Agent 技能 |
| [docs/](docs/) | 架构、设计、迁移、测试和报告文档 |
| [scripts/](scripts/) | 项目维护、迁移和验证脚本 |

## 常用命令

```bash
# 根目录 Agent
npm run portfolio
npm run feishu
npm test

# 前端
cd web-frontend
npm run dev
npm run build
npm test

# quantsys-v2 后端
cd quantsys-v2
python api/server.py
python api/server_websocket.py

# quant 后端
cd quant
python api/server.py
```

## 服务端口

| 服务 | 默认地址 | 配置项 |
| --- | --- | --- |
| web-frontend | `http://localhost:3001` | `web-frontend/vite.config.ts` |
| quantsys-v2 HTTP API | `http://127.0.0.1:5001` | `QUANTSYS_API_PORT` |
| quantsys-v2 WebSocket | `ws://127.0.0.1:5003` | `QUANTSYS_WS_PORT` |
| quant API | `http://127.0.0.1:5002` | `QUANT_API_PORT` |

## 文档分区

| 路径 | 内容 |
| --- | --- |
| [docs/reports/](docs/reports/) | 阶段报告、验证报告、修复总结 |
| [docs/reports/2026-05/](docs/reports/2026-05/) | 2026-05 迁移和前端修复报告归档 |
| [docs/superpowers/specs/](docs/superpowers/specs/) | 功能设计文档 |
| [docs/superpowers/plans/](docs/superpowers/plans/) | 实施计划 |
| [docs/api/](docs/api/) | API 相关说明 |
| [docs/design/](docs/design/) | 架构和设计说明 |
| [web-frontend/docs/](web-frontend/docs/) | 前端专项文档 |
| [quant/docs/](quant/docs/) | QuantSys 后端文档 |
| [quantsys-v2/docs/](quantsys-v2/docs/) | QuantSys V2 文档 |

## 本地产物

以下目录主要是运行时数据、测试输出或本地工具产物，默认不作为项目入口：

- `.pi-invest/`
- `.playwright-mcp/`
- `.superpowers/`
- `.venv/`
- `coverage/`
- `htmlcov/`
- `logs/`
- `dist/`
- `web-frontend/dist/`
- `quant-web/dist/`

## 当前整理说明

根目录只保留项目入口文档、脚本和原型文件。2026-05 的临时修复报告已归档到 [docs/reports/2026-05/](docs/reports/2026-05/)。
