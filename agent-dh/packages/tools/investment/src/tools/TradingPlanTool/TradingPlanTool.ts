/**
 * TradingPlanTool - 交易计划工具（投资脑侧，REQ-261021222905-6dff t12）
 *
 * 契约与 agent-ts 的 trading_plan 工具一致（IF-17）：同一套 action 枚举、同一后端、
 * 同一错误透传口径。账户纪律（R-019）：缺省取本次实例投资账户，不写死单一账户名。
 */
import { BaseTool, DEFAULT_AGENT_ACCOUNT } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { tradingPlanPrompt, TradingPlanParams } from './prompt';

const ACTIONS = [
  'today', 'list', 'get', 'create', 'patch', 'apply', 'activate', 'pause',
  'resume', 'close', 'preview', 'stats', 'reflect', 'reflections', 'blocked_stats',
] as const;

export class TradingPlanTool extends BaseTool<TradingPlanParams, unknown> {
  protected readonly metadata: ToolMetadata = {
    name: 'trading_plan',
    category: 'trading',
    version: '1.0.0',
    timeoutMs: 20000,
  };

  protected readonly prompt = tradingPlanPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: TradingPlanParams): ValidationResult {
    if (!args.action || !ACTIONS.includes(args.action as any)) {
      return {
        success: false,
        errorType: 'INPUT_ERROR' as any,
        field: 'action',
        issue: `action 必须是 ${ACTIONS.join('|')} 之一`,
        received: String(args.action),
        expected: '受控枚举',
        example: 'today',
      };
    }
    const needId = ['get', 'patch', 'apply', 'activate', 'pause', 'resume', 'close',
      'preview', 'stats', 'reflect', 'reflections'] as const;
    if ((needId as readonly string[]).includes(args.action) && !args.plan_id) {
      return {
        success: false,
        errorType: 'INPUT_ERROR' as any,
        field: 'plan_id',
        issue: `${args.action} 需要 plan_id`,
        received: String(args.plan_id),
        expected: '正整数',
        example: '42',
      };
    }
    if (args.action === 'create' && (!args.name || !args.spec)) {
      return {
        success: false,
        errorType: 'INPUT_ERROR' as any,
        field: 'name/spec',
        issue: 'create 需要 name 与 spec',
        received: '缺失',
        expected: 'name + spec',
        example: '{name: "今日计划", spec: {...}}',
      };
    }
    return { success: true };
  }

  protected async execute(args: TradingPlanParams, _context: ToolContext): Promise<unknown> {
    const account = (args.account && args.account.trim()) || DEFAULT_AGENT_ACCOUNT;
    const id = Number(args.plan_id || 0);
    switch (args.action) {
      case 'today':
        return this.qv2.plansToday(account);
      case 'list':
        return this.qv2.listPlans(account, args.status);
      case 'get':
        return this.qv2.getPlan(id);
      case 'create':
        return this.qv2.createPlan({
          account,
          name: args.name,
          horizon: args.horizon || 'day',
          spec: args.spec,
          created_by: 'agent',
          actor: 'agent',
        });
      case 'patch':
        return this.qv2.patchPlan(id, {
          expected_version: args.expected_version,
          spec_patch: args.spec_patch,
          reason: args.reason,
          decision_audit_id: args.decision_audit_id,
          actor: 'agent',
        });
      case 'apply':
        return this.qv2.applyPlan(id, {
          expected_version: args.expected_version,
          reason: args.reason,
          hypothesis: args.hypothesis,
          decision_audit_id: args.decision_audit_id,
          actor: 'agent',
        });
      case 'activate':
        return this.qv2.activatePlan(id, {
          expected_version: args.expected_version, actor: 'agent',
        });
      case 'pause':
        return this.qv2.pausePlan(id, { reason: args.reason, actor: 'agent' });
      case 'resume':
        return this.qv2.resumePlan(id, {
          expected_version: args.expected_version, actor: 'agent',
        });
      case 'close':
        return this.qv2.closePlan(id, {
          reason: args.reason,
          close_disposition: args.close_disposition,
          actor: 'agent',
        });
      case 'preview':
        return this.qv2.compilePlanPreview(id);
      case 'stats':
        return this.qv2.planStats(id);
      case 'reflect':
        return this.qv2.recordPlanReflection(id, {
          answers: args.answers,
          verdict: args.verdict,
          reasoning: args.reason,
          actions: args.actions,
          period: args.period,
        });
      case 'reflections':
        return this.qv2.listPlanReflections(id);
      case 'blocked_stats':
        return this.qv2.blockedSignalStats();
      default:
        throw new Error(`未支持的 action: ${args.action}`);
    }
  }

  protected wrap(result: unknown, _context: ToolContext): ToolResponse<unknown> {
    return { success: true, data: result };
  }
}
