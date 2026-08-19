# Agent-DH Investment Profile

PI Investment 的 DSH (DeepSeek Harness) 投资分析 Agent 配置。

## 快速启动

### 开发模式（tsx 热加载）

```bash
# 设置 API Key
export DEEPSEEK_API_KEY=sk-...

# 启动（默认端口 13080）
cd ~/.dsh/profiles/investment
./start.sh

# 指定端口
./start.sh 13081

# 仅打印配置
./start.sh 13080 --dump-config
```

### 生产模式（需构建）

```bash
# 1. 构建所有 PI 插件为 JavaScript
cd /Users/yunpeng/pi-investment/agent-dh
pnpm run build

# 2. 使用 profile 本地的 npm 版 DSH 启动（已与 deepseek-harness 源码仓解耦）
cd ~/.dsh/profiles/investment
node --import tsx/esm node_modules/@deepseek-ai/dsh/lib/bin.js --profile investment --port 13080
```

## 为什么需要 tsx 模式

PI Investment 插件使用 TypeScript 编写（`main: ./src/index.ts`），且内部互引使用 `.js` 说明符——Node 原生类型擦除不改写说明符，因此无论源码仓还是 npm 运行时都必须挂 tsx 加载器。

**tsx 模式** (`node --import tsx/esm`) 让 Node.js 能够直接运行 TypeScript，支持：
- 开发时热加载插件修改
- 无需构建步骤即可测试
- 保持源码与运行一致

## 插件清单（14个，48个工具）

| 插件 | 工具数 | 功能 |
|------|--------|------|
| `@pi-investment/investment` | 8 | 行情、K线、财务、宏观、北向资金、市场情绪、股票池、策略列表 |
| `@pi-investment/trading` | 6 | 账户信息、持仓、交易执行、交易监控、算法交易、对账 |
| `@pi-investment/intelligence` | 3 | 盯盘规则、盯盘管理、市场告警 |
| `@pi-investment/competition` | 3 | 对手行为、战场评估、操纵检测 |
| `@pi-investment/market` | 3 | 市场风格、行业分析、筹码分析 |
| `@pi-investment/risk` | 3 | 风险控制、风险指标、Barra分解 |
| `@pi-investment/strategy` | 6 | 策略执行、机会扫描、筛选、轮动提案、轮动模拟、轮动执行 |
| `@pi-investment/factor` | 2 | 因子计算、因子分析 |
| `@pi-investment/model` | 3 | 模型预测、模型训练、模型评估 |
| `@pi-investment/memory` | 3 | 记忆搜索、记忆写入、经验记录 |
| `@pi-investment/evolution` | 2 | 进化运行、进化排行榜 |
| `@pi-investment/scheduler` | 1 | 调度器管理 |
| `@pi-investment/notification` | 2 | 飞书通知、通用通知 |
| `@pi-investment/data-manager` | 2 | 数据质量报告、数据管理 |

## 工具描述优化原则

所有工具描述遵循以下规范：

1. **使用场景说明** - 描述开头说明"用于：..."
2. **参数示例** - 参数描述包含具体示例值
3. **枚举值解释** - 每个枚举值都有中文说明
4. **输出字段完整** - 输出 schema 包含所有字段及单位
5. **单位标注** - 价格（元）、数量（股）、金额（元）、比例（%）

## 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | 是（或 OPENAI_API_KEY） |
| `OPENAI_API_KEY` | OpenAI API Key（与 DeepSeek 相同） | 是（或 DEEPSEEK_API_KEY） |
| `QUANTSYS_V2_API_URL` | quantsys-v2 后端地址 | 否（默认 http://localhost:5001） |

## 配置文件

- `cordis.yml` - 基础配置（空根）
- `cordis.patch.yml` - 插件配置和系统提示词
- `package.json` - 依赖声明
- `start.sh` - 启动脚本
