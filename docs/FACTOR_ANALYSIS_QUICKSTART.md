# 因子分析功能 - 快速开始

## ✅ 已完成的工作

### 1. Python分析脚本（3个）
- ✅ `quant/scripts/analyze_feature_importance.py` - 整体因子重要性
- ✅ `quant/scripts/analyze_stock_factors.py` - 单股因子分析  
- ✅ `quant/scripts/generate_enhanced_report.py` - 增强版报告

### 2. TypeScript服务层
- ✅ `src/services/quant/factor-analysis-service.ts` - 因子分析服务

### 3. AI工具层（3个工具）
- ✅ `src/tools/factor-analysis-tools.ts`
  - `get_feature_importance` - 查看因子重要性
  - `analyze_stock_factors` - 分析单只股票
  - `compare_stock_factors` - 对比多只股票

### 4. 工具注册
- ✅ 已注册到 `src/infrastructure/tools/index.ts`
- ✅ AI可以自动调用这些工具

---

## 🚀 立即体验

### 方式1：在AI对话中使用（推荐）

启动AI Agent：
```bash
npm run dev
```

然后问AI：
```
查看因子重要性
分析000001的因子
对比000001和600036
为什么推荐这只股票？
```

AI会自动调用对应的工具，返回格式化的分析结果。

---

### 方式2：直接运行Python脚本

```bash
cd quant

# 1. 查看整体因子重要性
python scripts/analyze_feature_importance.py

# 2. 分析单只股票
python scripts/analyze_stock_factors.py 000001

# 3. 分析指定日期
python scripts/analyze_stock_factors.py 600036 2026-05-18

# 4. 生成增强版报告
python scripts/generate_enhanced_report.py
```

---

### 方式3：测试TypeScript工具

```bash
npm run tsx src/scripts/test-factor-analysis.ts
```

---

## 📋 前置条件

### 必需：
1. **训练好的ML模型**
   ```bash
   # 检查模型是否存在
   ls quant/quantsys/ml/models/xgboost_model.pkl
   
   # 如果不存在，先训练模型
   cd quant
   python -m quantsys.ml.training.trainer
   ```

2. **股票数据**
   ```bash
   # 检查数据库
   ls quant/quantsys/data/stocks.db
   
   # 如果没有数据，先获取数据
   cd quant
   python scripts/fetch_data.py
   ```

### 可选：
3. **SHAP库（更准确的因子分析）**
   ```bash
   pip install shap
   ```

---

## 💡 使用示例

### 示例1：理解模型决策

**场景**：AI推荐买入000001，你想知道为什么

**对话**：
```
你: 为什么推荐买入000001？

AI: [自动调用 analyze_stock_factors]

📊 000001 因子分析

**预测结果**:
- 方向: 📈 看涨
- 上涨概率: 68.50%

**关键因子**:
1. 📈 RSI=18.3 超卖 (贡献: +0.086)
2. 📈 价格接近布林带下轨 (贡献: +0.062)
3. 📉 成交量萎缩 (贡献: -0.023)

**解读**: 
超卖反弹机会，但成交量不足，建议小仓位试探。
```

---

### 示例2：选股决策

**场景**：在多只股票中选择最优标的

**对话**：
```
你: 对比000001、600036、600519，哪个更好？

AI: [自动调用 compare_stock_factors]

📊 股票对比分析

| 排名 | 股票 | 上涨概率 | 关键优势 |
|------|------|----------|----------|
| 1 | 600036 | 75.20% | RSI超卖+布林带下轨 |
| 2 | 600519 | 70.50% | 均线多头+成交量放大 |
| 3 | 000001 | 68.50% | RSI超卖但量能不足 |

**投资建议**: 首选600036，超卖程度最深，反弹空间最大。
```

---

### 示例3：了解模型逻辑

**场景**：想知道模型主要依赖哪些指标

**对话**：
```
你: 你的模型主要看什么指标？

AI: [自动调用 get_feature_importance]

📊 因子重要性分析

🏆 Top 10 最重要因子:
1. RSI (15.23%) - 相对强弱指标
2. MA5/MA20 (12.45%) - 短期均线比
3. MACD_DIF (9.87%) - MACD快线
4. Volume_Ratio (8.56%) - 成交量比率
5. Price/MA20 (7.34%) - 价格相对均线
...

💡 前5个因子贡献了53%的预测能力
```

---

## 🎯 核心价值

### 对用户：
- ✅ **透明度**：知道AI为什么这么推荐
- ✅ **可验证**：可以检查模型逻辑是否合理
- ✅ **可学习**：理解哪些指标最重要
- ✅ **可信任**：建立对AI决策的信心

### 对开发者：
- ✅ **可调试**：快速定位模型问题
- ✅ **可优化**：知道哪些因子需要改进
- ✅ **可解释**：向用户解释模型行为
- ✅ **可监控**：追踪因子变化

---

## 📊 输出格式

所有工具都返回Markdown格式，包含：
- 📈 表格（清晰对比）
- 💡 解读（人类语言）
- 📖 说明（因子含义）
- 🎯 建议（投资决策）

完美适配AI对话界面！

---

## 🔧 故障排查

### 问题1：模型文件不存在
```bash
❌ 模型文件不存在: quant/quantsys/ml/models/xgboost_model.pkl

解决：
cd quant
python -m quantsys.ml.training.trainer
```

### 问题2：股票数据不存在
```bash
❌ 未找到股票 000001 的数据

解决：
cd quant
python scripts/fetch_data.py
```

### 问题3：SHAP库未安装
```bash
⚠️ SHAP库未安装，使用简化分析

解决（可选）：
pip install shap
```

---

## 📚 完整文档

详细使用指南：[FACTOR_ANALYSIS_GUIDE.md](./FACTOR_ANALYSIS_GUIDE.md)

---

## ✨ 现在就试试！

```bash
# 1. 启动AI
npm run dev

# 2. 问AI
> 查看因子重要性
```

🎉 享受透明、可解释的AI投资决策！
