# t-ab4c82 策略库治理清单（TEST 残留盘点 + unmeasured 补测可行性）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
策略库治理清单（TEST 残留盘点 + unmeasured 补测可行性）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：analysis
- 端侧：backend

## 得到什么结果
清单落 docs/requirements/REQ-261019144524-ec50/w4-strategy-cleanup.md，包含每条 TEST 策略的 id/名称/创建时间与处置建议；包含 evolution_run 降级原因的实测结论；执行 strategy_list 复核无策略被硬删

## 实施方案（implementation）
①strategy_list 全量分页拉取并分类；②抽查 evolution_run/回测接口可用性；③清单与建议落文档

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-19T14:39:56.808Z，窗口 session-503df447-3664-4823-ada8-9d779312d94a）

这一步做完，策略库治理有了可裁决的清单：父卡「125 条含 TEST 残留」的预期被证伪——主表现存仅 5 条、TEST 命名 0 条（09-13 已清 320 条），真正的残留是派生表孤儿数据（backtest_results 540 行 + evolution 两表 106 行悬空，且全部无 data_contracts 登记）；同时实证 14→101→5 两次库表变动无任何台账。补测可行性结论：回测通道可用，但 evolution_run 连续第 4 周因 schema 边界硬错误不可用、且「零交易」判据缺陷当日再次实证（实际 -23.18% 被判无信号），补测判据须禁用 totalTrades。复核判 fail 的验收路径偏离已修复：清单正本落 w4-strategy-cleanup.md，原 work-logs 底稿标注迁移指针。

### 完成项

- TEST 残留盘点：主表 0 条（09-13 已清 320 条），现存 5 条策略全量清单（id/名称/创建时间/处置建议）落 w4 §1；真正残留=派生表孤儿/悬空数据（backtest_results 540 行 + evolution 两表 106 行，均无 data_contracts 登记）落 w4 §2
- unmeasured 补测可行性结论：回测通道可用；evolution_run 第 4 周 schema 硬错误复现 +「零交易」判据缺陷当日再实证（实际 -23.18% 被判无信号）；补测序建议落 w4 §4
- 治理断链证据：14→101→5 两次库表变动无台账（w4 §3），支撑根因假设 4
- 验收路径偏离修复：w4-strategy-cleanup.md 落盘为正本，work-logs 底稿标注迁移指针；strategy_list 复核现存 5 条与盘点一致、本卡零删除

### 改动文件

- `docs/requirements/REQ-261019144524-ec50/w4-strategy-cleanup.md`
- `docs/work-logs/2026-10/strategy-library-governance-inventory.md`

### 下一步

按 DAG 推进下一张父卡 t-9bae04（经验库噪声处置方案）

---
