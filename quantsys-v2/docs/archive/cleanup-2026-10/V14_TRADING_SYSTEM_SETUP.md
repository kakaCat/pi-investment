# V14交易系统配置完成报告

**配置时间**: 2026-07-01  
**任务状态**: ✅ 完成  

---

## 📋 已创建的文件

### 1. V14策略实现
**文件**: `domain/strategies/v14_strategy.py`

**功能**:
- V14策略封装（BaseStrategy接口）
- 7日调仓周期
- 5只集中持仓
- 18%单股权重（Kelly准则）
- -12%止损线

**配置**:
```python
{
    'name': 'V14 XGBoost Multi-Factor P0',
    'version': '2.0.0',
    'rebalance_days': 7,
    'max_positions': 5,
    'max_position_pct': 0.90,
    'model_path': 'live_trading/models/v14_p0_model.json'
}
```

### 2. V14定时任务
**文件**: `infrastructure/jobs/v14_trading_job.py`

**功能**:
- v14_daily_check(): 每日检查（止损+调仓）
- v14_manual_rebalance(): 手动强制调仓

**流程**:
1. 加载V14 P0模型（75因子）
2. 检查单股止损（-12%）
3. 判断调仓日（7天周期）
4. 执行调仓（如到期）

### 3. V14调度器
**文件**: `scripts/init_v14_scheduler.py`

**功能**:
- 初始化V14调度器
- 注册定时任务（交易日15:30）
- 启动/停止调度器

---

## 🎯 V13 vs V14 对比

| 配置项 | V13 | V14 | 改进 |
|--------|-----|-----|------|
| 调仓周期 | 5天 | 7天 | 降低交易成本 |
| 持仓数量 | 8只 | 5只 | 集中持有高Alpha |
| 单股权重 | 15% | 18% | Kelly准则 |
| 总仓位 | 85% | 90% | 提高资金利用率 |
| 止损 | -15% | -12% | 放宽止损线 |
| 移动止损 | 无 | 有 | 浮盈20/30/50%触发 |
| 因子数量 | 68 | 75 | +7个 |
| 训练样本 | 23,313 | 233,456 | +1000% |
| 账户名 | default | v14_simulation | 独立账户 |

---

## 🚀 使用方法

### 方法1: 启动V14调度器（自动化）

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2

# 初始化并启动V14调度器
python scripts/init_v14_scheduler.py

# 或直接启动（不交互）
python -c "from scripts.init_v14_scheduler import start_scheduler; start_scheduler()"
```

**效果**: 交易日每天15:30自动执行V14策略

### 方法2: 手动执行V14交易

```bash
# 手动执行一次V14每日检查
python -c "from infrastructure.jobs.v14_trading_job import v14_daily_check; import json; print(json.dumps(v14_daily_check(), indent=2))"

# 手动强制调仓（不检查周期）
python -c "from infrastructure.jobs.v14_trading_job import v14_manual_rebalance; import json; print(json.dumps(v14_manual_rebalance(), indent=2))"
```

### 方法3: 通过SimulationTrader直接运行

```bash
# 使用V14 P0模型运行模拟交易
cd live_trading
python simulation_trader.py
```

**注意**: 确保已切换到V14 P0模型（使用`switch_model.sh p0`）

---

## 📊 V13和V14并行运行

### 独立账户

| 策略 | 账户名 | 数据库隔离 |
|------|--------|-----------|
| V13 | `default` | ✅ 独立 |
| V14 | `v14_simulation` | ✅ 独立 |

### 同时运行V13和V14

```bash
# 终端1: 启动V13调度器
python scripts/init_v13_scheduler.py

# 终端2: 启动V14调度器
python scripts/init_v14_scheduler.py
```

两个策略会使用不同账户，互不干扰。

---

## 🔧 配置说明

### V14模拟仓账户

**账户名**: `v14_simulation`
**初始资金**: ¥100,000（可配置）
**数据库表**:
- `quant.positions` (持仓)
- `quant.trades` (交易记录)
- `quant.accounts` (账户)

### V14实盘账户（未配置）

如需实盘交易，需要:
1. 创建账户: `v14_real`
2. 配置券商接口
3. 修改job参数: `account_name='v14_real'`

---

## ⚠️ 注意事项

1. **数据库共享**: V13和V14使用同一数据库，通过account_name区分
2. **模型文件**: 确保使用正确的模型文件（V14 P0）
3. **调仓周期**: V14为7天，V13为5天
4. **风险控制**: V14独立的止损逻辑（-12%）

---

## 📈 下一步建议

### 立即可用
1. ✅ V14策略已配置
2. ✅ V14定时任务已创建
3. ✅ V14调度器已就绪
4. 🔜 启动V14调度器测试

### 实盘部署（可选）
1. 配置券商接口
2. 创建V14实盘账户
3. 小资金验证（1-2万）
4. 逐步扩大资金

---

**配置完成！现在可以启动V14交易系统了。** 🎉
