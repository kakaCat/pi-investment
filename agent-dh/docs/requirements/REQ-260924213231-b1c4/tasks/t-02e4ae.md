# t-02e4ae 投影逐份登记态到 reqboard_status·研发

> 子卡（父卡 t-7e9633 · 阶段 dev） ｜ 状态：done ｜ 本文件由收口窗口按台账渲染（台账是唯一事实源）

## 在做什么
投影逐份登记态到 reqboard_status·研发

## 解决什么问题
子卡阶段：研发

## 得到什么结果（验收标准）

本卡为该父卡的研发子卡，交付物 = 父卡验收口径：npx vitest run tests/tools-status.test.ts tests/design-registration.test.ts tests/output-contract.test.ts 全绿；design_docs[] 的 on_disk/registered/confirmed 三态与磁盘+台账逐份一致；本卡的改动清单与自测输出见 docs/requirements/REQ-260924213231-b1c4/tasks/t-02e4ae.md

## 实施方案
改 packages/web/dsh-pmboard/src/application/internal/design-docs.ts（designDocRegistration 合并磁盘/产物簿/确认章）、packages/web/dsh-pmboard/src/application/query/QueryState.ts、packages/web/dsh-pmboard/src/tools/StatusTool/StatusTool.ts（输出 schema 增 design_docs[]）；回归 packages/web/dsh-pmboard/tests/tools-status.test.ts。

[子卡阶段·研发] 只做本阶段；验收：改动已落盘，相关测试或命令跑通并附输出摘要

## 执行与完工记录
- workflow run：2026-09-25 00:01:13（stopReason=completed，产出非空=True）
- 改动文件：
  - packages/web/dsh-pmboard/src/application/internal/design-docs.ts
  - packages/web/dsh-pmboard/src/application/query/QueryState.ts
  - packages/web/dsh-pmboard/src/tools/StatusTool/StatusTool.ts
  - packages/web/dsh-pmboard/tests/tools-status.test.ts
- 完成项：
  - design-docs.ts：新增端口级投影 `DesignDocScanPort` + `designDocNamesOf` + `designDocRegistrationOf`（扫 design/ 目录 + 读 requirement.md front-matter 策略 + `designDocRegistration` 三源合成），扫描口径与 reqboard_submit(kind=design) 的 designDocNames 一致，避免两处投影两套真相
  - QueryState.ts：绑定需求处（open[0]）计算 design_docs，并在返回体新增 `design_docs` 键；未绑定窗口返回空数组（不瞎报）
  - StatusTool.ts：output.schema 增 `design_docs[]`（name/path/on_disk/registered/confirmed/exempted/conditional），满足 additionalProperties:false 的输出契约
  - tests/tools-status.test.ts：新增 4 条回归用例——①未登记/待确认/已落章/缺失 四态逐份与磁盘+台账一致（行集与顺序为 feature 必交 5 份）②front-matter sides=frontend 出条件必交项、design_exempt 带豁免理由 ③未绑定窗口 design_docs=[] ④未知/缺 category 只报磁盘额外件
- 执行段：1 次（末次 2026-09-24 23:57:01，outcome=succeeded）
