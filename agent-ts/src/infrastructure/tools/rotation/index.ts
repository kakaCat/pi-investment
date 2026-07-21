/**
 * Rotation Tools - 策略轮动决策工具链
 *
 * 四步决策链：
 * 1. rotation_proposal  — 获取轮动方案（市场风格 + 策略表现 + 建议）
 * 2. rotation_simulate  — 模拟执行（不真正执行，查看影响）
 * 3. rotation_execute   — 真正执行（approve/partial/reject）
 * 4. rotation_verify    — 验证效果（预期 vs 实际）
 *
 * 每个工具都是反馈节点：返回结构化上下文 + 下一步建议
 */
export { rotationProposalTool } from "./rotation-proposal-tool.js";
export { rotationSimulateTool } from "./rotation-simulate-tool.js";
export { rotationExecuteTool } from "./rotation-execute-tool.js";
export { rotationVerifyTool } from "./rotation-verify-tool.js";
