---
req: REQ-261006010812-cd19
kind: design
doc: design/test-cases
title: 审计自身的验证——三道自检、验收命令复跑清单、只读性回归
serves: FR-1, FR-2, FR-3, FR-5, FR-6
---

# 测试与验收（REQ-261006010812-cd19）

> 审计的"测试"不是测产品，而是**测这份报告能不能被复核**。三道自检 + 一张复跑清单。

## 1. 三道自检（serves: FR-5, FR-6）

- **serves: FR-5, FR-6**
- 报告落盘后，**先自检再提交**，任一不过即就地返工：

| # | 自检 | 判据（可机械执行） |
|---|---|---|
| S1 | 五节齐全 | `grep -c '^## ' audit-report.md` ≥ 5，且 `## 结论摘要`/`## 一致性矩阵`/`## 验收命令复跑`/`## 缺口清单`/`## 改进项` 逐节非空 |
| S2 | 无软判定词 | `grep -nE '基本一致|大致符合|疑似|应该没问题|预期通过' audit-report.md` 命中数 = 0 |
| S3 | 证据列不空 | 一致性矩阵每行证据列匹配 `^\[L[1-4]\]`；改进项每行「可证伪判据」列非空且含命令或断言 |

## 2. 验收命令复跑清单（serves: FR-3）

- **serves: FR-3**
- 被审设计 `design.md` §12 给出的 7 条命令，**逐条**进报告第 3 节；本审计预先登记预期形态
  （跑之前先写"要跑的是哪条、它想证什么"，避免事后挑好跑的去跑）：

| # | 命令（`quantsys-v2/` 下） | 想证的设计条款 | 已知风险 |
|---|---|---|---|
| C1 | `venv/bin/python -m pytest tests/live_trading/ tests/test_v13_scheduler.py -v` | FR-1/FR-2 失败可见性 | 用例可能需要 DB 或会外发（有 `notify_guard` 兜底） |
| C2 | `venv/bin/python tools/check_trading_day_judgment.py --dates 2026-10-05,2026-10-06,2026-10-07,2026-10-08` | FR-3 交易日判定 | **文件不存在**（E-3）→ 预期落 `不可跑`，并给纯函数复刻的 `L4` 替代 |
| C3 | `venv/bin/python tools/check_should_have_run.py` | FR-4/FR-8 漏跑盘点 | 该文件被 `.gitignore:85` 排除（E-4） |
| C4 | `venv/bin/python tools/check_strategy_config_effective.py` | FR-5 配置单源 | 同上（E-4） |
| C5 | `venv/bin/python -m pytest tests/regression/test_strategy_config_refactor.py -v` | FR-6 未接线链路已修实 | 该测试是否已改真断言 |
| C6 | `venv/bin/python -m pytest tests/services/test_pending_orders.py -v` | FR-7 挂单批量不中断 | 同上 |
| C7 | `venv/bin/python tools/reconcile_sim_account.py --account v13_simulation` | FR-10 账本自洽（超卖 0 行） | 只读，但依赖生产库连通 |

- 每条记录：`实跑/不可跑` + 真实退出码 + ≤80 字输出摘要（契约见 `interfaces.md` §6）。
- **不可跑 ≠ 跳过**：C2 这类必须给替代判据（纯函数复刻 + 标 `L4`），并在缺口清单里留一行。

## 3. 抽查复现用例（serves: FR-2, FR-5）

- **serves: FR-2, FR-5**
- 目的：证明"报告不是自说自话"。方法：从一致性矩阵里**固定抽 5 行**（第 1、5、9、13、17 行；
  不足则取全部），逐行按证据列原样复跑：

| 抽查 | 通过判据 |
|---|---|
| 证据为 `[L2] 路径:行` | 打开该行，内容与「说明」列一致 |
| 证据为 `[L1] 命令` | 原样执行，退出码/计数与报告所写一致（时间型数据允许数值变化，结论方向不得变） |
| 证据为 `[L3] 库查询` | 在报告所记时刻的语义下重跑，结论一致；数值差异需在报告里已声明为"截至时刻" |
| 证据为 `[L4] 推演` | 该行判定必须是 `无法判定`，否则抽查不通过 |

- 抽查结果写进报告 `## 逐条取证附录`（二级节），列出 5 行的抽查结论（逐行 `通过/不通过`）。

## 4. 只读性回归（serves: FR-2）

- **serves: FR-2**
- 开审前与收工后各跑一次：

```bash
git status --porcelain -- live_trading/ application/ infrastructure/ tools/ \
  | grep -v '^?? .*audit' ; echo "---"; git stash list | wc -l
```

- 通过判据：两次输出**逐字相同**（即审计没有给被审代码加改动、没有 stash 残留）。
- 若因跑 pytest 产生了 `__pycache__` 等噪声，须在报告里声明哪些是噪声、哪些是真实差异。

## 5. 验收命令汇总（本需求自身，serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6)

- **serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6**

```bash
# 报告存在且五节齐全（S1）
grep -c '^## ' docs/requirements/REQ-261006010812-cd19/audit-report.md      # >= 5
# 无软判定词（S2）
grep -cE '基本一致|大致符合|疑似|应该没问题|预期通过' docs/requirements/REQ-261006010812-cd19/audit-report.md   # 0
# 一致性矩阵行数与证据强度标注（S3）
grep -c '^\[L[1-4]\]' docs/requirements/REQ-261006010812-cd19/audit-report.md  # >= 矩阵行数
# 只读性回归（§4）
git status --porcelain -- live_trading/ application/ infrastructure/ tools/     # 与本轮开审前一致
```

- 期望：四条全部满足；任一条不满足 → 报告不合格，返工而非"说明一下"。
