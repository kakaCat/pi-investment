# Agent-DH 快速参考卡片

## 🚀 启动/停止

```bash
# 启动（默认端口 13080）
cd ~/.dsh/profiles/investment && ./start.sh

# 启动（指定端口）
cd ~/.dsh/profiles/investment && ./start.sh 13081

# 停止
lsof -ti:13080 | xargs kill

# 重启
lsof -ti:13080 | xargs kill && cd ~/.dsh/profiles/investment && ./start.sh
```

## 🔧 开发

```bash
# 构建所有插件（可选，tsx 模式下不需要）
cd agent-dh && pnpm build

# 构建单个插件（可选）
cd agent-dh/packages/investment && pnpm build

# 清理并重新构建（仅生产环境需要）
cd agent-dh && rm -rf node_modules packages/*/node_modules packages/*/dist && pnpm install && pnpm build
```

**注意**: DSH 使用 tsx 模式运行，直接加载 TypeScript 源码（`.ts` 文件），无需构建。详见 `docs/WHY-NO-DIST.md`

## 📝 配置

```bash
# 编辑活跃配置（推荐）
vim ~/.dsh/profiles/investment/cordis.patch.yml

# 编辑模板配置（参考）
vim agent-dh/cordis.yml

# 查看当前配置
cat ~/.dsh/profiles/investment/cordis.patch.yml
```

## 🔍 调试

```bash
# 检查进程
ps aux | grep "dsh.*investment"

# 检查端口
lsof -ti:13080

# 检查 Web UI
curl http://localhost:13080

# 检查 QuantsysV2 后端
curl http://localhost:5001/api/stocks/search?q=平安

# 查看插件构建状态
ls -la agent-dh/packages/*/dist/*.mjs
```

## 📦 插件列表（14个，48个工具）

| 插件 | 工具数 | 功能 |
|------|--------|------|
| investment | 8 | 行情、K线、财务、宏观、北向资金、市场情绪、股票池、策略 |
| trading | 6 | 账户、持仓、交易执行、监控、算法交易、对账 |
| intelligence | 3 | 盯盘规则、盯盘管理、市场告警 |
| competition | 3 | 对手行为、战场评估、操纵检测 |
| market | 3 | 市场风格、行业分析、筹码分析 |
| risk | 3 | 风险控制、风险指标、Barra分解 |
| strategy | 6 | 策略执行、机会扫描、筛选、轮动提案、轮动模拟、轮动执行 |
| factor | 2 | 因子计算、因子分析 |
| model | 3 | 模型预测、模型训练、模型评估 |
| memory | 3 | 记忆搜索、记忆写入、经验记录 |
| evolution | 2 | 进化运行、进化排行榜 |
| scheduler | 1 | 调度器管理 |
| notification | 2 | 飞书通知、通用通知 |
| data-manager | 2 | 数据质量报告、数据管理 |

## 🌐 端口分配

- **13080** - DSH investment profile (Web UI)
- **5001** - QuantsysV2 backend (Python)
- **8080** - Agent OS (Go, 遗留)

## 📁 关键路径

- **插件源码**: `~/pi-investment/agent-dh/packages/`
- **DSH Profile**: `~/.dsh/profiles/investment/`
- **活跃配置**: `~/.dsh/profiles/investment/cordis.patch.yml`
- **模板配置**: `~/pi-investment/agent-dh/cordis.yml`
- **启动脚本**: `~/.dsh/profiles/investment/start.sh`

## 🔑 环境变量

```bash
# 必需
export DEEPSEEK_API_KEY=sk-...
export OPENAI_API_KEY=sk-...

# 可选
export QUANTSYS_V2_API_URL=http://localhost:5001
```

## 📚 文档

- **完整开发指南**: `agent-dh/CLAUDE.md`
- **项目概览**: `agent-dh/README.md`
- **Profile 说明**: `agent-dh/profiles/investment/README.md`

## ⚠️ 重要提示

- ✅ Agent-DH 是 **DSH Profile**，不是独立应用
- ✅ 使用 **tsx 模式**运行，支持 TypeScript 热加载
- ✅ 部分插件无需构建（直接加载 .ts 文件）
- ❌ 不要创建 HTTP 服务器（DSH 已提供）
- ❌ 不要使用 `apps/cli/`（已删除）
- ❌ 不要运行 `npm run dev`（已移除）

---

**快速启动**: `cd ~/.dsh/profiles/investment && ./start.sh`
