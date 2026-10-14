# t-f7cd30 规则写入口缺省显式化（含批量与输入校验）·测试

> 需求：REQ-261007133807-eda6 「何时叫 agent」判据收敛与可见化（升级路径单一入口）

## 在做什么
规则写入口缺省显式化（含批量与输入校验）·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-07T11:05:26.630Z，窗口 session-f9c75862-cab1-4a4d-b7b3-9d69c6c42d49）

t10 测试段完成：10 passed，库回读证明缺省落显式值；误建的生产库探针已清理。

### 完成项

- tests/adapters/test_watch_rules_api_policy.py → 10 passed（含新增的库回读用例）
- 回读证据：库中 escalation_policy = {auto_escalate: true, anomaly_change_pct: 5.0}（非 NULL/{}）
- 测试库自清理为零残留（规则 0 / 触发 0）
- 如实声明一处失误：先前用独立 python 探针跑路由，PGDATABASE 被 .env 覆盖，误在生产库建了 2 条探针规则（id 33/34）——已逐条删除并复核残留 0；教训：应用级探针只能在 pytest 内跑（conftest 负责切库）
- 追加同类防线：把「库回读」写进用例，不再依赖手工脚本

### 改动文件

- `tests/adapters/test_watch_rules_api_policy.py`

### 下一步

父卡 t-9cd059 收尾。

---
