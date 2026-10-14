# t-fde9be 端到端验收、真实台账观察与回滚演练·复核

> 需求：REQ-261006093620-a315 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

## 在做什么
端到端验收、真实台账观察与回滚演练·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/<REQ>/design/` 逐条核对；`npx vitest run <相关测试文件>` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-06T02:11:56.862Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

第二段完成：休市日与回滚两条端到端探针均通过，免 reload 生效与可逆性得证。

### 完成项

- 休市日端到端探针（真仓储 + 真门 + 真库）：run.status=skipped、error=None、五键 result 齐全
- 回滚/免 reload 探针三步：trading-days→skipped、改 always→success、改回→skipped（可逆）
- 证明 FR-7：策略改一行即时生效，无需 POST reload、无需重启
- 生产回滚 SQL 已写入 verification.md（八行改回 always 即可）
- 如实登记探针首版缺陷：故意执行不存在的命令触发失败上报链，被 notify-guard 拦下（egress=0、用户无感知），已补两处桩后 intercepted=0

### 改动文件

- `docs/requirements/REQ-261006093620-a315/notes/test_e2e_holiday_skip_probe.py`
- `docs/requirements/REQ-261006093620-a315/notes/test_e2e_policy_toggle_probe.py`

### 下一步

第三段：观测留档与限制登记。

---
