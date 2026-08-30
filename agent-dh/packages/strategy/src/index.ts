/**
 * Strategy Plugin - 策略插件
 *
 * 提供策略执行、回测、筛选、板块轮动等功能的插件
 *
 * @module @pi-investment/strategy
 * @version 1.0.0
 * @description
 * 策略插件是 Agent-DH 的核心功能模块之一，提供以下能力：
 *
 * 1. **策略执行** (StrategyExecuteTool)
 *    - 执行预定义的交易策略
 *    - 支持实时和模拟交易
 *
 * 2. **策略优化** (StrategyOptimizeTool)
 *    - 策略参数优化
 *    - 回测验证
 *
 * 3. **机会扫描** (OpportunityScanTool)
 *    - 扫描市场交易机会
 *    - 基于技术指标和基本面分析
 *
 * 4. **股票筛选** (ScreeningTool)
 *    - 多维度股票筛选
 *    - 自定义筛选条件
 *
 * 5. **轮动提议** (RotationProposalTool)
 *    - 生成板块轮动建议
 *    - 基于市场趋势分析
 *
 * 6. **轮动模拟** (RotationSimulateTool)
 *    - 模拟轮动策略效果
 *    - 风险评估
 *
 * 7. **轮动执行** (RotationExecuteTool)
 *    - 执行板块轮动交易
 *    - 实时监控
 *
 * @architecture
 * 所有工具已重构为 BaseTool 架构 (2026-08-28)
 * - 统一的三阶段执行流程：validate → execute → wrap
 * - 标准化的错误处理
 * - 类型安全的参数和返回值
 *
 * @dependencies
 * - @deepseek-ai/cordis: 插件系统框架
 * - @pi-investment/quantsys-v2-client: 量化系统 V2 客户端
 * - @pi-investment/core-tool: 工具基础设施
 *
 * @example
 * ```typescript
 * // 在 agent-dh 中使用策略插件
 * import StrategyPlugin from '@pi-investment/strategy';
 *
 * app.plugin(StrategyPlugin, {
 *   quantsysV2: {
 *     baseURL: 'http://localhost:5001',
 *     timeout: 30000,
 *   }
 * });
 * ```
 */

import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

import { createStrategyExecuteTool } from './tools/StrategyExecuteTool';
import { createStrategyOptimizeTool } from './tools/StrategyOptimizeTool';
import { createOpportunityScanTool } from './tools/OpportunityScanTool';
import { createScreeningTool } from './tools/ScreeningTool';
import { createRotationProposalTool } from './tools/RotationProposalTool';
import { createRotationSimulateTool } from './tools/RotationSimulateTool';
import { createRotationExecuteTool } from './tools/RotationExecuteTool';

/**
 * 策略插件配置接口
 */
export interface Config {
  /**
   * QuantsysV2 客户端配置
   */
  quantsysV2?: {
    /**
     * QuantsysV2 API 基础 URL
     * @default 'http://localhost:5001'
     */
    baseURL?: string;

    /**
     * API 请求超时时间（毫秒）
     * @default 30000
     */
    timeout?: number;
  };
}

/**
 * Strategy Plugin for Agent-DH
 *
 * 策略执行、回测、筛选、板块轮动插件
 *
 * Refactored to BaseTool architecture (2026-08-28)
 *
 * @class StrategyPlugin
 * @extends {Service}
 *
 * @remarks
 * 该插件依赖 'tools' 服务进行工具注册
 * 所有策略工具都通过 QuantsysV2Client 与后端通信
 */
export default class StrategyPlugin extends Service {
  /**
   * 声明依赖的服务
   * 需要 'tools' 服务来注册策略工具
   */
  static inject = ['tools'];

  /**
   * 插件配置 Schema
   * 使用 Schemastery 进行配置验证和类型推导
   */
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  /**
   * QuantsysV2 客户端实例
   * 用于与量化系统后端通信
   * @private
   */
  private qv2: QuantsysV2Client;

  /**
   * 构造函数
   *
   * @param ctx - Cordis 上下文，提供插件系统功能
   * @param config - 插件配置
   *
   * @remarks
   * 构造函数执行以下操作：
   * 1. 调用父类构造函数，注册服务名称 'strategy'
   * 2. 初始化 QuantsysV2Client 实例
   * 3. 注册所有策略工具到 tools 服务
   */
  constructor(ctx: Context, config: Config) {
    super(ctx, 'strategy');

    // 初始化 QuantsysV2 客户端
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });

    // 注册所有策略工具
    this.registerTools();
  }

  /**
   * 注册所有策略工具
   *
   * @private
   *
   * @remarks
   * 注册以下 7 个策略工具：
   *
   * 1. strategy_execute - 策略执行
   * 2. strategy_optimize - 策略优化
   * 3. opportunity_scan - 机会扫描
   * 4. screening - 股票筛选
   * 5. rotation_proposal - 轮动提议
   * 6. rotation_simulate - 轮动模拟
   * 7. rotation_execute - 轮动执行
   *
   * 所有工具都遵循 BaseTool 架构，提供统一的接口和错误处理
   */
  private registerTools() {
    const { ctx, qv2 } = this;

    // 注册策略执行工具
    ctx.tools.register(createStrategyExecuteTool(qv2));

    // 注册策略优化工具
    ctx.tools.register(createStrategyOptimizeTool(qv2));

    // 注册机会扫描工具
    ctx.tools.register(createOpportunityScanTool(qv2));

    // 注册股票筛选工具
    ctx.tools.register(createScreeningTool(qv2));

    // 注册轮动提议工具
    ctx.tools.register(createRotationProposalTool(qv2));

    // 注册轮动模拟工具
    ctx.tools.register(createRotationSimulateTool(qv2));

    // 注册轮动执行工具
    ctx.tools.register(createRotationExecuteTool(qv2));
  }
}
