# K线买卖点标注功能 - 更新总结

**日期**: 2026-05-22  
**功能**: 在K线图上标注量化系统的买卖点信号

---

## ✅ 已完成的更新

### 1. 后端API规范（backend-api-spec.md）

新增**交易信号模块**，包含4个API命令：

#### P0（必须）
- ✅ `signal.get-trading-signals` - 获取股票的买卖点信号
- ✅ `signal.record-signal` - 记录新的买卖点信号

#### P1（重要）
- ✅ `signal.mark-error` - 标记错误的信号（用于改进策略）
- ✅ `signal.get-statistics` - 获取信号准确率统计

---

### 2. 数据库设计（database-design.md）

新增**trading_signals表**（第9张表）：

**核心字段**：
- 信号基本信息：signal_id, date, symbol, signal_type, price, confidence
- 信号原因：reasons（JSON数组）
- 操作者：operator（Agent-v2 / User）
- 执行状态：status, executed, executed_price, executed_time
- 盈亏信息：pnl_current, pnl_percentage, pnl_realized
- 错误标记：is_error, error_type, error_feedback

**索引优化**：
- `idx_signals_symbol_date` - 按股票和日期查询
- `idx_signals_type_status` - 按信号类型和状态筛选
- `idx_signals_operator_date` - 按操作者查询
- `idx_signals_executed` - 查询已执行的信号
- `idx_signals_error` - 查询错误信号

---

### 3. 前端原型设计（frontend-prototype-task-complete.md）

在**图表研究页面**增强中添加了**买卖点标注功能**：

#### 核心功能
1. **K线图标注**
   - 买入点：绿色向上箭头 ↑
   - 卖出点：红色向下箭头 ↓
   - 观望点：灰色圆点 •

2. **悬停详情卡片**
   - 显示：日期、价格、置信度、操作者
   - 信号原因列表（RSI、MACD等）
   - 执行状态和当前盈亏
   - 操作按钮：查看完整分析、标记错误

3. **筛选控制**
   - 按操作者：所有 / 仅Agent / 仅我的
   - 按状态：所有 / 仅已执行 / 仅待审批
   - 按时间：30天 / 90天 / 1年 / 全部

4. **买卖点列表**
   - 表格展示所有买卖点
   - 显示执行状态和盈亏
   - 可点击查看详情或标记错误

5. **准确率统计**
   - 买入信号准确率
   - 卖出信号准确率
   - 平均持仓时间
   - 平均收益率

---

## 🎯 功能价值

### 1. 验证量化信号
- 直观看到买卖点是否在合理位置
- 判断信号的时机是否正确

### 2. 学习和改进
- 分析错误的买卖点
- 标记错误类型（时机错误、价格错误、原因错误）
- 用于优化策略参数

### 3. 建立信任
- 看到Agent的决策过程
- 了解信号的置信度和原因
- 查看历史准确率

### 4. 快速决策
- 基于历史买卖点判断当前是否应该操作
- 对比Agent的判断和自己的判断

---

## 📊 数据流

```
1. Agent生成信号
   ↓
2. 调用 signal.record-signal 记录到数据库
   ↓
3. 前端调用 signal.get-trading-signals 获取信号
   ↓
4. 在K线图上标注买卖点
   ↓
5. 用户查看、验证、标记错误
   ↓
6. 调用 signal.mark-error 反馈
   ↓
7. 用于改进策略
```

---

## 📝 实现优先级

### P0（第1周）
- ✅ 后端：`signal.get-trading-signals` + `signal.record-signal`
- ✅ 数据库：创建 `trading_signals` 表
- ✅ 前端：K线图买卖点标注基础功能

### P1（第2周）
- ✅ 后端：`signal.mark-error` + `signal.get-statistics`
- ✅ 前端：悬停详情卡片、筛选控制、买卖点列表

### P2（第3周）
- ✅ 前端：准确率统计展示、交互优化
- ✅ 测试：完整的买卖点功能测试

---

## 🚀 下一步

所有文档已更新完毕，各Agent可以开始并行工作：

1. **Agent 1（后端）**: 实现4个signal API命令
2. **Agent 2（前端）**: 在图表研究页面添加买卖点标注
3. **Agent 3（数据库）**: 创建trading_signals表
4. **Agent 4（测试）**: 编写买卖点功能测试用例

---

## 📚 更新的文档

1. ✅ `docs/backend-api-spec.md` - 新增交易信号模块（4个API）
2. ✅ `docs/database-design.md` - 新增trading_signals表
3. ✅ `docs/frontend-prototype-task-complete.md` - 图表研究页面增加买卖点标注
4. ✅ `docs/task-assignment.md` - 更新实现优先级
5. ✅ `docs/kline-signal-feature-summary.md` - 本文档（功能总结）

---

**功能已完整添加到设计文档中！** 🎉
