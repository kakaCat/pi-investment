# t-b1b15e 回测窗口末强制平仓计账与口径字段·复核

> 需求：REQ-261020014122-d659 回测判据与 evolution_run schema 修复（解除策略补测阻塞）

## 在做什么
回测窗口末强制平仓计账与口径字段·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-20T00:58:50.455Z，窗口 session-503df447-3664-4823-ada8-9d779312d94a）

复核：diff 与设计契约逐条对齐，副作用边界与调用方零越界

### 完成项

- git diff 逐行复核：强制平仓段与 design/interfaces.md §2.2 契约一致（末日收盘价/加权平均入场/pnl 不含卖出费/tiers 同构/forced_close 标记）
- 副作用边界复核通过：cash 与 equity_curve 零改动；空 signals_df 走 _empty_metrics 也恒含两新键；价格校验错误路径（success:False）不受影响
- 确认 strategy_evolution_service.py 零改动（MIN_TRADES 判据随输入修复自愈）

### 下一步

测试段：C1-C3 终验

---
