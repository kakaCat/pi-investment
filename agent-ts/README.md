# PI Investment - AI 投资顾问

面向 A 股/港股投研和量化交易的本地工作区。项目当前由三部分组成：TypeScript Agent 核心、Python 量化后端、Vue 前端控制台。

## 当前入口

| 模块 | 路径 | 主要用途 |
| --- | --- | --- |
| Agent 核心 | `src/` | 投资助手、工具调用、组合管理、飞书集成 |
| 量化后端 | `quantsys-v2/` | v2 API/CLI/WebSocket 和新量化架构 |
| 前端控制台 | `web-frontend/` | Vue 3 + Vite 量化交易系统前端 |
| 技能文件 | `skills/` | Agent 投研流程和领域知识 |
| 文档 | `docs/` | 架构、迁移、报告、设计和计划 |

`quant-web/` 是旧前端目录，当前主要前端入口是 `web-frontend/`。

## 架构概览

```text
pi-investment/
├── src/                 # TypeScript Agent 核心和工具适配层
├── quantsys-v2/         # Python 量化后端，HTTP 端口 5001，WebSocket 端口 5003
├── web-frontend/        # Vue 3 前端，Vite 开发端口 3001
├── skills/              # 投资技能文件
├── scripts/             # 维护和迁移脚本
├── docs/                # 项目文档和报告
└── .pi-invest/          # 本地运行数据，默认不纳入版本控制
```

## Agent 工具系统

项目为 AI Agent 提供了完整的量化投资工具链，采用六层架构设计（2025-05-25 重构完成）：

- **L1 数据管道**：统一的数据获取接口（股票信息、K线、财务数据）
- **L2 因子工厂**：批量因子计算和分析
- **L3 模型层**：机器学习模型训练和预测（待实现）
- **L4 组合构建**：持仓管理和再平衡
- **L5 执行引擎**：订单管理和交易执行
- **L6 监控运维**：实时监控和告警

工具系统从 61 个分散工具精简至 30 个结构化工具，采用统一命名规范（`data_*`, `factor_*`, `portfolio_*`, `trade_*`, `monitor_*`）。

详见 [CLAUDE.md](./CLAUDE.md) 了解完整的工具列表和使用指南。

前端默认通过 `VITE_API_BASE_URL=http://127.0.0.1:5001` 访问 `quantsys-v2` HTTP API，并通过 `VITE_WS_URL=ws://127.0.0.1:5003` 连接 WebSocket。

## 快速开始

### 前置依赖

- Node.js >= 22（根目录 Agent）
- Node.js >= 18（`web-frontend/`）
- Python >= 3.9
- PostgreSQL（当前量化数据层优先使用 PostgreSQL）

### 安装依赖

```bash
npm install
cd web-frontend && npm install
cd ../quant && pip install -r requirements.txt
```

如需使用 `quantsys-v2/`：

```bash
cd quantsys-v2
pip install -r requirements.txt
```

### 启动前端和后端

推荐前端连接 `quantsys-v2`：

```bash
# 终端 1: HTTP API
cd quantsys-v2
python api/server.py

# 终端 2: WebSocket API
cd quantsys-v2
python api/server_websocket.py

# 终端 3: 前端
cd web-frontend
npm run dev
```

默认地址：

- 前端: `http://localhost:3001`
- `quantsys-v2` HTTP API: `http://127.0.0.1:5001`
- `quantsys-v2` WebSocket: `ws://127.0.0.1:5003`
- `quant` API: `http://127.0.0.1:5002`

如需启动 `quant` 后端：

```bash
cd quant
python api/server.py
```

### Agent 命令

```bash
npm run portfolio
npm run feishu
npm test
```

## 配置

常用环境变量：

```bash
export OPENAI_API_KEY=your-key-here
export DEEPSEEK_API_KEY=your-key-here
export PYTHON_BACKEND_URL=http://localhost:5002
export PYTHON_BACKEND_TIMEOUT=30000
```

前端配置位于 `web-frontend/.env.development` 和 `web-frontend/.env.example`：

```bash
VITE_API_BASE_URL=http://127.0.0.1:5001
VITE_WS_URL=ws://127.0.0.1:5003
VITE_USE_MOCK=false
```

飞书 Bot 需要额外配置：

```bash
export FEISHU_APP_ID=cli_xxx
export FEISHU_APP_SECRET=your-feishu-secret
```

## 常用文档

- [项目索引](INDEX.md)
- [量化后端](quantsys-v2/README.md)
- [前端控制台](web-frontend/README.md)
- [测试指南](docs/testing-guide.md)
- [2026-05 报告归档](docs/reports/2026-05/)

## 故障排查

**前端请求失败**

- 确认 `web-frontend/.env.development` 中的 `VITE_API_BASE_URL`
- 确认对应后端端口已启动
- 检查 Vite 代理配置：`web-frontend/vite.config.ts`

**健康检查失败**

```bash
curl http://127.0.0.1:5001/api/health
```

**端口冲突**

- `QUANTSYS_API_PORT` 控制 `quantsys-v2/api/server.py`（默认 5001）
- `QUANTSYS_WS_PORT` 控制 `quantsys-v2/api/server_websocket.py`（默认 5003）

## 免责声明

本项目输出的分析和建议仅供研究参考，不构成投资建议。投资有风险，入市需谨慎。
