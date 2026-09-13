import type { ToolPrompt } from '@pi-investment/core-tool';
import type { CorePlanSnapshot } from '@pi-investment/quantsys-v2-client';

export interface CorePlanParams {
  account_name?: string;
}

export type CorePlanResult = CorePlanSnapshot;

function pct(x: any, digits: number): string {
  const n = Number(x);
  return Number.isFinite(n) ? (n * 100).toFixed(digits) + '%' : 'n/a';
}

function num(x: any, digits: number): string {
  const n = Number(x);
  return Number.isFinite(n) ? n.toFixed(digits) : 'n/a';
}

export const corePlanPrompt: ToolPrompt<CorePlanParams, CorePlanResult> = {
  description:
    '读取投资脑 core 建仓计划（只读）：目标暴露、core 持仓清单、成长板子额度、**新鲜度**、以及与当前持仓的机械差额。' +
    '适用于：盘前按计划建仓、取计划持仓作候选、核对计划是否已生成。' +
    '⚠️ 关键差异：本工具会直接告诉你计划**陈不陈**（freshness.is_stale / stale_reason）——' +
    '直读 config/core_plan.json 看不出这一点，周五的计划周一读出来一模一样。' +
    '⚠️ 本工具**只读**，不触发重新生成（生成参数集已审批）；需要补跑用 scheduler_manage 触发 core_plan_generate。',

  useCases: [
    '盘前读取当日建仓计划（由 09:05 的 core_plan_generate 生成）',
    '判断计划是否新鲜（是否今天生成、是否早于 09:00）——过期应如实报告并停止，不得手工补造',
    '取"目标组合 vs 当前持仓"的差额（含 T+1 可卖量 shares_available）',
    '取计划持仓作为候选池（core + 成长板子额度）',
  ],

  examples: [
    {
      title: '读取当日计划',
      params: {},
      expectedResult: '账户 agent_brain｜generated_at 今天 09:05｜目标暴露 12.5%｜core 15 只 + 成长板 2 只｜需买入 17 只约 62,696 元',
    },
    {
      title: '计划过期（生成失败）',
      params: {},
      expectedResult: 'available=true 但 freshness.is_stale=true，stale_reason: "generated_at=… 不是今天"——按例行纪律判"生成失败"并停止，不要自己写脚本或改参数补跑。',
    },
  ],

  notes: [
    '⚠️ delta **不是委托清单**：plan_close 是计划生成时的收盘价（不是实时价）、未做 regime/止损复检、未做分批节奏（计划本身分 4 批）。下单前必须走 R-001/R-002，并 data_fetch_quote(source=realtime) 重新取价。',
    '⚠️ delta.rows 中 action=REVIEW 表示"持仓但不在本计划内"，**不等于应卖出**——本计划是建仓计划，不含退出判断。',
    '⚠️ 卖出前必须看 shares_available（T+1：当日买入次日才可卖，宪法第2条）。',
    '💡 account_name 缺省 = 本实例投资账户；后端会与**计划文件自身记录的账户**比对，不一致时不给跨账户差额并说明原因（计划只覆盖单一账户）。',
    '💡 计划生成参数集已审批，不要在调用侧改参数；需重新生成：scheduler_manage(action="trigger", task_id="337")。',
  ],

  relatedTools: ['account_info', 'position_list', 'regime_position_limit', 'scheduler_manage', 'portfolio_trade'],

  parameters: {
    account_name: {
      type: 'string',
      description: '账户名称。缺省为本实例投资账户；与计划文件记录的账户不一致时不给差额',
      example: 'agent_brain',
    },
  },

  output: {
    // ⚠️ 可空字段必须写 oneOf（DSH schema DSL 不支持 type 数组，见 dsh-tools json-schema.js：
    //    "type arrays are not supported"，同时 "cannot declare both type and oneOf"）。
    // 2026-09-13 线上实测（w-c8cae280）：本 schema 原先把 these 声明成 string/number，
    // 而后端在"计划可用/新鲜/held_only 行"等正常情形下返回 **null** →
    // 工具调用直接失败："value.unavailable_reason must be a string / target_shares must be a number"。
    // 也就是说：**schema 比数据更严 = 工具在正常路径上不可用**（与"契约必须与线上数据对齐"同一条教训）。
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        plan_file: { type: 'string' },
        available: { type: 'boolean' },
        unavailable_reason: {
          oneOf: [{ type: 'string' }, { type: 'null' }],
          description: '不可用原因；available=true 时为 null',
        },
        account: { oneOf: [{ type: 'string' }, { type: 'null' }] },
        account_mismatch: { type: 'boolean' },
        freshness: {
          oneOf: [
            {
              type: 'object', additionalProperties: true,
              properties: {
                generated_at: { oneOf: [{ type: 'string' }, { type: 'null' }] },
                data_date: { oneOf: [{ type: 'string' }, { type: 'null' }] },
                is_stale: { type: 'boolean' },
                stale_reason: {
                  oneOf: [{ type: 'string' }, { type: 'null' }],
                  description: '过期原因；新鲜时为 null',
                },
                age_hours: { oneOf: [{ type: 'number' }, { type: 'null' }] },
              },
            },
            { type: 'null' },
          ],
        },
        plan: { oneOf: [{ type: 'object', additionalProperties: true }, { type: 'null' }] },
        delta: {
          oneOf: [
            {
              type: 'object', additionalProperties: true,
              properties: {
                account: { type: 'string' },
                cash_available: { oneOf: [{ type: 'number' }, { type: 'null' }] },
                summary: { type: 'object', additionalProperties: true },
                limit_check: { oneOf: [{ type: 'object', additionalProperties: true }, { type: 'null' }] },
                caveats: { type: 'array', items: { type: 'string' } },
                rows: {
                  type: 'array',
                  items: {
                    type: 'object', additionalProperties: true,
                    properties: {
                      symbol: { type: 'string' },
                      bucket: { type: 'string' },
                      action: { type: 'string' },
                      // held_only（计划外持仓）行的目标/差额天然为 null —— 这正是线上触发失败的那条
                      target_shares: { oneOf: [{ type: 'number' }, { type: 'null' }] },
                      held_shares: { type: 'number' },
                      shares_available: { type: 'number' },
                      delta_shares: { oneOf: [{ type: 'number' }, { type: 'null' }] },
                    },
                  },
                },
              },
            },
            { type: 'null' },
          ],
        },
      },
    },
    render: (_args, data) => {
      const L: string[] = [];
      if (!data || !data.available) {
        L.push('❌ core 建仓计划不可用');
        if (data && data.unavailable_reason) L.push('原因：' + String(data.unavailable_reason));
        return [{ type: 'text', text: L.join('\n') }];
      }
      const f: any = data.freshness || {};
      const plan: any = data.plan || {};
      const ex: any = plan.exposure || {};
      L.push(f.is_stale ? '⚠️ core 计划已过期（不要按它建仓）' : '✅ core 计划新鲜');
      L.push('账户 ' + String(data.account) + '｜生成 ' + String(f.generated_at) +
        '｜行情日期 ' + String(f.data_date || 'n/a') + '｜已生成 ' + String(f.age_hours) + ' 小时');
      if (f.is_stale) L.push('过期原因：' + String(f.stale_reason));
      if (data.account_mismatch) L.push('⚠️ 账户不匹配：' + String(data.unavailable_reason));
      L.push('目标暴露 ' + pct(ex.target_pct, 1) + '（首期上限 ' + pct(ex.first_phase_cap_pct, 0) +
        '｜core 20日年化波动 ' + pct(ex.core_realized_vol_ann, 1) + '｜回撤 ' + pct(ex.core_drawdown, 1) +
        ' → 闸门 ' + String(ex.dd_gate) + '）');
      const hold: any[] = Array.isArray(plan.holdings) ? plan.holdings : [];
      L.push('core 持仓 ' + hold.length + ' 只：');
      for (const h of hold) {
        L.push('  ' + h.symbol + '  现价 ' + num(h.close, 2) + '  权重 ' + num(h.weight_pct_of_core, 1) +
          '%  ' + String(h.lots) + ' 手 ≈ ' + num(h.amount, 0) + ' 元  ' + String(h.industry || ''));
      }
      const sleeve: any = plan.growth_sleeve || {};
      const sh: any[] = Array.isArray(sleeve.holdings) ? sleeve.holdings : [];
      const sm: any = sleeve.meta || {};
      L.push('成长板子额度 ' + sh.length + ' 只｜暴露 ' + pct(sm.exposure_pct_of_total, 2) +
        '（约 ' + num(sm.amount, 0) + ' 元）');
      for (const h of sh) {
        L.push('  ' + h.symbol + '  现价 ' + num(h.close, 2) + '  ' + String(h.lots) +
          ' 手 ≈ ' + num(h.amount, 0) + ' 元');
      }
      const d: any = data.delta;
      if (!d) {
        L.push('（本次未计算与持仓的差额）');
      } else {
        const s: any = d.summary || {};
        L.push('');
        L.push('--- 目标 vs 当前持仓的机械差额（现金 ' + num(d.cash_available, 0) + '）---');
        L.push('买 ' + String(s.buy_count) + ' 只（约 ' + num(s.est_buy_amount, 0) + ' 元）｜卖 ' +
          String(s.sell_count) + ' 只｜已足 ' + String(s.hold_count) + ' 只｜需复核 ' +
          String(s.review_count) + ' 只｜现金' + (s.cash_sufficient ? '够' : '不够'));
        const rows: any[] = Array.isArray(d.rows) ? d.rows : [];
        for (const r of rows) {
          if (r.action === 'NONE') continue;
          L.push('  [' + r.action + '] ' + r.symbol +
            '  目标 ' + (r.target_shares === null ? '-' : String(r.target_shares)) +
            ' 股 / 持 ' + String(r.held_shares) + ' 股（可卖 ' + String(r.shares_available) + '）' +
            ' → 差 ' + (r.delta_shares === null ? '-' : String(r.delta_shares)) + ' 股' +
            (r.est_amount === null ? '' : '  ≈' + num(r.est_amount, 0) + ' 元'));
        }
        const cav: string[] = Array.isArray(d.caveats) ? d.caveats : [];
        L.push('⚠️ 这不是委托清单：' + (cav[0] || ''));
        L.push('⚠️ ' + (cav[4] || ''));
      }
      return [{ type: 'text', text: L.join('\n') }];
    },
  },
};
