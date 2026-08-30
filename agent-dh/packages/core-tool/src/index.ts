/**
 * Agent-DH 工具框架核心
 *
 * 提供 BaseTool 抽象基类，所有工具必须继承此类。
 * 框架强制执行三个步骤：校验参数、执行任务、包装返回数据。
 */

export * from './types';
export { BaseTool } from './BaseTool';
export { sanitizeLossless, toSnake } from './lossless';
