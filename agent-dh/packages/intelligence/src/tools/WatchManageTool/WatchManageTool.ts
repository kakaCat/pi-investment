import { BaseTool, ToolResponse, ValidationResult, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
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

      // 校验 condition 格式（2026-09-01 扩展：pnl_pct / volume_surge / velocity）
      const validConditions = [
        /^price\s*>\s*\d+(\.\d+)?$/,
        /^price\s*<\s*\d+(\.\d+)?$/,
        /^change_pct\s*>\s*-?\d+(\.\d+)?$/,
        /^change_pct\s*<\s*-?\d+(\.\d+)?$/,
        /^pnl_pct\s*>\s*-?\d+(\.\d+)?$/,
        /^pnl_pct\s*<\s*-?\d+(\.\d+)?$/,
        /^volume_surge\s*>\s*\d+(\.\d+)?$/,
        /^velocity\s*>\s*\d+(\.\d+)?\s*\/\s*\d+$/,
      ];

      const isValidCondition = validConditions.some(regex => regex.test(condition.trim()));
      if (!isValidCondition) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          issue: `condition 格式错误。支持：price>100、price<90、change_pct>5、change_pct<-3、pnl_pct<-8（持仓盈亏，配 cost_price 或自动取持仓成本）、pnl_pct>10、volume_surge>4（量能倍数）、velocity>2/15（15分钟窗口波动≥2%）`,
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
    // 2026-09-01 扩展：reason → 后端 context（监视理由）；pnl_pct 自动补成本价
    const request: any = { ...params };
    delete request.reason;
    // account 不再删除：create 时透传后端落库为规则归属账户（2026-09-04 账户关联）

    if (params.action === 'create') {
      if (params.reason) request.context = params.reason;
      if (params.expires_at) request.expires_at = params.expires_at;

      const isPnl = /^\s*pnl_pct/.test(params.condition ?? '');
      if (isPnl && !params.cost_price) {
        // 自动取持仓成本（对标 agent-ts"持仓补位止损"场景）
        const account = params.account || 'agent_virtual';
        const positions = await this.qv2Client.getPositions(account);
        const pos = (positions || []).find((p: any) => p.symbol === params.symbol);
        const cost = pos?.avgCost ?? pos?.avg_cost ?? pos?.costPrice;
        if (!cost) {
          throw new Error(
            `pnl_pct 条件需要成本价：账户 ${account} 未持有 ${params.symbol}，请显式传 cost_price 参数`
          );
        }
        request.cost_price = cost;
        if (!params.account) request.account = account; // 成本来自该账户持仓 => 归属该账户
      } else if (params.cost_price) {
        request.cost_price = params.cost_price;
      }
    }

    const result = await this.qv2Client.manageWatchRule(request);
    // 2026-08-30 修复：
    // 1) rule_id 取值兼容后端 {rule:{id}} 包装（unwrap 返回 data 层）；
    // 2) rule_id/data 可能为 undefined，顶层 undefined 键会被
    //    DSH snapshotJsonValue 拒绝（"value is not lossless JSON"），整体过清洗。
    const rid = result?.rule?.id ?? result?.id ?? result?.rule_id;
    return sanitizeLossless({
      success: true,
      rule_id: rid,
      action: params.action,
      message: params.action === 'create'
        ? `规则已创建 (ID: ${rid ?? 'unknown'})`
        : `规则已${params.action === 'enable' ? '启用' : params.action === 'disable' ? '禁用' : '删除'}`,
      data: result,
    });
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
