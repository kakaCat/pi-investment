# t-fb59e6 定义节点契约与产物模型（domain 层）

## 提示词

shared/protocol.ts：StageKey + StageDetail 判别联合；StageArtifact（含 confirmedAt/confirmedBy）+ STAGE_ARTIFACT_REQUIREMENTS；CATEGORY_FLOW_PROFILES 分类流程档案（每分类：启用阶段子集/必备产物/生效硬门）；HUMAN_ONLY 增加 brainstorming>planning、decomposing>implementing，SYSTEM 移除后者；StagePromptKey 映射；RequirementRecord 增加 projectId/parentId/artifacts；PlanTask 增加 executorHint；TaskRecord 增加 dependsSummary；schemaVersion 3→4

## 验收标准

编译通过；shape/转移表/分类档案齐备；老台账加载回归单测通过

## 执行记录

- ✓ 完成 w-8913546f · 09-15 17:36 → 09-15 17:51 · 手动

  w-8913546f [状态] → in_progress：开工 t1：domain 层契约定义，是 t2/t3/t5/t6 的公共依赖，由本窗口亲自做（窗口 session-8913546f-bd1a-4ca5-a737-deb0b429e5bf）
  w-8913546f [状态] → testing：t1 推进（窗口 session-8913546f-bd1a-4ca5-a737-deb0b429e5bf）
  w-8913546f [状态] → in_review：t1 推进（窗口 session-8913546f-bd1a-4ca5-a737-deb0b429e5bf）
  w-8913546f [状态] → done：t1 完成：domain 契约+schema v4，188 测试绿，类型零错误（窗口 session-8913546f-bd1a-4ca5-a737-deb0b429e5bf）
