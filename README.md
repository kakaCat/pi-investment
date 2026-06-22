# AI Stock Investment Advisor

AI 股票投资顾问系统 - 支持 A 股 / 港股

## 项目结构

```
pi-investment/
├── agent-ts/          # TypeScript AI Agent (主应用)
│   ├── src/           # 源代码
│   ├── skills/        # Agent 技能定义
│   └── package.json   # 依赖配置
│
├── quantsys-v2/       # Python 量化后端 (v2)
│   ├── api/           # Flask REST API (5001) + WebSocket (5003)
│   ├── services/      # 业务逻辑层
│   └── repositories/  # 数据访问层
│
├── web-frontend/      # Vue 3 前端 (可选)
│   └── ...            # Vite dev server (3001)
│
├── docs/              # 项目文档
├── scripts/           # 工具脚本
└── docker/            # Docker 配置
```

## 快速开始

### 1. TypeScript Agent

```bash
cd agent-ts
npm install
npm run dev          # 启动 TUI Agent
npm run feishu       # 启动飞书机器人
```

### 2. Python 量化后端

```bash
cd quantsys-v2
source ../activate-py313.sh    # 激活 Python 3.13 环境
python start_all.py            # 启动 REST API + WebSocket
```

### 3. 环境变量

复制并配置环境变量：
```bash
cp agent-ts/.env.example agent-ts/.env
# 编辑 agent-ts/.env，填入必要的 API Key
```

## 详细文档

- TypeScript Agent: [agent-ts/README.md](agent-ts/README.md)
- Python Backend: [quantsys-v2/README.md](quantsys-v2/README.md)
- 项目规范: [agent-ts/CLAUDE.md](agent-ts/CLAUDE.md)

## 端口分配

| 服务 | 端口 |
|------|------|
| quantsys-v2 REST API | 5001 |
| quantsys-v2 WebSocket | 5003 |
| web-frontend (Vite) | 3001 |
| PostgreSQL | 5432 |
| Redis | 6379 |

## 技术栈

- **Agent**: TypeScript, DeepSeek API, @mariozechner/pi-agent-core
- **Backend**: Python 3.13, Flask, pandas, akshare, TA-Lib
- **Database**: PostgreSQL 14+
- **Cache**: Redis
- **Frontend**: Vue 3, Element Plus, Vite
