# t-0b6aaf 执行期接门与跳过落账（含 manual 旁路）·测试

> 需求：REQ-261006093620-a315 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

## 在做什么
执行期接门与跳过落账（含 manual 旁路）·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-06T02:00:23.312Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

测试段完成：合并回归 81 条全过、端到端探针通过、读数已留档。

### 完成项

- 合并回归 81 passed（基线 67 + t4 新增 8 + t5 新增 6），未降
- 本卡验收：test_scheduler_skip_ledger.py 6 passed
- 真端到端探针 1 passed（真仓储 + 真门 + 真库）
- 读数补入 notes/acceptance-run.md 的 t5 小节（含探针实际输出与夹具修正说明）
- notify-guard intercepted=0 egress=0

### 改动文件

- `docs/requirements/REQ-261006093620-a315/notes/acceptance-run.md`

### 下一步

t6（t-3a7ebb）：人工触发改投一次性 manual job。

---
