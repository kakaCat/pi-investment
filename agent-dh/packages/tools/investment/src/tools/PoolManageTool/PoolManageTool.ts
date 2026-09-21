import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { poolManagePrompt, PoolManageParams } from './prompt';

const NEED_POOL_ID: ReadonlySet<string> = new Set([
  'update', 'delete', 'add_members', 'remove_members',
  'update_member', 'refresh', 'sync_names', 'validate',
]);

const NEED_SYMBOLS: ReadonlySet<string> = new Set(['add_members', 'remove_members']);

/**
 * PoolManageTool - 股票池管理（写操作）
 * action 路由对齐 qv2 后端 /api/pools 系端点契约（2026-09-05 逐端点核对）。
 */
export class PoolManageTool extends BaseTool<PoolManageParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'pool_manage',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 60000, // refresh/scan_create/validate 涉及全市场打分，放宽超时
  };

  protected readonly prompt = poolManagePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: PoolManageParams): ValidationResult {
    if (!args?.action) {
      return { success: false, issue: 'action 必填：create/scan_create/update/delete/add_members/remove_members/update_member/refresh/sync_names/validate' };
    }
    const a = args.action;

    if (a === 'create' || a === 'scan_create') {
      if (!args.name) return { success: false, issue: `${a} 需要 name（池名）` };
      if (!args.pool_type) return { success: false, issue: `${a} 需要 pool_type（static/dynamic）` };
      if (a === 'scan_create' && !args.filter_template) {
        return { success: false, issue: 'scan_create 需要 filter_template（筛选规则），如 {min_score:60, technical:[], fundamental:["pe_low"], top_n:20}' };
      }
      if (a === 'create' && args.pool_type === 'dynamic' && !args.filter_template) {
        return { success: false, issue: 'create(dynamic) 需要 filter_template，否则后续 refresh 无规则可用' };
      }
    } else if (a === 'delete') {
      if (!args.pool_id) return { success: false, issue: 'delete 需要 pool_id（先用 pool_list 确认目标）' };
      if (!args.reason) return { success: false, issue: 'delete 属不可逆破坏性操作，必须提供 reason 说明为何删除（并应同步 decision_audit 留痕）' };
    } else if (NEED_POOL_ID.has(a)) {
      if (!args.pool_id) return { success: false, issue: `${a} 需要 pool_id` };
      if (a === 'update' && !args.name && !args.description && !args.symbols) {
        return { success: false, issue: 'update 至少提供 name/description/symbols 之一' };
      }
      if (NEED_SYMBOLS.has(a) && (!args.symbols || args.symbols.length === 0)) {
        return { success: false, issue: `${a} 需要非空 symbols 数组` };
      }
      if (a === 'update_member' && !args.symbol) {
        return { success: false, issue: 'update_member 需要 symbol' };
      }
    }
    return { success: true };
  }

  protected async execute(args: PoolManageParams, _context: ToolContext): Promise<any> {
    const a = args.action;
    switch (a) {
      case 'create': {
        const isDynamic = args.pool_type === 'dynamic';
        const pool = await this.qv2.createPool({
          name: args.name!,
          pool_type: args.pool_type!,
          description: args.description,
          symbols: isDynamic ? undefined : args.symbols,
          filter_template: isDynamic ? args.filter_template : undefined,
          refresh_interval: args.refresh_interval,
        });
        return { action: a, pool_id: pool.id, ...pool };
      }
      case 'scan_create': {
        const pool = await this.qv2.scanAndCreatePool({
          name: args.name!,
          pool_type: args.pool_type!,
          filter_template: args.filter_template!,
          refresh_interval: args.refresh_interval,
          description: args.description,
        });
        return { action: a, pool_id: pool.id, ...pool };
      }
      case 'update': {
        const updates: Record<string, any> = {};
        if (args.name !== undefined) updates.name = args.name;
        if (args.description !== undefined) updates.description = args.description;
        if (args.symbols !== undefined) updates.symbols = args.symbols;
        const pool = await this.qv2.updatePool(args.pool_id!, updates as any);
        return { action: a, pool_id: pool.id, ...pool };
      }
      case 'delete': {
        // 删除前确认池存在，把名字带回结果便于留痕
        let name = '';
        try {
          const p = await this.qv2.getPool(args.pool_id!);
          name = p?.name ?? '';
        } catch {
          // 池不存在时后端 delete 会 404，让错误自然上抛
        }
        await this.qv2.deletePool(args.pool_id!);
        return { action: a, pool_id: args.pool_id, name, deleted: true };
      }
      case 'add_members': {
        const result = await this.qv2.addPoolMembers(args.pool_id!, {
          symbols: args.symbols!,
          description: args.description,
          buy_point: args.buy_point,
          sell_point: args.sell_point,
          tags: args.tags,
        });
        return { action: a, pool_id: args.pool_id, ...result };
      }
      case 'remove_members': {
        const result = await this.qv2.removePoolMembers(args.pool_id!, args.symbols!);
        return { action: a, pool_id: args.pool_id, ...result };
      }
      case 'update_member': {
        const result = await this.qv2.updatePoolMember(args.pool_id!, args.symbol!, {
          description: args.description,
          buy_point: args.buy_point,
          sell_point: args.sell_point,
          tags: args.tags,
        });
        return { action: a, pool_id: args.pool_id, symbol: args.symbol, ...result };
      }
      case 'refresh': {
        // 先确认是 dynamic 池（static 池无 filter_template，后端会拒绝，提前给出清晰错误）
        const p = await this.qv2.getPool(args.pool_id!);
        if (p?.pool_type !== 'dynamic') {
          throw new Error(`池 #${args.pool_id}「${p?.name ?? ''}」是 static 池，无筛选规则可刷新；成员需手工 add_members/remove_members 维护`);
        }
        const pool = await this.qv2.refreshPool(args.pool_id!);
        return { action: a, pool_id: pool.id, ...pool };
      }
      case 'sync_names': {
        const pool = await this.qv2.syncStockNames(args.pool_id!);
        return { action: a, pool_id: pool.id, ...pool };
      }
      case 'validate': {
        const result = await this.qv2.validatePool(args.pool_id!, {
          strategy_ids: args.strategy_ids,
          start_date: args.start_date,
          end_date: args.end_date,
        });
        return { action: a, pool_id: args.pool_id, ...result };
      }
      default:
        throw new Error(`未知 action: ${String(a)}`);
    }
  }

  protected wrap(data: any): ToolResponse<any> {
    return { success: true, data };
  }
}
