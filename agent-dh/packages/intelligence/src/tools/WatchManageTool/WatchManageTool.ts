import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { watchManagePrompt, type WatchManageParams } from './prompt';

export class WatchManageTool extends BaseTool<WatchManageParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'watch_manage',
    category: 'intelligence',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = watchManagePrompt;

  constructor(private qv2Client: QuantsysV2Client) {
    super();
  }

  protected validate(params: WatchManageParams): ValidationResult {
    const { action, rule_id, name, symbol, condition } = params;

    // 2026-08-27：前端参数校验（此前缺字段直达后端才报 400，错误信息晦涩）
    if (action === 'create') {
      const missing: string[] = [];
      if (!name) missing.push('name（规则名称）');
      if (!symbol) missing.push('symbol（股票代码）');
      if (!condition) missing.push('condition（触发条件）');

      if (missing.length > 0) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          issue: `watch_manage create 缺少必填参数: ${missing.join('、')}。示例: action=create, name="茅台突破2000", symbol="600519", condition="price>2000"`,
        };
      }

      // 校验 condition 格式
      const validConditions = [
        /^price\s*>\s*\d+(\.\d+)?$/,
        /^price\s*<\s*\d+(\.\d+)?$/,
        /^change_pct\s*>\s*-?\d+(\.\d+)?$/,
        /^change_pct\s*<\s*-?\d+(\.\d+)?$/,
      ];

      const isValidCondition = validConditions.some(regex => regex.test(condition));
      if (!isValidCondition) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          issue: `condition 格式错误。支持格式：price>100、price<90、change_pct>5、change_pct<-3`,
        };
      }
    } else if (['enable', 'disable', 'delete'].includes(action)) {
      if (!rule_id) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          issue: `watch_manage ${action} 缺少必填参数: rule_id。先用 watch_list 查询规则 ID`,
        };
      }
    }

    return { success: true };
  }

  protected async execute(params: WatchManageParams, context: ToolContext): Promise<any> {
    const result = await this.qv2Client.manageWatchRule(params);
    return {
      success: true,
      rule_id: result?.id ?? result?.rule_id,
      action: params.action,
      message: params.action === 'create'
        ? `规则已创建 (ID: ${result?.id ?? 'unknown'})`
        : `规则已${params.action === 'enable' ? '启用' : params.action === 'disable' ? '禁用' : '删除'}`,
      data: result,
    };
  }

  protected wrap(data: any, context: ToolContext): ToolResponse<any> {
    return {
      success: true,
      data,
      message: data.message,
      metadata: {
        rule_id: data.rule_id,
        action: data.action,
      },
    };
  }
}
