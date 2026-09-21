/**
 * 阶段提示词键（REQ-422af1 t4 立，t7 收口删兼容壳）。
 *
 * 文本源在 domain/prompt/fragments/**（构建期内联进 generated/fragments.ts），取词唯一入口
 * 是 resolveStagePrompt（INV-1）。P0 期用于兜住冻结测试的兼容只读视图
 * `STAGE_PROMPTS` / `stagePromptFor` 已在 t7「冻结测试迁移」完成后**物理删除**：
 * 双入口会绕过路由（违反 INV-1），且它们只是派生的第二事实源。
 *
 * 本模块现在只保留"键"的类型与常量，供 shared/protocol 再导出。
 *
 * @module dsh-pmboard/domain/stage/StagePromptSpec
 */
/**
 * 六份阶段纪律提示词的键（无 draft——draft 无阶段纪律）。
 *
 * REQ-422af1 修（浏览器包回归）：本模块被 shared/protocol **值再导出**，而客户端要打包
 * shared/protocol —— 故它必须是**叶子**（零 import）。此前它 import domain/prompt/index，
 * 把 generated/fragments（全部提示词分片，约 +76KB）拖进了 lib/client.js。
 * 现权威定义在此，依赖方向为 prompt → stage（提示词域反向引用本模块）。
 */
export const ALL_STAGE_PROMPT_KEYS = [
  'brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'archived',
] as const

/** 键类型（从常量推导，避免第二事实源）。 */
export type StagePromptKey = (typeof ALL_STAGE_PROMPT_KEYS)[number]
