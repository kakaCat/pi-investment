# 缠论功能使用指南

## 📖 概述

本文档介绍如何使用已集成的缠论（Chan Theory）分析功能。

---

## 🚀 快速开始

### 1. 环境修复（必需）

#### 修复 Python 类型注解兼容性

**问题：** Python 3.8 不支持 `dict | None` 语法

**解决方案：** 修改 `adapters/inbound/api/routes/charts.py:211`

```python
# 将这行：
def _parse_sina_a_quote(raw: str, symbol: str) -> dict | None:

# 改为：
def _parse_sina_a_quote(raw: str, symbol: str) -> Optional[dict]:

# 并在文件顶部添加导入：
from typing import Optional
```

或者升级到 Python 3.10+：
```bash
# 推荐使用 Python 3.11+
pyenv install 3.11
pyenv local 3.11
pip install -r requirements.txt
```

#### 配置数据库连接

确保 `.env` 文件包含正确的 PostgreSQL 配置：
```bash
PGHOST=localhost
PGPORT=5432
PGDATABASE=quant_investment
PGUSER=your_username
PGPASSWORD=your_password
```

### 2. 启动服务

```bash
cd quantsys-v2

# 启动API服务器
python start_all.py

# 或单独启动REST API
python adapters/inbound/api/server.py
```

验证服务启动：
```bash
curl http://localhost:5001/api/chan/health
# 预期输出: {"status":"ok","service":"chan-analysis"}
```

### 3. 启动前端

```bash
cd web-frontend
npm run dev
```

访问：`http://localhost:3000`

---

## 🎯 使用方法

### 方法一：通过前端界面

1. **打开股票详情页**
   - 在左侧菜单点击"图表研究"或"股票列表"
   - 选择任意股票（如：600519 茅台）
   - 进入股票详情页

2. **切换到"缠论分析"标签页**
   - 在页面顶部的标签栏中，点击"缠论分析"
   - 系统会自动加载最近一年的缠论分析

3. **查看分析结果**
   - **顶部信息栏**：显示走势类型（上涨/下跌/盘整）和统计数据
   - **K线图区域**：显示买卖点标记
   - **底部表格**：查看买卖点详细信息

### 方法二：通过API调用

#### 分析单只股票

```bash
curl -X POST http://localhost:5001/api/chan/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "600519.SH",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31"
  }' | python -m json.tool
```

**响应示例：**
```json
{
  "symbol": "600519.SH",
  "trend_type": "上涨",
  "bis": [
    {
      "direction": "up",
      "start_index": 0,
      "end_index": 5,
      "high": 1850.0,
      "low": 1720.0,
      "length": 6,
      "amplitude": 0.075
    }
  ],
  "segments": [...],
  "zhongshus": [...],
  "buypoints": [
    {
      "type": "1买",
      "price": 1720.5,
      "date": "2024-03-15",
      "confidence": 0.9,
      "position_ratio": 1.0,
      "reason": "下跌背驰"
    }
  ]
}
```

#### 使用 Python

```python
import requests

response = requests.post('http://localhost:5001/api/chan/analyze', json={
    'symbol': '600519.SH',
    'startDate': '2024-01-01',
    'endDate': '2024-12-31'
})

result = response.json()
print(f"走势类型: {result['trend_type']}")
print(f"买卖点数量: {len(result['buypoints'])}")

for bp in result['buypoints']:
    print(f"{bp['type']} @ ¥{bp['price']:.2f} (置信度: {bp['confidence']:.1%})")
```

#### 使用 JavaScript

```javascript
const response = await fetch('http://localhost:5001/api/chan/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    symbol: '600519.SH',
    startDate: '2024-01-01',
    endDate: '2024-12-31'
  })
});

const result = await response.json();
console.log('走势类型:', result.trend_type);
console.log('买卖点:', result.buypoints);
```

---

## 📊 数据说明

### 走势类型

- **上涨**：高点和低点都在抬升，无中枢形成
- **下跌**：高点和低点都在下降，无中枢形成
- **盘整**：存在中枢，价格在区间震荡

### 买卖点类型

| 类型 | 说明 | 置信度 | 建议仓位 |
|------|------|--------|----------|
| **1买** | 下跌背驰后的第一个买点 | 90% | 满仓 100% |
| **2买** | 回调不破中枢的第二个买点 | 70% | 半仓 60% |
| **3买** | 突破前高的第三个买点 | 50% | 轻仓 30% |
| **1卖** | 上涨背驰后的第一个卖点 | 90% | 清仓 100% |
| **2卖** | 反弹不破中枢的第二个卖点 | 70% | 减仓 60% |
| **3卖** | 跌破前低的第三个卖点 | 50% | 止损 30% |

### 笔（Bi）

连接相邻顶底分型的折线，是缠论最小的方向性单位。

**字段说明：**
- `direction`: 方向（up/down）
- `high/low`: 最高/最低价
- `length`: 包含的K线数量
- `amplitude`: 振幅（百分比）

### 线段（Segment）

由至少3笔构成的更大级别方向性结构。

**字段说明：**
- `direction`: 方向（up/down）
- `start_index/end_index`: 起止索引
- `bi_count`: 包含的笔数量

### 中枢（ZhongShu）

至少3个线段的重叠区间，代表盘整或震荡。

**字段说明：**
- `high/low`: 中枢上下沿
- `type`: 类型（震荡）
- `segment_count`: 包含的线段数量

---

## 🔧 高级用法

### 过滤特定买卖点类型

```bash
curl -X POST http://localhost:5001/api/chan/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "600519.SH",
    "startDate": "2024-01-01",
    "endDate": "2024-12-31",
    "buypointTypes": ["1买", "2买"]
  }'
```

### 自定义日期范围

```bash
# 分析最近3个月
curl -X POST http://localhost:5001/api/chan/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "600519.SH",
    "startDate": "2024-03-01",
    "endDate": "2024-06-01"
  }'
```

---

## 🐛 故障排查

### 1. API返回 "无数据"

**原因：** 数据库中没有该股票的K线数据

**解决：**
```bash
# 运行数据修复
curl -X POST http://localhost:5001/api/stock/repair \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600519.SH"}'
```

### 2. 前端一直显示"分析中..."

**原因：** API服务未启动或连接失败

**检查：**
```bash
# 1. 检查API服务是否运行
curl http://localhost:5001/api/chan/health

# 2. 检查前端配置的API地址
# 编辑 web-frontend/src/views/StockDetail/index.vue
# 确认 fetch('http://localhost:5001/api/chan/analyze', ...)
```

### 3. 买卖点数量为0

**原因：** 可能是正常现象（该时间段内没有出现符合条件的买卖点）

**建议：**
- 延长分析时间范围（如：一年 → 两年）
- 检查是否使用了过滤条件

---

## 📈 最佳实践

### 1. 选择合适的时间范围

- **短期分析**（1-3个月）：看近期买卖点
- **中期分析**（6个月-1年）：推荐，数据量适中
- **长期分析**（1-3年）：看大周期结构，计算量大

### 2. 结合其他指标

缠论分析结果应与其他标签页结合：
- **技术指标**：验证MACD背驰
- **历史信号**：对比其他策略信号
- **因子一览**：确认基本面支撑

### 3. 置信度使用建议

- **90%置信度（1买/1卖）**：背驰明显，可重仓
- **70%置信度（2买/2卖）**：中枢支撑，可中仓
- **50%置信度（3买/3卖）**：突破确认，轻仓试探

---

## 🎓 缠论基础知识

### 核心概念

1. **分型**：K线高低点的结构模式
2. **笔**：连接分型的最小单位
3. **线段**：3笔以上构成的趋势
4. **中枢**：3线段重叠形成的震荡区
5. **背驰**：价格新高/新低但MACD面积减小

### 三类买点

- **第一类买点**：下跌后首次背驰
- **第二类买点**：回调不破中枢
- **第三类买点**：突破前高确认

### 学习资源

- [缠论原文](http://blog.sina.com.cn/chzhshch)
- [本项目README](../domain/chan/README.md)

---

## 📞 支持

如有问题或建议，请：
1. 查看项目文档：`quantsys-v2/domain/chan/README.md`
2. 运行测试：`python test_chan_integration.py`
3. 查看日志：`tail -f /tmp/api-server.log`

---

**祝投资顺利！** 📈
