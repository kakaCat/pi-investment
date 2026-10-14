# 独立评审报告 · REQ-261006010812-cd19

> 角色：本报告不复用提交者的自述结论，**逐条独立重查**后才采信。
> 重查时刻：2026-10-06 09:2x–09:5x（CST）；重查方式：新命令 + 新查询，不看提交者的中间输出。

## 1. 评审范围

被评审对象：本次审计的四份证据文件与最终报告（`evidence/a1~a4`、`audit-report.md`），
及其对 REQ-261004154902-a7cd 的判定。评审问题：**结论是否可被第三方按原文复现**。

## 2. 逐条独立重查（重查项 → 结果）

| # | 被评审结论 | 重查方式 | 结果 |
|---|---|---|---|
| 1 | M-06 休市日仍记 success | 重新查库：`select status,result::text from quant.scheduler_runs where id=3375` 并展开 JSON | **成立**：`status='success'`，`result.details.details.check.status='skipped'`、`reason='not_trading_day'` |
| 2 | M-12 `pending-orders-match` 未落地 | 重跑 `select count(*) … where name like '%pending%'` | **成立**：0 行 |
| 3 | M-23 raw 超卖仍 4 行 | 重跑净额 `<0` 聚合计数 | **成立**：4 只（300045/300469/300561/300765） |
| 4 | M-25 `V13_CHAIN_STRICT` 未接线 | 重跑 `grep -rn V13_CHAIN_STRICT --include=*.py` | **成立**：0 命中 |
| 5 | G-1 风险检查调用不存在的方法 | 重跑方法定义搜索 + 定位到 `SimulationORMRepository` 类内 | **成立**（并修正口径：全局唯一命中是无关的 FastAPI 路由函数 `p2_batch2_async.py:79`） |
| 6 | G-3 盘中无止损 | 重查 `intraday_monitor.py:77` 与 `rule_guard.guard_account_applicable` | **成立**：账户写死 `rotation_main`；策略账户被拒 |
| 7 | G-4 载体不在版本控制 | 重跑 `git status` / `git check-ignore -v` / `ls` | **成立**：`??` 整目录、`.gitignore:85`、工具不存在 |
| 8 | G-5 盘点器报漏跑 | 重跑 `tools/check_should_have_run.py` | **成立**：exit 2、漏跑 1（`daily-strategy-validation`） |
| 9 | G-7 v14 声明失真 | 重数 `v14_p0_valid_factors.json` 与配置值 | **成立**：75 vs 78 |
| 10 | G-8 无假绿灯结构门禁 | 重查 `pytest.ini` | **成立**：无 `filterwarnings` |
| 11 | R-1 设计定标自相矛盾 | 重跑 `TradingDayGuard.check('2026-10-08')` 与纯函数判据 | **成立**：check → False（`source=future`）；纯函数冻结 today → True |
| 12 | 只读性（未改被审对象） | 重跑全仓 `git status --porcelain` 计数 | **成立**：128 = 开审前 128 |

## 3. 未采信 / 已驳回的项

- **未采信**：`tools/reconcile_sim_account.py` 的 exit 0 与「✅ 自洽」结论 —— 评审只把它当"工具口径"，
  另以 raw SQL 复核，发现超卖仍 4 行；因此报告把该条判为「已实现但语义偏离」而非「一致」。
- **未采信**：设计文档自述的「回滚 = git revert」与「判据命令可跑」—— 均以 git/文件系统事实驳回。
- **未主张**：探活杀进程告警、missed 落库端到端 —— 二者需要生产副作用（D-3 禁止），
  评审不把它们写成"通过"，报告中相应判定为 `无法判定`。

## 4. 评审结论

- 四份证据文件的 12 项关键结论**全部可复现**；1 项（G-1）在评审中被补精了口径（不影响判定）。
- 报告的一级结论（已实现但语义偏离 + 三条最重发现）**与证据一致**，未发现夸大或未列反证。
- 剩余不确定项已显式标注（M-11 无法判定、C2 不可跑的替代判据），无「静默降级」。
- **评审判定：通过**（可作为人工验收的输入，但验收结论仍由人作出）。
