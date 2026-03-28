# PI Investment - AI 投资顾问

基于 [piagent](https://github.com/user/piagent) 架构的 A 股/港股投资分析 Agent。通过 TypeScript 驱动 LLM 对话，优先走 TypeScript 原生数据源，必要时回退到 Python/akshare，提供投资分析和组合管理能力。

## 架构

```
pi-investment/
├── src/
│   ├── core/
│   │   └── agent/
│   │       └── system-prompt.ts     # 投资顾问系统提示词
│   ├── services/
│   │   └── intelligence/
│   │       ├── system-prompt-builder.ts  # 8层提示词组装器
│   │       └── bootstrap-loader.ts      # Bootstrap 文件加载器
│   └── tools/
│       ├── investment-tools.ts      # 投资工具注册
│       └── akshare-bridge.ts        # TypeScript → Python 桥接
├── python/
│   └── akshare_bridge.py           # akshare 数据获取
├── skills/                          # 投资技能文件
│   ├── stock-screener.md           # 选股技能
│   ├── deep-analysis.md            # 深度分析技能
│   ├── risk-manager.md             # 风险管理技能
│   ├── market-analysis.md          # 市场分析技能
│   ├── portfolio-review.md         # 持仓复盘技能
│   └── quant-strategy.md           # 量化策略技能
├── package.json
└── tsconfig.json
```

## 快速开始

### 前置依赖

- Node.js >= 22
- Python >= 3.9
- pip install akshare

### 安装

```bash
npm install
pip install akshare
```

### 配置

设置 API Key（DeepSeek 或其他 LLM 提供商）：

```bash
export DEEPSEEK_API_KEY=your-key-here
```

### 启动

```bash
npm run dev
```

可选：

```bash
npm run portfolio
npm test
```

## 可用工具

### 行情数据
| 工具 | 功能 | 输入 |
|------|------|------|
| `get_stock_price` | 获取实时价格 | symbol (如 '600519') |
| `get_stock_info` | 获取公司基本信息 | symbol |
| `get_stock_news` | 获取个股新闻舆情 | symbol |

### 基本面分析
| 工具 | 功能 | 输入 |
|------|------|------|
| `get_financial_data` | 财务数据(ROE/利润率/负债率) | symbol |
| `get_valuation` | 估值数据(PE/PB/PEG) | symbol |

### 技术分析
| 工具 | 功能 | 输入 |
|------|------|------|
| `analyze_technical` | 技术指标(MA/MACD/RSI/布林带) | symbol |
| `get_buy_range` | 计算合理买入区间 | symbol |

### 选股筛选
| 工具 | 功能 | 输入 |
|------|------|------|
| `screen_stocks` | 按条件筛选股票 | sector, max_pe, min_roe |

### 宏观数据
| 工具 | 功能 | 输入 |
|------|------|------|
| `get_market_overview` | 大盘指数概览 | - |
| `get_north_flow` | 北向资金流向 | - |
| `get_macro_data` | 宏观经济指标(PMI/CPI) | - |

### 持仓管理
| 工具 | 功能 | 输入 |
|------|------|------|
| `manage_portfolio` | 管理投资组合 | action: get/add/remove/update |

## 技能系统

技能文件（`skills/*.md`）为 Agent 提供投资领域的专业知识和工作流程指导：

- **选股技能** - A 股优质股票筛选标准和流程
- **深度分析** - 四维评分框架（基本面+估值+技术+消息）
- **风险管理** - 仓位控制、止损原则、加仓策略
- **市场分析** - 宏观指标解读、行业轮动框架
- **持仓复盘** - 组合健康度评估、调仓建议
- **量化策略** - 市场过滤、行业轮动、质量评分、趋势确认

## 示例对话

```
用户: 帮我分析一下贵州茅台

Agent: [调用 get_stock_info, get_stock_price, get_financial_data,
        get_valuation, analyze_technical, get_stock_news]

       ## 贵州茅台(600519) 深度分析报告
       综合评分: 78分 - 推荐持有
       ...
```

```
用户: 帮我在新能源板块选几只好股票

Agent: [调用 screen_stocks("新能源", max_pe=35, min_roe=12)]
       [对 Top-3 调用 get_financial_data + get_valuation]

       ## 新能源板块选股推荐
       | 排名 | 股票 | ROE | PE | 推荐理由 |
       ...
```

```
用户: 现在大盘环境怎么样？

Agent: [调用 get_market_overview, get_north_flow, get_macro_data]

       ## 市场分析报告
       市场温度: 偏热
       建议仓位: 60%
       ...
```

## 免责声明

本工具提供的所有分析和建议仅供参考，不构成投资建议。投资有风险，入市需谨慎。请根据自身风险承受能力做出独立判断。
