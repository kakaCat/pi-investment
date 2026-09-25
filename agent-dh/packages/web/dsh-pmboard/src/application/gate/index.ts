/**
 * 门禁系统统一导出（REQ-260925212722-96e7）
 *
 * 提供统一的门禁调用接口，集中导出所有门禁函数和类型定义。
 *
 * @module dsh-pmboard/application/gate
 */

// 导出门禁检查函数
export { designGateCheck } from './design-gate.js'
export { taskCoverageGateCheck } from './task-coverage-gate.js'
export { acceptanceGateCheck } from './acceptance-gate.js'

// 导出门禁结果类型（从任意一个门禁文件导出即可，它们共享同一接口定义）
export type { GateResult } from './design-gate.js'
