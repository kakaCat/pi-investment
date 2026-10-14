# t-98fce1 scripts/tools 归位·研发

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
scripts/tools 归位·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-01T12:20:21.856Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

研发段：**先把卡片的三个前提逐个量了一遍，发现都不准**（说是可直删的 5 个脚本里有 3 个正被测试依赖），于是只做了真正安全又可入库的四件事——删掉 2 个确实没人用的脚本、把 2 个真测试从 scripts/ 移进 tests/（它们开始被收集且全过）、把 1 个"挂着 test 名其实是检查器"的脚本改名，并顺手修掉它一个让它长期假报失败的路径 bug。

### 完成项

- **实测推翻卡片三处前提**（详见 work-log）：① 卡说 5 个日期戳脚本 0 引用可直删，实测只有 2 个是 0 引用，另 3 个**正被 4 个测试文件 import**（审计 grep 范围漏了 `tests/`）；② 14 个 scripts/test_*.py 中 **11 个未被 git 跟踪**，`scripts/test_orm` 被文档引用 **34 次**（非卡说 10~11）；③ 卡说 7 个 _v2/_fixed 补丁产物，实测只有 **4 个**且全部未跟踪
- 删除 2 个真无引用的一次性脚本：`scripts/calibrate_20260723_{v13,v14}_return.py`（未跟踪 → 仅本地）
- 保留 3 个迁移脚本并实测可用：`migrate_20260720_multi_account` / `migrate_20260813_action_case_unify` / `migrate_20260813_scheduler_tasks` —— 它们是 4 个测试文件的夹具，删之会打断测试
- `git mv` 2 个真测试进 `tests/`：`test_batch_fundamentals_fix.py`、`test_stock_resolve_fix.py`（移动后 **6 passed**；全仓收集数 **6429 → 6435**）
- 把"名为 test 实为检查器"的 `scripts/test_migration_syntax.py` 改名为 `scripts/check_migration_syntax.py`（它不收集任何测试）
- **顺带修掉该检查器的真 bug**：它用 `Path(__file__).parent` 当仓库根，导致每一项都把仓库相对路径拼成 `scripts/application/...` 而报"文件不存在"——长期假报失败。修正后实跑输出 `🎉 所有检查通过！迁移成功！`，从任意 cwd 运行同样成立（说明那批 provider 迁移本来就是完成的）
- 结论写入跟踪文档：`docs/work-logs/2026-10/scripts-inventory-and-corrections.md`（含三处更正、处置清单、范围外余量、可复用教训、新脚本放置规范）
- 范围外如实登记：94 个平铺 .py 仅 **19 个受版本控制**（75 个未跟踪/被忽略）；剩余 11 个 test_*.py 全部未跟踪；4 个补丁产物全部未跟踪——这些都改不动仓库
- 验收①③④⑤逐条达成；②（5 个脚本）与"test_*.py 归零"两项按实测修订，未硬做会打断测试或改不了仓库的事

### 改动文件

- `scripts/check_migration_syntax.py`
- `docs/work-logs/2026-10/scripts-inventory-and-corrections.md`

---
