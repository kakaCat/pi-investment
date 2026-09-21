import { BaseTool, DEFAULT_AGENT_ACCOUNT } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { corePlanPrompt, CorePlanParams, CorePlanResult } from './prompt';

/**
 * CorePlanTool - 读取投资脑建仓计划（只读）
 *
 * 为什么需要它（B8，2026-09-13 w-a9ec14d7）：
 * 三个例行任务原先靠**硬编码文件路径**直读 config/core_plan.json，既读不出计划陈不陈，
 * 也算不出 core-plan 任务自己要求的"与当前持仓的差额"。本工具把计划 + 新鲜度 + 差额一次给全。
 *
 * 只读：不触发重新生成（生成参数集已审批）。
 */
export class CorePlanTool extends BaseTool<CorePlanParams, CorePlanResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'core_plan',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = corePlanPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: CorePlanParams): ValidationResult {
    if (args.account_name !== undefined && args.account_name !== null) {
      if (typeof args.account_name !== 'string' || args.account_name.trim() === '') {
        return {
          success: false,
          errorType: 'INPUT_ERROR' as any,
          field: 'account_name',
          issue: 'account_name 必须是非空字符串',
          received: String(args.account_name),
          expected: '非空字符串',
          example: 'agent_brain',
        };
      }
    }
    return { success: true };
  }

  protected async execute(args: CorePlanParams, _context: ToolContext): Promise<CorePlanResult> {
    // TODO: 处理非200响应 - 添加错误处理或降级逻辑（404/500等），参考 pe_percentile 改进方案
    // 每个工具的业务语义不同，需要根据具体场景设计降级策略
    // 账户纪律（R-019）：缺省 = 本实例投资账户（工具层默认），显式传入以传入为准。
    // 后端会把它与**计划文件自身记录的账户**比对：不一致时返回 account_mismatch=true
    // 且不给差额（计划只覆盖单一账户，跨账户算差额是错数据）。不静默。
    const account = (args.account_name && args.account_name.trim()) || DEFAULT_AGENT_ACCOUNT;
    const result = await this.qv2.getCorePlan(account);
    return result as unknown as CorePlanResult;
  }

  protected wrap(result: CorePlanResult, _context: ToolContext): ToolResponse<CorePlanResult> {
    // ⚠️ available=false（文件缺失/无法解析/账户不匹配）**按成功返回**：
    // 它带 unavailable_reason，是有信息量的正常结果，由模型据此决策（停止/上报/换账户）。
    // 若包装成工具错误，模型只会看到"调用失败"，反而丢掉原因。
    return { success: true, data: result };
  }
}
