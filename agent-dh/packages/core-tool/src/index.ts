/**
 * Agent-DH 工具框架核心
 *
 * 提供 BaseTool 抽象基类，所有工具必须继承此类。
 * 框架强制执行三个步骤：校验参数、执行任务、包装返回数据。
 */

export * from './types';
export { BaseTool } from './BaseTool';
export { sanitizeLossless, toSnake } from './lossless';
// 账户单一事实源（2026-09-13 w-c8cae280：取代散落 30 处的 'agent_virtual'/'agent_brain' 字面量）
export { DEFAULT_AGENT_ACCOUNT } from './account';
// 风控输入可信度闸门（2026-09-11 提升为共享：M4 熔断与 regime_position_limit 共用，避免逻辑漂移）
export { assessDrawdownTrust, recomputeMaxDrawdown, assessBreakerTrigger, BREAKER_THRESHOLD_PCT, MIN_NAV_POINTS, DRAWDOWN_TOLERANCE_PP } from './drawdownTrust';
