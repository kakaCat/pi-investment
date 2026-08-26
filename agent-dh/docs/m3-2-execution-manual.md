# M3-2 策略回测矩阵 - 执行手册

## 目标

验证 5 个候选策略在不同市场环境（牛/熊/震荡）下的表现，筛选出样本外夏普比率 >1 的生产策略池（≥3 个）。

## 策略池（已选定）

| 编号 | 策略名称 | 类型 | 特点 | 适用环境 |
|------|----------|------|------|----------|
| 1 | V13 XGBoost Multi-Factor | ML多因子 | 5日调仓，8只持仓 | 通用 |
| 2 | V14 XGBoost Multi-Factor Optimized | ML多因子 | 30日调仓，15只持仓 | 牛市优化 |
| 3 | Strategy 272 | 技术指标-严格 | RSI<50 + 突破MA5 + MACD>0 + 放量>1.3 | 震荡/弱势 |
| 4 | Strategy 273 | 技术指标-宽松 | RSI<60 + 轻度突破 + MACD>-0.5 | 牛市 |
| 5 | Strategy 274 ML | ML预测 | Random Forest，买入概率>0.7 | 通用 |

**多样性分析**：
- ✅ 类型多样：2个ML多因子 + 2个技术指标 + 1个ML预测
- ✅ 风格互补：严格(272) vs 宽松(273)，短线(V13) vs 长线(V14)
- ✅ 环境覆盖：牛市(V14/273) + 震荡(272) + 通用(V13/274)

## 环境定义

| 环境 | 日期区间 | 预期上证指数收益 | 特征 |
|------|----------|------------------|------|
| 牛市 | 2023-01-01 ~ 2023-06-30 | +5% 以上 | 上涨趋势，高成交量 |
| 熊市 | 2022-04-01 ~ 2022-10-31 | -15% 以上 | 下跌趋势，恐慌情绪 |
| 震荡 | 2021-07-01 ~ 2021-12-31 | ±5% 区间 | 无明显趋势，波动加剧 |

## 前置条件

### 1. 服务运行

```bash
# 检查 quantsys-v2 后端
lsof -ti:5001 -sTCP:LISTEN && echo "✅ quantsys-v2 运行中" || echo "❌ quantsys-v2 未运行"

# 如果未运行，启动服务
cd /Users/yunpeng/pi-investment/quantsys-v2
nohup python adapters/inbound/fastapi_app/main.py > /Users/yunpeng/v2-api.log 2>&1 &
```

### 2. 数据回填（关键）

**问题**：quantsys-v2 的 K 线端点只读数据库，不会自动拉取外部数据。

**解决**：运行数据回填脚本补充 3 个环境区间的历史 K 线。

```bash
cd /Users/yunpeng/pi-investment/quantsys-v2

# 方案 A：使用 W1 回填脚本（自动选股）
python scripts/w1_backfill_klines.py --mode all

# 方案 B：针对性回填（推荐，避免回填所有股票超时）
python << 'EOF'
import sys
sys.path.insert(0, '.')
from adapters.outbound.repositories.kline_repository import KlineORMRepository
from application.services.data_backfiller import DataBackfiller

repo = KlineORMRepository()
backfiller = DataBackfiller(kline_repo=repo)

# 回填上证指数 + 常用股票
symbols = ['000001', '600519', '000002', '600036', '601318']
periods = [
    ('2023-01-01', '2023-06-30'),
    ('2022-04-01', '2022-10-31'),
    ('2021-07-01', '2021-12-31'),
]

for start, end in periods:
    print(f'回填 {start} ~ {end}')
    for symbol in symbols:
        try:
            result = backfiller.backfill_symbol(symbol, start, end)
            print(f'  {symbol}: {result}')
        except Exception as e:
            print(f'  {symbol}: 失败 - {e}')
EOF
```

**外部数据源问题**：如果 AkShare/baostock 等外部数据源不可用（连接断开/超时），需要等待恢复。通常晚上或次日早晨恢复。

**验证数据**：

```bash
# 检查上证指数 2023 年上半年数据
curl -s "http://localhost:5001/api/stock/000001/klines?start_date=2023-01-01&end_date=2023-06-30&period=daily" | jq '.count'

# 应返回 >100（约 120 个交易日）
```

## 执行步骤

### 步骤 1：验证环境

脚本会自动验证 3 个环境的 K 线数据覆盖和实际收益率：

```bash
cd /Users/yunpeng/pi-investment/agent-dh
python scripts/m3-2-strategy-backtest-matrix.py
```

**预期输出**：
```
【步骤 1/3】验证市场环境定义

验证环境：牛市 (2023-01-01 ~ 2023-06-30)
  ✅ 120 根K线 | 收益: 5.2% (预期 5.0%)

验证环境：熊市 (2022-04-01 ~ 2022-10-31)
  ✅ 140 根K线 | 收益: -16.8% (预期 -15.0%)

验证环境：震荡 (2021-07-01 ~ 2021-12-31)
  ✅ 125 根K线 | 收益: 1.3% (预期 0.0%)
```

如果某个环境数据不足，脚本会退出并提示先回填数据。

### 步骤 2：执行回测矩阵

脚本会自动执行 5 策略 × 3 环境 = 15 次回测。每次回测约 10 分钟，总计 **2.5 小时**。

**注意**：
- 脚本会保存中间结果到 `output/m3-2/interim_*.json`（防止中途失败丢失）
- 可以 Ctrl+C 中断，下次从失败处继续（需手动修改脚本跳过已完成的）

**预期输出**：
```
【步骤 2/3】执行回测矩阵 (15 次回测)

回测: V13 XGBoost Multi-Factor × 牛市
  ✅ 收益: 12.5% | 回撤: -8.3% | 夏普: 1.35 | 胜率: 65.0%

回测: V13 XGBoost Multi-Factor × 熊市
  ✅ 收益: -5.2% | 回撤: -12.1% | 夏普: 0.42 | 胜率: 45.0%

...（继续 13 次）
```

### 步骤 3：查看报告

脚本会自动生成两份输出：

1. **JSON 结果**：`output/m3-2/backtest_results_YYYYMMDD_HHMMSS.json`
   - 包含所有回测的原始数据
   - 可用于二次分析

2. **Markdown 报告**：`output/m3-2/backtest_report_YYYYMMDD_HHMMSS.md`
   - 策略排名表（按平均夏普）
   - 详细回测矩阵
   - 生产策略池建议

**报告示例**：

```markdown
# M3-2 策略回测矩阵报告

**执行时间**: 2026-08-26 20:00:00
**策略数量**: 5
**环境数量**: 3
**回测总数**: 15 (成功: 15)

## 策略排名（按平均夏普比率）

| 排名 | 策略 | 平均夏普 | 平均收益(%) | 最大回撤(%) | 生产级 |
|------|------|----------|------------|------------|--------|
| 1 | V13 XGBoost Multi-Factor | 1.25 | 8.5 | 12.3 | ✅ |
| 2 | Strategy 274 ML | 1.18 | 7.2 | 15.8 | ✅ |
| 3 | V14 XGBoost Multi-Factor Optimized | 1.05 | 9.3 | 18.5 | ✅ |
| 4 | Strategy 273 | 0.92 | 6.1 | 22.4 | ❌ |
| 5 | Strategy 272 | 0.85 | 5.8 | 19.1 | ❌ |

## 生产策略池建议

✅ **筛选出 3 个生产策略**（夏普>1 且回撤<20%）：

- **V13 XGBoost Multi-Factor**: 夏普 1.25, 收益 8.5%, 回撤 12.3%
- **Strategy 274 ML**: 夏普 1.18, 收益 7.2%, 回撤 15.8%
- **V14 XGBoost Multi-Factor Optimized**: 夏普 1.05, 收益 9.3%, 回撤 18.5%
```

## 后续操作

### 1. 飞书推送

```bash
# 将报告推送到飞书
python << 'EOF'
import requests

with open('output/m3-2/backtest_report_最新.md', 'r') as f:
    report = f.read()

# 调用 feishu_notify（需要在 DSH 会话中）
# 或直接用 webhook
url = "你的飞书webhook"
requests.post(url, json={"msg_type": "text", "content": {"text": report[:2000]}})
EOF
```

### 2. 落库记录

```bash
# 保存到 os-memory
python << 'EOF'
import json
with open('output/m3-2/backtest_results_最新.json', 'r') as f:
    results = json.load(f)

# 调用 memory_write(namespace='strategy_evaluation', content=json.dumps(results))
EOF
```

### 3. 应用生产策略

将筛选出的生产策略配置到实盘信号生成：

```python
# 在 agent-dh 配置文件中启用
PRODUCTION_STRATEGIES = [13, 274, 14]  # V13, 274, V14
```

## 故障排查

### Q1: 回测超时（>10分钟）

**原因**：策略计算量大或股票池太大

**解决**：
- 缩小股票池范围（在策略配置中限制）
- 增加超时时间（修改脚本 `timeout=600` → `1200`）

### Q2: 某个策略全部失败

**原因**：策略代码 bug 或依赖缺失

**解决**：
- 查看 quantsys-v2 日志：`tail -100 /Users/yunpeng/v2-api.log`
- 跳过该策略，用剩余策略完成矩阵

### Q3: 环境验证失败（无 K 线数据）

**原因**：数据库未回填或外部数据源不可用

**解决**：
- 等待外部数据源恢复（通常晚上或次日）
- 运行数据回填脚本（见"前置条件"章节）

### Q4: 生产策略不足 3 个

**原因**：筛选标准过严或策略整体表现不佳

**解决**：
- 放宽标准：夏普>0.8 或回撤<25%
- 优化策略参数（用 evolution_run）
- 增加新策略候选

## 验收标准

- ✅ 15 次回测全部完成（或失败原因明确记录）
- ✅ 矩阵表格包含 4 个指标（收益/回撤/夏普/胜率）
- ✅ 至少筛选出 3 个生产策略（夏普>1）
- ✅ 结果已落库（memory_write）并飞书推送

## 附录：手动执行单次回测

如果脚本失败，可以手动执行单次回测测试：

```bash
curl -X POST http://localhost:5001/api/strategies/13/backtest \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2023-01-01",
    "end_date": "2023-06-30",
    "initial_capital": 100000,
    "mode": "backtest"
  }' | jq '.result | {收益率, 最大回撤, 夏普比率, 胜率}'
```

---

**文档版本**: v1.0  
**作者**: PI 投资顾问·投资脑  
**日期**: 2026-08-26  
**状态**: 待数据源恢复后执行
