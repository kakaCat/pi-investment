# 量化系统可视化前端

## 📊 功能特性

- ✅ **因子重要性分析** - 柱状图、饼图展示因子排名
- ✅ **股票因子分析** - 单股详细分析，雷达图、表格展示
- ✅ **股票对比** - 多只股票横向对比，智能推荐
- ✅ **交易信号** - 实时买卖信号监控

## 🚀 快速启动

### 1. 安装依赖

```bash
cd quant-web
npm install
```

### 2. 启动后端API

```bash
# 在另一个终端
cd ../quant
pip install flask flask-cors
python api/server.py
```

后端API会在 `http://localhost:5000` 启动

### 3. 启动前端

```bash
npm run dev
```

前端会在 `http://localhost:3000` 启动

### 4. 访问

打开浏览器访问：`http://localhost:3000`

## 📦 技术栈

- **前端框架**: React 18 + TypeScript
- **UI组件**: Ant Design 5
- **图表库**: Recharts
- **构建工具**: Vite
- **HTTP客户端**: Axios

## 🎯 页面说明

### 1. 因子重要性
- 查看52个因子的重要性排名
- Top 15柱状图
- Top 5饼图
- 80/20法则分析

### 2. 股票分析
- 输入股票代码（如000001）
- 查看预测结果（上涨概率、方向、置信度）
- Top 10关键因子表格
- 因子贡献柱状图
- 因子雷达图

### 3. 股票对比
- 添加2-5只股票
- 横向对比预测结果
- 智能推荐最优标的
- 关键因子差异分析

### 4. 交易信号
- 实时买卖信号列表
- 按信心度排序
- 买入/卖出信号统计

## 🔧 开发命令

```bash
# 开发模式
npm run dev

# 构建生产版本
npm run build

# 预览生产版本
npm run preview
```

## 📝 API接口

后端提供以下API：

- `GET /api/health` - 健康检查
- `GET /api/feature-importance` - 因子重要性
- `GET /api/stock/:symbol/factors` - 股票因子分析
- `POST /api/stocks/compare` - 股票对比
- `GET /api/signals` - 交易信号

## 🎨 界面预览

### 因子重要性
- 📊 柱状图展示Top 15因子
- 🥧 饼图展示Top 5占比
- 📈 统计卡片（总数、核心数、最重要因子）

### 股票分析
- 🔍 搜索框输入股票代码
- 📊 预测结果卡片（价格、概率、方向、置信度）
- 📋 因子贡献表格
- 📈 柱状图可视化
- 🎯 雷达图展示

### 股票对比
- ➕ 添加/删除股票
- 🏆 排名表格
- 💡 投资建议

### 交易信号
- 📈 买入信号列表
- 📉 卖出信号列表
- 📊 统计面板

## ⚠️ 注意事项

1. **确保后端API已启动**
   ```bash
   cd quant
   python api/server.py
   ```

2. **确保有训练好的模型**
   ```bash
   ls quant/quantsys/ml/models/xgboost_model.pkl
   ```

3. **确保有股票数据**
   ```bash
   ls quant/quantsys/data/stocks.db
   ```

## 🐛 故障排查

### 问题1: 前端无法连接后端
- 检查后端是否在5000端口运行
- 检查浏览器控制台是否有CORS错误

### 问题2: 显示"模型未加载"
- 确保已训练ML模型
- 检查模型路径是否正确

### 问题3: 显示"未找到股票数据"
- 确保数据库中有该股票的数据
- 运行数据获取脚本

## 📚 相关文档

- [因子分析功能指南](../docs/FACTOR_ANALYSIS_GUIDE.md)
- [快速开始](../docs/FACTOR_ANALYSIS_QUICKSTART.md)
- [量化系统文档](../quant/README.md)
