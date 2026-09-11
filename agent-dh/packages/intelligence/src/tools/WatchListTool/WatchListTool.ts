import { BaseTool, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { watchListPrompt, type WatchListParams } from './prompt';

export class WatchListTool extends BaseTool<WatchListParams, any[]> {
  protected readonly metadata: ToolMetadata = {
    name: 'watch_list',
    category: 'intelligence',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = watchListPrompt;

  constructor(private qv2Client: QuantsysV2Client) {
    super();
  }

  protected validate(params: WatchListParams): ValidationResult {
    // 无参数，直接返回成功
    return { success: true };
  }

  protected async execute(params: WatchListParams, context: ToolContext): Promise<any[]> {
    const result: any = await this.qv2Client.listWatchRules();
    const rules: any[] = Array.isArray(result) ? result : (result?.rules ?? []);

    // 2026-09-11（w-c8cae280）：真实触发次数
    // 背景：后端 /api/watch/rules 不返回 triggered_count（响应键实测无此字段），
    // 旧实现 `?? 0` 把「字段缺失」伪装成「从未触发」——53 条规则全部显示 0，
    // 而同一时刻 watch_triggers 里规则 #135 当日已触发 4 次。
    // 该假 0 直接导致一次「盯盘引擎失效 / 持仓无保护」的误判（本窗口亲历并已更正）。
    // 现改为按触发记录真实统计；查询失败时置 null 并显式说明，禁止再用 0 冒充。
    let counts: Map<any, number> | null = null;
    let triggerScope: string | null = null;
    try {
      const raw: any = await this.qv2Client.listWatchTriggers(undefined, 500);
      const triggers: any[] = Array.isArray(raw) ? raw : (raw?.triggers ?? []);
      counts = new Map();
      for (const t of triggers) {
        const id = t?.rule_id ?? t?.ruleId;
        if (id === undefined || id === null) continue;
        counts.set(id, (counts.get(id) ?? 0) + 1);
      }
      triggerScope = `最近 ${triggers.length} 条触发记录内`;
    } catch {
      counts = null;
    }

    // 2026-09-11 修复（REQ-342799）：后端 contract 为
    //   { id, symbol, enabled, conditions:[{type,params}], context }
    // 旧实现原样透传 → 工具 schema 声明的 name/condition 恒为 undefined，规则读不出内容。
    // 现在归一化：condition 由 conditions[] 渲染，name/reason 有回落而非 undefined。
    return rules.map((r: any) => {
      const conds: any[] = Array.isArray(r?.conditions)
        ? r.conditions
        : (r?.condition ? [r.condition] : []);
      // 单条件渲染（支持 combined 递归——AND 只可能出现在 combined 节点内部）
      const renderCond = (c: any): string => {
        if (typeof c === 'string') return c;
        const t = c?.type ?? 'condition';
        const ps: any = c?.params ?? {};
        if (t === 'price_break') return 'price ' + (ps.direction === 'below' ? '<' : '>') + ' ' + ps.price;
        if (t === 'volume_surge') return 'volume_surge>' + ps.multiple;
        // 2026-09-11 修复：后端 pnl_pct 的阈值键是 pct（非 value），
        // 旧实现读 ps.value → 渲染成 'pnl_pct > undefined'，看起来像阈值丢失（实为展示 bug）。
        if (t === 'pnl_pct') return 'pnl_pct ' + (ps.direction === 'below' ? '<' : '>') + ' ' + (ps.pct ?? ps.value);
        if (t === 'combined') {
          const sep = ps.operator === 'AND' ? ' 且 ' : ' 或 ';
          const inner = (Array.isArray(ps.conditions) ? ps.conditions : []).map(renderCond).join(sep);
          return '(' + inner + ')';
        }
        return t + ' ' + JSON.stringify(ps);
      };
      const parts = conds.map(renderCond);
      // ⚠️ 顶层 conditions 列表的执行语义是 **OR（任一触发）**，不是 AND：
      // engine.py 对 conditions[] 逐条独立评估，每条各有闩锁/冷却/通知（AND 只能通过
      // 单个 combined 节点表达）。旧实现 join(' AND ') 与执行语义**相反**，后果实测：
      //   · 10 条合法的"区间突破"规则（如 跌破9.85 或 突破10.2）被渲染成
      //     'price < 9.85 AND price > 10.2'，看起来逻辑恒假、像僵尸规则，
      //     2026-09-11 据此后**几乎误删这 10 条规则**；
      //   · 更危险的是反向误读：把"任一触发"当成"双重确认"，据此以为自己有确认保护。
      const condText = parts.join(parts.length > 1 ? ' 或 ' : '');
      return {
        ...r,
        name: r?.name ?? r?.rule_name ?? ('规则#' + (r?.id ?? '?')),
        // 空条件必须显式标注：2026-09-11 实测 65 条规则中 13 条 conditions=[]（created_by=opportunity_scan 自动建），
        // 这类规则永不触发；旧实现返回 undefined，容易被误读为『条件正常但未显示』。
        condition: condText || '(未配置触发条件——该规则永不触发，需人工补条件或删除)',
        condition_missing: conds.length === 0,
        conditions: conds,
        reason: r?.reason ?? r?.context ?? undefined,
        // 2026-09-11（REQ-733c5e）：优先用后端权威 triggered_count（rule_to_dict 现已返回该字段，
        // 为 COUNT(watch_triggers) 全量值）；后端缺失/非数字时回落到本工具的触发记录统计（近 500 条口径）。
        triggered_count: (typeof r?.triggered_count === 'number' ? r.triggered_count : (counts ? (counts.get(r?.id) ?? 0) : null)),
        triggered_count_scope: (typeof r?.triggered_count === 'number') ? '全量（后端 COUNT）' : (triggerScope ?? undefined),
        triggered_count_note: (typeof r?.triggered_count === 'number' || counts) ? undefined : '触发次数未知（勿按 0 理解）',
      };
    });
  }

  protected wrap(data: any[], context: ToolContext): ToolResponse<any[]> {
    const rules = Array.isArray(data) ? data : [];
    return {
      success: true,
      data: rules,
      message: `共找到 ${rules.length} 条盯盘规则`,
      metadata: {
        total: rules.length,
        enabled: rules.filter((r: any) => r?.enabled).length,
        disabled: rules.filter((r: any) => !r?.enabled).length,
      },
    };
  }
}
