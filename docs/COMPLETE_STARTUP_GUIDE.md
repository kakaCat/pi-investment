# 🚀 量化系统完整启动指南

## 📦 项目架构（3部分）

```
pi-investment/
├── 1️⃣ AI Agent (TypeScript)          # AI对话助手
├── 2️⃣ 量化系统后端 (Python)          # 因子计算、ML模型
└── 3️⃣ 量化前端 (React)               # 可视化Dashboard
```

---

## 🎯 启动方式（3种）

### 方式1：AI对话模式 ⭐ 推荐日常使用

**适合**：日常投资决策、快速查询

```bash
# 启动AI Agent
cd /Users/mac/Documents/ai/pi-investment
npm run dev

# 然后问AI：
> 查看因子重要性
> 分析000001的因子
> 对比000001和600036
```

**特点**：
- ✅ 自然语言交互
- ✅ 自动调用量化系统
- ✅ 智能分析和建议

---

### 方式2：Web可视化模式 ⭐ 推荐深度分析

**适合**：详细分析、图表展示、多维度对比

#### 第1步：启动Python后端API

```bash
# 终端1：启动后端
cd /Users/mac/Documents/ai/pi-investment/quant

# 安装依赖（首次）
pip install flask flask-cors

# 启动API服务
python api/server.py

# 看到提示：
# 🚀 启动量化系统API服务...
# ✅ 服务初始化完成
# 📡 API地址: http://localhost:5000
```

#### 第2步：启动React前端

```bash
# 终端2：启动前端
cd /Users/mac/Documents/ai/pi-investment/quant-web

# 安装依赖（首次）
npm install

# 启动开发服务器
npm run dev

# 看到提示：
# ➜  Local:   http://localhost:3000/
```

#### 第3步：访问Web界面

打开浏览器访问：**http://localhost:3000**

**功能**：
- 📊 因子重要性分析（柱状图、饼图）
- 📈 股票因子分析（雷达图、表格）
- 🔍 股票对比（横向对比）
- 📡 交易信号（实时监控）

---

### 方式3：直接运行Python脚本

**适合**：快速测试、命令行操作

```bash
cd /Users/mac/Documents/ai/pi-investment/quant

# 1. 查看因子重要性
python scripts/analyze_feature_importance.py

# 2. 分析单只股票
python scripts/analyze_stock_factors.py 000001

# 3. 生成增强报告
python scripts/generate_enhanced_report.py
```

---

## 📋 前置条件检查

### 必需条件：

#### 1. 训练好的ML模型

```bash
# 检查模型是否存在
ls /Users/mac/Documents/ai/pi-investment/quant/quantsys/ml/models/xgboost_model.pkl

# 如果不存在，训练模型（需要5-10分钟）
cd /Users/mac/Documents/ai/pi-investment/quant
python -m quantsys.ml.training.trainer
```

#### 2. 股票数据

```bash
# 检查数据库
ls /Users/mac/Documents/ai/pi-investment/quant/quantsys/data/stocks.db

# 如果没有数据，获取数据
cd /Users/mac/Documents/ai/pi-investment/quant
python scripts/fetch_data.py
```

#### 3. Python依赖

```bash
cd /Users/mac/Documents/ai/pi-investment/quant
pip install -r requirements.txt
pip install flask flask-cors  # Web模式需要
```

#### 4. Node.js依赖

```bash
# AI Agent依赖
cd /Users/mac/Documents/ai/pi-investment
npm install

# Web前端依赖
cd /Users/mac/Documents/ai/pi-investment/quant-web
npm install
```

---

## 🎯 推荐使用流程

### 日常使用：AI对话模式

```bash
# 1. 启动AI
npm run dev

# 2. 快速查询
> 今天有什么买入信号？
> 分析000001的因子
> 对比茅台和五粮液
```

### 深度分析：Web可视化

```bash
# 1. 启动后端（终端1）
cd quant && python api/server.py

# 2. 启动前端（终端2）
cd quant-web && npm run dev

# 3. 浏览器访问
http://localhost:3000

# 4. 使用界面
- 点击"因子重要性" → 查看图表
- 点击"股票分析" → 输入000001
- 点击"股票对比" → 添加多只股票
- 点击"交易信号" → 查看实时信号
```

---

## 🎨 Web界面功能预览

### 1. 因子重要性页面
```
📊 因子重要性分析
├── 统计卡片
│   ├── 总因子数: 25个
│   ├── 核心因子数: 8个（贡献80%）
│   └── 最重要因子: RSI (15.23%)
├── Top 15 柱状图
├── Top 5 饼图
└── 解读说明
```

### 2. 股票分析页面
```
📈 股票因子分析
├── 搜索框（输入股票代码）
├── 预测结果卡片
│   ├── 股票代码: 000001
│   ├── 当前价格: ¥10.86
│   ├── 上涨概率: 68.50%
│   └── 置信度: 37.00%
├── 关键因子表格（Top 10）
├── 因子贡献柱状图
└── 因子雷达图
```

### 3. 股票对比页面
```
🔍 股票对比分析
├── 添加股票（最多5只）
├── 对比结果表格
│   ├── 排名
│   ├── 上涨概率
│   ├── 方向
│   └── 关键因子
└── 投资建议
    ├── 首选: 600036 (75.20%)
    └── 次选: 000001 (68.50%)
```

### 4. 交易信号页面
```
📡 交易信号
├── 统计面板
│   ├── 买入信号: 20个
│   ├── 卖出信号: 21个
│   └── 总信号数: 41个
├── 买入信号列表
└── 卖出信号列表
```

---

## 🔧 故障排查

### 问题1：AI无法调用因子分析工具

**症状**：AI说"工具未找到"或"调用失败"

**解决**：
```bash
# 1. 检查工具是否注册
grep "factorAnalysisTools" src/infrastructure/tools/index.ts

# 2. 重启AI
npm run dev
```

---

### 问题2：Web前端无法连接后端

**症状**：浏览器显示"获取数据失败"

**解决**：
```bash
# 1. 检查后端是否运行
curl http://localhost:5000/api/health

# 2. 如果没有响应，启动后端
cd quant
python api/server.py

# 3. 检查CORS配置
# 确保 api/server.py 中有 CORS(app)
```

---

### 问题3：显示"模型未加载"

**症状**：API返回"模型未加载"错误

**解决**：
```bash
# 训练模型
cd quant
python -m quantsys.ml.training.trainer

# 检查模型文件
ls quantsys/ml/models/xgboost_model.pkl
```

---

### 问题4：显示"未找到股票数据"

**症状**：查询股票时提示"未找到数据"

**解决**：
```bash
# 获取股票数据
cd quant
python scripts/fetch_data.py

# 检查数据库
sqlite3 quantsys/data/stocks.db "SELECT COUNT(*) FROM daily_klines;"
```

---

## 📊 完整启动流程（首次使用）

```bash
# ========== 准备工作 ==========

# 1. 安装Python依赖
cd /Users/mac/Documents/ai/pi-investment/quant
pip install -r requirements.txt
pip install flask flask-cors

# 2. 获取股票数据
python scripts/fetch_data.py

# 3. 训练ML模型
python -m quantsys.ml.training.trainer

# 4. 安装Node.js依赖
cd /Users/mac/Documents/ai/pi-investment
npm install

cd /Users/mac/Documents/ai/pi-investment/quant-web
npm install

# ========== 启动服务 ==========

# 方式A：AI对话模式
cd /Users/mac/Documents/ai/pi-investment
npm run dev

# 方式B：Web可视化模式
# 终端1：
cd /Users/mac/Documents/ai/pi-investment/quant
python api/server.py

# 终端2：
cd /Users/mac/Documents/ai/pi-investment/quant-web
npm run dev

# 浏览器访问：http://localhost:3000
```

---

## 🎉 快速测试

### 测试AI模式

```bash
npm run dev

# 输入：
> 查看因子重要性
```

### 测试Web模式

```bash
# 1. 启动后端
cd quant && python api/server.py

# 2. 测试API
curl http://localhost:5000/api/health

# 3. 启动前端
cd quant-web && npm run dev

# 4. 访问浏览器
open http://localhost:3000
```

---

## 📚 相关文档

- [因子分析功能指南](./docs/FACTOR_ANALYSIS_GUIDE.md)
- [快速开始](./docs/FACTOR_ANALYSIS_QUICKSTART.md)
- [Web前端README](./quant-web/README.md)
- [量化系统文档](./quant/README.md)

---

## 💡 使用建议

1. **日常使用**：用AI对话模式，快速方便
2. **深度分析**：用Web可视化，图表清晰
3. **批量处理**：用Python脚本，自动化执行

**现在就开始吧！** 🚀

选择一种方式启动，体验量化投资的魅力！
