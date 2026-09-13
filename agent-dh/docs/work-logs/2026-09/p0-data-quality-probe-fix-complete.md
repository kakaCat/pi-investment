---
id: wl-2026-09-p0-data-quality-probe-fix-complete
title: P0 数据质量探针修复完成报告
type: worklog
status: archived
updated: 2026-09-11
owners: [agent-dh]
tags: [worklog, 2026-09]
---

# P0 数据质量探针修复完成报告

## ✅ 本次完成（2026-09-11 22:30-00:45）

### 核心成果：P0 数据质量探针修复

**问题**：data_quality_report 报"7项全ok"，实测有4项问题
**根因**：wrap() 丢弃 tool_health 字段 + 探针判据过松 + 缺失关键探针

**修复**：
1. ✅ 修复 wrap() 保留 tool_health 字段
2. ✅ 加强 sector_analysis.window 探针（5 vs 60天 + top3比较）
3. ✅ 新增 3 个探针（factor资金字段、dividend_yield、barra小样本）
4. ✅ 创建回归测试（7个测试用例）

**效果对比**：
- 修复前：7ok/0degraded/0fail（假全绿）
- 修复后：**7ok/3degraded/0fail**（准确反映实际）
- sector窗口bug、dividend_yield null、barra小样本 **全部检测到** ✅

### 变更文件
```
packages/data-manager/src/tools/DataQualityReportTool/DataQualityReportTool.ts
  - 修复 wrap() 保留 tool_health 字段
  - 加强 sector_analysis 探针判据
  - 新增 3 个探针

packages/data-manager/tests/data-quality-probe.regression.test.ts
  - 新增回归测试
```

---

## 📋 P1/P2 任务规划（待新会话执行）

### 立即可执行（工作量小）
1. **P1-1: 暴露 stress-test / risk-parity 工具**
   - 后端 API 已有：`/api/risk/stress-test`、`/api/portfolio/risk-parity/optimize`
   - 需要：client 封装 + risk 插件注册
   - 工作量：30-60分钟

2. **P1-2: 调查 dividend_yield 为何为 null**
   - 当前：有分红流水，但 yield 字段为 null
   - 需要：定位是后端/前端/数据问题
   - 工作量：30-90分钟

### 需要架构设计（工作量大）
3. **P1-3: 判断结果自动对账**
   - 目标：把"观察/不交易"决策纳入 T+5/T+20 自动评估
   - 包含：missed_opportunity 检测
   - 工作量：3-5小时

4. **P1-4: 事件双轨合流**
   - 目标：stock_events + event_calendar 统一入口
   - 产出："未来 N 天全市场事件日历"
   - 工作量：2-3小时

### 需要后端改动
5. **P1-5: barra 小样本路径**
   - 目标：2只持仓时风险分解可用
   - 方案：单因子映射/收缩协方差
   - 工作量：后端3-5小时 + 前端1小时

### 数据问题（观察）
6. **sector_analysis 快照积累**
   - 状态：后端代码已修复，等待快照表积累历史
   - 方案：自然积累或手工回填
   - 优先级：P2

### 优化项（P2）
7. **minute_kline as_of 语义** - 文档 + 字段命名
8. **召回噪声治理** - 12万次检索、7%注入率

---

## 🎯 建议执行顺序

**新会话 1（2小时）**：
- P1-1: 暴露 stress-test / risk-parity（30-60min）
- P1-2: dividend_yield 调查修复（30-90min）

**新会话 2（3-4小时）**：
- P1-3: 判断结果自动对账（需要设计）

**新会话 3（2-3小时）**：
- P1-4: 事件双轨合流

**协调后端后**：
- P1-5: barra 小样本路径
- sector_analysis 快照回填

---

## 📊 当前状态

- ✅ **P0 完成**：探针系统重新可信
- 🔄 **P1 就绪**：任务已分类，执行路径明确
- 📋 **Token 使用**：105K/200K（建议新会话继续）

---

**下一步**：开启新会话，执行 P1-1 和 P1-2
