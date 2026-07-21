# Phase 3 快速启动指南

## 📋 准备工作

### 1. 环境检查

运行准备检查脚本：

```bash
cd quantsys-v2
python check_phase3_readiness.py
```

如果所有检查通过 ✅，继续下一步。  
如果有检查失败 ❌，按照提示解决问题。

---

## 🚀 Phase 3: 真实数据验证

### 步骤 1: 因子有效性验证

**目标**: 验证 TechnicalScorer 的预测能力

```bash
cd quantsys-v2
python validate_technical_scorer.py
```

**预期输出**:
```
因子有效性分析结果
==================
【IC 分析 - 信息系数】
  5日 IC:  0.0XXX
  10日 IC: 0.0XXX
  20日 IC: 0.0XXX

【IR 分析 - 信息比率】
  5日 IR: 0.XXX
  ...

【单调性分析】
  单调性得分: XX%

【决策建议】
✅/⚠️/❌ ...
```

**决策标准**:
- ✅ IC > 0.07 → 显著有效，进入步骤 2
- ⚠️ IC 0.05-0.07 → 略有效果，考虑参数优化
- ❌ IC < 0.05 → 效果不明显，重新设计

**如果遇到问题**:
```bash
# 检查错误日志
tail -100 validation_output.log

# 常见问题：
# 1. 数据不足 → 补充历史数据
# 2. 连接超时 → 检查数据库
# 3. 内存不足 → 减少股票数量或时间范围
```

---

### 步骤 2: 策略回测对比

**目标**: 对比新旧评分在实际策略中的表现

**前提**: 步骤 1 的 IC > 0.05

```bash
python backtest_scoring_comparison.py
```

**预期输出**:
```
回测结果对比
==================
【新评分策略】
  总收益率: XX.XX%
  年化收益: XX.XX%
  最大回撤: -X.XX%
  夏普比率: X.XX
  胜率: XX.XX%

【旧评分策略】
  总收益率: XX.XX%
  年化收益: XX.XX%
  最大回撤: -X.XX%
  夏普比率: X.XX
  胜率: XX.XX%

改进分析
==================
  收益率提升: +X.XX%
  夏普比率提升: +X.XX
  最大回撤变化: +/-X.XX%

决策建议
==================
✅/⚠️/❌ ...
```

**决策标准**:
- ✅ 收益提升 > 5% 且 夏普提升 > 0.2 → 上线新评分
- ⚠️ 收益提升 2-5% → 进入 Phase 4（参数优化）
- ❌ 收益提升 < 2% → 重新设计

---

## 🔧 Phase 4: 参数优化（可选）

**触发条件**: Phase 3 验证未达上线标准但有改善

### 可优化的参数

1. **权重调整**
   ```python
   # 在 TechnicalScorer 中调整
   rsi_weight = 20      # 当前 ±20 分
   macd_weight = 20     # 当前 ±20 分
   adx_weight = 15      # 当前 0-15 分
   volume_weight = 20   # 当前 ±20 分
   resonance_weight = 15 # 当前 0-15 分
   ```

2. **阈值调优**
   ```python
   # RSI 阈值
   rsi_oversold = 30    # 超卖阈值
   rsi_overbought = 70  # 超买阈值
   
   # ADX 阈值
   adx_threshold = 25   # 趋势强度阈值
   
   # 成交量阈值
   volume_threshold = 1.5  # 放量阈值
   ```

3. **优化方法**
   - 网格搜索
   - 贝叶斯优化
   - 遗传算法

---

## 📊 Phase 5: 生产上线（如果验证通过）

### 上线准备清单

- [ ] Phase 3 验证通过（IC > 0.07，收益 > 5%）
- [ ] 代码审查完成
- [ ] 性能测试通过
- [ ] 监控告警配置
- [ ] 回滚方案准备
- [ ] A/B 测试框架就绪

### A/B 测试建议

**分流比例**: 10% 新评分 vs 90% 旧评分  
**观察期**: 2-4 周  
**关键指标**:
- 选股胜率
- 平均收益
- 用户反馈

**决策规则**:
- 新评分显著优于旧评分 → 全量切换
- 效果相当 → 继续观察或回滚
- 效果变差 → 立即回滚

---

## 🛠️ 故障排查

### 问题 1: 数据库连接失败

```bash
# 检查数据库服务
# PostgreSQL: pg_isready
# MySQL: mysqladmin ping

# 检查配置
cat quantsys-v2/config/database.yml

# 测试连接
python -c "from repositories.kline_repository import KlineRepository; KlineRepository()"
```

### 问题 2: 数据不足

```bash
# 检查数据覆盖范围
# 补充历史数据（根据你的数据源）
python scripts/sync_historical_data.py --start-date 2022-01-01
```

### 问题 3: 内存不足

```python
# 在验证脚本中减少股票数量
test_symbols = all_symbols[:50]  # 从 200 减少到 50

# 或缩短时间范围
start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')  # 从 180 天改为 365 天
```

### 问题 4: alphalens 相关错误

```bash
# 重新安装 alphalens-reloaded
pip install --upgrade alphalens-reloaded

# 如果仍然失败，使用简化版验证
python validate_technical_scorer_simple.py
```

---

## 📞 获取帮助

### 文档位置

- **项目总结**: `docs/superpowers/reports/2026-06-04-opportunity-scoring-project-summary.md`
- **Phase 1 报告**: `docs/superpowers/reports/2026-06-04-opportunity-scoring-phase1-completion.md`
- **Phase 2 报告**: `docs/superpowers/reports/2026-06-04-opportunity-scoring-phase2-completion.md`
- **使用文档**: `quantsys-v2/services/scoring/README.md`

### 相关代码

- **评分引擎**: `quantsys-v2/services/scoring/`
- **验证脚本**: `quantsys-v2/validate_*.py`
- **回测脚本**: `quantsys-v2/backtest_*.py`

---

## ✅ 完成后

记得更新文档和创建 Phase 3 完成报告：

```bash
# 创建 Phase 3 报告
docs/superpowers/reports/2026-06-04-opportunity-scoring-phase3-completion.md

# 记录关键指标：
# - IC 值
# - 收益提升
# - 回测表现
# - 最终决策
```

---

**祝验证顺利！** 🎉
