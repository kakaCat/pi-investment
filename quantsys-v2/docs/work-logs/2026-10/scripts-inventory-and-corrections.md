# scripts / tools 清点与三处前提更正

**日期**: 2026-10-01
**需求**: REQ-261001145152-3982 · 任务 t-9b20eb（scripts/tools 归位）
**结论一句话**: 本卡的四个前提里**三个与实测不符**；真正可入库且零风险的处置只有 4 件小事，
其余标的都在版本控制之外（`scripts/` 按 t-d4199a 裁定保持忽略）。

---

## 一、实测结论（与卡片/审计的三处偏差）

| 卡片/审计的说法 | 实测 | 差在哪 |
|---|---|---|
| 「5 个日期戳一次性脚本**已确认 0 引用**，直删」 | 只有 **2 个**是 0 引用；另 **3 个正被 4 个测试文件 import** | 审计的 grep 范围是 `docs/ infrastructure/ deployment/ config/ ~/Library/LaunchAgents`，**漏了 `tests/`**（引用恰好都在那里） |
| 「14 个 `test_*.py` 误置在 `scripts/`」 | 其中 **11 个未被 git 跟踪**；`scripts/test_orm` 被文档引用 **34 次**（不是 10~11 次） | 引用计数与跟踪状态都需要实测 |
| 「7 个 `_v2`/`_fixed` 补丁产物」 | 只找到 **4 个**，且**全部未跟踪** | 审计列举时混入了不存在的名字（`migrate_new_tables.py` 等） |

被测试 import 的 3 个脚本（**必须保留**，它们是测试夹具）：

```
tests/test_multi_account_domain.py      → scripts.migrate_20260720_multi_account.run_migration
tests/infrastructure/test_scheduler_misfire.py      → scripts.migrate_20260813_scheduler_tasks.run_migration
tests/infrastructure/test_action_case_unify.py      → scripts.migrate_20260813_action_case_unify.run_migration
tests/live_trading/test_trade_action_case.py        → 同上
```

## 二、本次实际处置（可入库且零风险）

1. **删除 2 个真·无引用脚本**（未跟踪，仅本地）：`scripts/calibrate_20260723_{v13,v14}_return.py`。
2. **`git mv` 2 个真测试进 `tests/`**：
   `test_batch_fundamentals_fix.py`、`test_stock_resolve_fix.py`（移动后各 3 条，共 **6 passed**）。
   收益：`pytest --collect-only` 收集数 **6429 → 6435**。
3. **改名 1 个"名为 test 实为检查器"的脚本**：
   `scripts/test_migration_syntax.py` → `scripts/check_migration_syntax.py`（它不收集任何测试）。
4. **修掉该检查器的一个真 bug**：它用 `Path(__file__).parent` 当仓库根，于是把
   `application/services/...` 拼成 `scripts/application/services/...`，**每一项都报
   "No such file or directory"**——长期假报失败。改为 `Path(__file__).resolve().parent.parent`
   后实跑输出 `🎉 所有检查通过！迁移成功！`，且从任意 cwd 运行都成立。
   （即：那批 provider 迁移本来就是完成的，红灯是脚本自己的问题。）

以上第 2~4 项均已入库；第 1 项因文件未被跟踪，只改本地磁盘。

## 三、本次范围之外（如实登记，避免"看起来做完了"）

| 标的 | 数量 | 为什么不做 |
|---|---|---|
| `scripts/` 根下平铺 `.py` | 94 个（**仅 19 个已跟踪**，75 个未跟踪/被忽略） | 75 个不在版本控制内 → 重排只改本地磁盘、仓库看不到差异 |
| `scripts/test_*.py` | 剩 **11 个**（全部未跟踪） | 同上；且它们从未被 pytest 收集过，贸然迁入 `tests/` 会让一批从未跑过的用例开始运行并可能失败 |
| `_v2`/`_fixed` 补丁产物 | 4 个（全部未跟踪） | 未跟踪 → 删除无法入库；其中 `fetch_stock_news_fixed.py` 还被 `tests/test_stock_data_fix.py` 当路径字符串引用 |

## 四、教训（可复用的判定纪律）

1. **grep 范围就是结论的边界**：写「已确认 0 引用」时必须列出扫过的目录。本次审计漏了
   `tests/`，于是把 3 个**测试夹具**误判成可直删的一次性脚本——按原卡执行会**打断 4 个测试文件**。
2. **"未跟踪"要先测**：同一目录里 94 个文件只有 19 个受版本控制，不先测就会把
   "改本地磁盘"当成"完成了一项工程任务"。
3. **迁移类脚本不能只按 docs 引用判定**：`migrate_*` 常被测试当夹具 import，
   判活要看 `tests/` 与 `scripts/` 自身，而不是只看文档与业务代码。

## 五、后续规范（新脚本放哪）

- 一次性脚本 → `scripts/oneoff/`（或 `tools/oneoff/`），并**显式 `git add -f`**——
  `scripts/` 整体被忽略（t-d4199a 裁定：scripts/ 属一次性资产，保持忽略、不追溯删除已入库的 80 个）。
- 真·测试文件必须放 `tests/`（`test_` 前缀即被 pytest 收集，放 `scripts/` 等于永不运行）。
- 检查器/运维脚本用 `check_*` / `verify_*` / `diagnose_*` 命名，**不要用 `test_` 前缀**。
