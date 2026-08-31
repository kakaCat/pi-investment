import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { MemoryClient } from '@pi-investment/agent-os-client';
import { experienceWritePrompt, type ExperienceWriteParams, type ExperienceWriteResult } from './prompt';

export class ExperienceWriteTool extends BaseTool<ExperienceWriteParams, ExperienceWriteResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'experience_write',
    category: 'memory',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = experienceWritePrompt;

  constructor(private memoryClient: MemoryClient) {
    super();
  }

  protected validate(params: ExperienceWriteParams): ValidationResult {
    const { symbol, scenario, outcome } = params;

    // 检查 symbol 不为空
    if (!symbol || symbol.trim().length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: '股票代码不能为空',
      };
    }

    // 检查 scenario 不为空
    if (!scenario || scenario.trim().length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'scenario',
        issue: '场景描述不能为空',
      };
    }

    // 检查 outcome 有效性
    const validOutcomes = ['profit', 'loss', 'neutral'];
    if (outcome && !validOutcomes.includes(outcome)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'outcome',
        issue: `无效的结果类型: ${outcome}`,
        expected: validOutcomes.join(', '),
      };
    }

    return { success: true };
  }

  protected async execute(params: ExperienceWriteParams, context: ToolContext): Promise<ExperienceWriteResult> {
    const { symbol, scenario, outcome, lesson, pnl_pct } = params;

    const timestamp = new Date().toISOString();
    const content = [
      `${symbol} 交易经验（${timestamp}）`,
      `场景：${scenario}`,
      outcome ? `结果：${outcome}` : null,
      typeof pnl_pct === 'number' ? `盈亏：${pnl_pct}%` : null,
      lesson ? `教训：${lesson}` : null,
    ].filter(Boolean).join('\n');

    const res = await this.memoryClient.write({
      title: `${symbol} ${outcome || ''} ${scenario}`.slice(0, 80),
      content,
      namespace: 'experience',
      tags: [symbol, outcome || 'neutral'].filter(Boolean),
      importance: outcome === 'loss' ? 0.8 : 0.6,
    });

    return {
      success: true,
      // 2026-08-31: 修复字段契约——Agent OS write 响应为 { memory: { id }, success }，
      // 此前读 res?.id 恒为空 → experience_id 永远空串。兼容 res.memory.id 与 res.id。
      experience_id: String(res?.memory?.id ?? res?.id ?? ''),
    };
  }

  protected wrap(data: ExperienceWriteResult, _context: ToolContext): ToolResponse<ExperienceWriteResult> {
    return {
      success: true,
      data,
    };
  }
}
