# t-af8fa3 让异常检测真的运行，并输出可区分的三态·复核

> 需求：REQ-261006133733-1fdf 异常值检测静默失效：成交量段迭代错对象（每只必抛错、被 except 吞成无异常）

## 在做什么
让异常检测真的运行，并输出可区分的三态·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/<REQ>/design/` 逐条核对；`npx vitest run <相关测试文件>` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-06T05:44:03.156Z，窗口 session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6）

复核结论：三态与质量分四态逐条兑现，无偏离；两条低影响观察已登记不改。

### 完成项

- 逐条对照 design/interfaces.md §1 三态表：A/B/C 三态八键实测齐备，has_anomalies is False 只在 A 态出现
- B 态保留既有 message 文案（Insufficient data for anomaly detection）逐字未变；新增键只增不改
- C 态实测：ok=False、has_anomalies=None、unknown_reason=RuntimeError: boom、error 同值；方法不抛
- 质量分四态独立复算：有异常 2/40=5% → 80.0；确无异常 → 100；数据不足（剔除归一）→ 100；检测失败（分量 0）→ 80.0
- 静态：data_validator 内 has_anomalies 无真值判断（仅 is True/is False/is None 与字面赋值）
- 无偏离：实现与 interfaces.md §1–§2 逐条一致
- 观察·低（登记不改）：若取数本身抛错（比本缺陷更严重），get_data_quality_score 仍走既有外层 except → 0.0；该行为未改，属计划外
- 观察·低（登记不改）：数据不足时「剔除归一」在覆盖率/重复率满分情形下得 100——符合「不奖不罚」设计，但会让此类股票的分数与「确无异常」相同；差异只在 anomaly_unknown_reason 计数上体现
- 模板不符：本卡复核 acceptance 的 npx vitest 不适用本仓 Python 栈，改用 pytest 等价口径

### 下一步

测试子卡复跑既有回归与三态探针；新增用例文件由 t3 承载。

---
