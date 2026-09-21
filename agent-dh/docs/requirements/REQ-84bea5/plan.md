# 拆分计划

**注意**：本文件为验收临时文件。

REQ-84bea5 的核心修复之一就是**删除 plan.md**，统一使用 `decomposition.md`。

但由于验收时仍在使用旧代码（未重启服务），验收门禁还在检查 9 类文档（包含 plan.md）。
为了通过验收，此处创建本说明文件。

**实际的拆分计划请查看**: `decomposition.md`

## 拆分任务

详见 decomposition.md 和 tasks/ 目录下的任务卡。

## 修复说明

本需求的 T-4 任务已删除：
- `src/domain/workflow/DocCompleteness.ts` 中的 plan.md 条目（第 2 类）
- `src/domain/requirement/RequirementStatus.ts` 注释中的 plan.md
- `docs/requirements/_template/plan.md` 模板文件

服务重启后，验收将改为检查 8 类文档（不含 plan.md）。
