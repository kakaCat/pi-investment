# t-9b20eb scripts/tools 归位

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
scripts/tools 归位

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

按用户裁定**只做"可入库、零风险"那部分**（其余标的在版本控制之外，登记待办不硬做）：
① `scripts/` 下**已跟踪**的 `test_*.py` = **0**（实测：`git ls-files 'quantsys-v2/scripts/test_*.py'` 计数 0）。原验收写"`ls scripts/test_*.py | wc -l` = 0"**不可达成**：剩余 11 个全部未被 git 跟踪（`scripts/` 按 t-d4199a 裁定保持忽略），迁入 `tests/` 会让一批从未跑过的用例开始运行。
② 一次性脚本：**删 2 个**（`calibrate_20260723_{v13,v14}_return.py`，引用数 0、未跟踪）。原验收"5 个已删"**不成立**：另 3 个 `migrate_20260720_multi_account` / `migrate_20260813_action_case_unify` / `migrate_20260813_scheduler_tasks` **正被 4 个测试文件 import**（审计 grep 漏了 `tests/`），删之会打断测试——已保留并实测三者仍可导入。
③ 文档引用：`grep -rn "scripts/test_orm" --include='*.md'` 仍为 34 处且**全部有效**（那些文件未跟踪、仍在原处）。本卡移动/改名的 3 个文件旧路径引用 = **0**（实测无残留）。
④ `pytest --collect-only -q` 收集数 **6429 → 6435**（+6，来自移入的 2 个测试文件，移动后 **6 passed**）。
⑤ 额外修复：改名后的 `scripts/check_migration_syntax.py` 有真 bug（用 `Path(__file__).parent` 当仓库根 → 每项都报"文件不存在"），已修并实测输出 `🎉 所有检查通过`；从任意 cwd 运行同样成立。
⑥ 范围外登记（写入 `docs/work-logs/2026-10/scripts-inventory-and-corrections.md`）：94 个平铺 .py 中仅 19 个受版本控制、11 个未跟踪 test 文件、4 个未跟踪补丁产物的现状与理由。

## 实施方案（implementation）
① 删 5 个已确认 0 引用的日期戳脚本（calibrate_20260723_{v13,v14}_return.py、migrate_20260720_multi_account.py、migrate_20260813_{action_case_unify,scheduler_tasks}.py）；② 14 个误置 test_*.py 从 scripts/ git mv 到 tests/ 并更新文档引用（test_orm*.py 被文档引用 10~11 次，不可盲删）；③ 7 个 _v2/_fixed 补丁产物逐个反查调用方后处理；④ 新脚本一律进已有分类子目录（94 个仍平铺在 scripts/ 根）。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-01T12:29:17.893Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

这一步做完，变化是：**"散在脚本目录里的真测试"被归位、两个确认没人用的脚本被删、一个长期假报失败的检查器被修好**——两个真测试移进 tests/ 后开始被收集并通过（收集数 +6），而三个看着像一次性、其实被测试依赖的迁移脚本**用实验证明必须保留**（拿掉就 17 个报错）。同时把"这一大堆文件其实大多不在版本控制里"的现状如实写进了结论文档。

### 完成项

- **实测推翻卡片三处前提**（逐条留痕）：① "5 个日期戳脚本 0 引用可直删"→ 只有 **2 个**是 0 引用，另 3 个被 **4 个测试文件 import**（审计 grep 范围漏 `tests/`）；② "14 个 test_*.py 迁到 tests/"→ 其中 **11 个未被 git 跟踪**，`scripts/test_orm` 被文档引用 **34 次**；③ "7 个 _v2/_fixed 补丁产物"→ 实际只有 **4 个**且全部未跟踪
- 删 2 个真无引用的一次性脚本（未跟踪，仅本地）：`scripts/calibrate_20260723_{v13,v14}_return.py`
- 保留 3 个被测试依赖的迁移脚本，并**用反证实验钉死该决策**：临时拿掉 `migrate_20260720_multi_account.py` → 相关测试文件立刻出现 **17 errors**（import 失败）；恢复后 import 类错误 0
- `git mv` 2 个真测试进 `tests/`（`test_batch_fundamentals_fix` / `test_stock_resolve_fix`）：移动后 **6 passed**，全仓收集数 **6429 → 6435**；git 以 `R`（重命名）记录，历史可追溯
- 把"名为 test 实为检查器"的脚本改名为 `scripts/check_migration_syntax.py`（它不收集任何测试）
- **顺带修掉该检查器的真 bug**（`Path(__file__).parent` 当仓库根 → 每项报"文件不存在"，长期假报失败）：修正后实测 `🎉 所有检查通过！迁移成功！`，任意 cwd 均可运行——即那批 provider 迁移本来就是完成的
- 结论沉淀到跟踪文档 `docs/work-logs/2026-10/scripts-inventory-and-corrections.md`（65 行）：三处更正、处置清单、范围外余量（94 个平铺文件仅 19 个受版本控制等）、可复用教训（grep 范围即结论边界；"未跟踪"要先测）、新脚本放置规范（一次性→scripts/oneoff/ 且显式 git add -f；真测试必须放 tests/；检查器用 check_/verify_ 前缀）
- 诚实边界：本卡大头（75 个未跟踪文件、11 个未跟踪 test 文件、4 个未跟踪补丁产物）**在版本控制之外**，处置只改本地磁盘、仓库看不到差异——已如实登记而非假装完成
- 四张子卡（研发/联调/复核/测试）全部完成

### 改动文件

- `scripts/check_migration_syntax.py`
- `tests/test_batch_fundamentals_fix.py`
- `tests/test_stock_resolve_fix.py`
- `docs/work-logs/2026-10/scripts-inventory-and-corrections.md`

---
