/**
 * TradingPlanTool 提示词（REQ-261021222905-6dff t12 · D-7/D-9）
 *
 * 纪律：投资脑（agent-dh）是计划主消费方；账户缺省取实例投资账户；
 * 写操作必须带 decision_audit_id；两步提交：patch 只暂存+预览 diff，apply 才生效。
 */
import type { ToolPrompt } from '@pi-investment/core-tool';

export interface TradingPlanParams {
  action:
    | 'today'
    | 'list'
    | 'get'
    | 'create'
    | 'patch'
    | 'apply'
    | 'activate'
    | 'pause'
    | 'resume'
    | 'close'
    | 'preview'
    | 'stats'
    | 'reflect'
    | 'reflections'
    | 'blocked_stats';
  plan_id?: number;
  account?: string;
  status?: string;
  name?: string;
  horizon?: 'day' | 'swing';
  spec?: Record<string, unknown>;
  spec_patch?: Record<string, unknown>;
  expected_version?: number;
  reason?: string;
  decision_audit_id?: string;
  hypothesis?: Record<string, unknown>;
  verdict?: 'keep' | 'adjust' | 'close' | 'observe';
  answers?: Record<string, string>;
  actions?: Array<Record<string, unknown>>;
  close_disposition?: string;
  period?: string;
}

export type TradingPlanResult = Record<string, unknown>;

export const tradingPlanPrompt: ToolPrompt<TradingPlanParams, TradingPlanResult> = {
  description:
    '交易计划管理（qs_plan）：盘前 today 拉今日计划；create/patch（预览 diff）→ apply（生效并重编译）管理计划；' +
    'activate/pause/resume/close 生命周期；盘后 reflect 提交五问反思；stats/blocked_stats 看统计。' +
    '计划编译成盯盘规则由 WatchEngine 执行，**下单仍由你终判**；写操作必须带 decision_audit_id。',

  useCases: [
    '盘前第一步：today 看今日激活计划、环境闸结论、持仓差额与待决待办',
    '把 core_plan 生成的待补计划补上真实入场条件（patch 看 diff → apply 生效）',
    '触发止损/止盈后按计划执行，并在盘后用 reflect 交反思报告',
    '激活/暂停/关闭计划（激活=编译规则；关闭有持仓必须给 close_disposition）',
  ],

  examples: [
    {
      title: '盘前看今日计划',
      params: { action: 'today' },
      expectedResult: '{empty:false, plans:[{plan:{id,status,version}, targets:[{symbol,name,budget_pct,position}], env_gate, pending_todos}]}',
    },
    {
      title: '补入场条件（两步提交）',
      params: {
        action: 'patch', plan_id: 1, expected_version: 2,
        spec_patch: { entry: { conditions: [{ type: 'staged_break', params: { price: 56.2 } }], combinator: 'all_of' } },
        reason: '补回踩确认入场条件', decision_audit_id: 'd-20261022-1',
      },
      expectedResult: '返回 diff 预览（path/from/to），**尚未生效**；确认后调 apply',
    },
    {
      title: '提交反思',
      params: { action: 'reflect', plan_id: 1, verdict: 'keep', reason: '维持',
                answers: { q1: '…', q2: '…', q3: '…', q4: '…', q5: '…' } },
      expectedResult: '{report_id, plan_id}（五问缺项会被 400 点名）',
    },
  ],

  notes: [
    '⚠️ 托管规则唯一写点是计划编译器：改入场/止损/减仓请改计划，不要直接改 watch 规则。',
    '⚠️ 观察窗（默认 10 交易日）内改同一字段需要 change_reason 或 ≥2 条证据；反向修改必须写明「上次判断为什么错了」。',
    '⚠️ closed/archived 计划不可修改（422）；有持仓关闭必须给 close_disposition。',
    '⚠️ entry.pending=true 表示入场条件待补（core_plan 适配器生成），此时编译器只编止损，不会生成入场规则。',
  ],

  parameters: {
    action: {
      type: 'string',
      description: '操作：today|list|get|create|patch|apply|activate|pause|resume|close|preview|stats|reflect|reflections|blocked_stats',
      example: 'today',
    },
    plan_id: { type: 'number', description: '计划 ID（除 today/list/create/blocked_stats 外必填）', example: 1 },
    account: { type: 'string', description: '账户（缺省取实例投资账户）', example: 'agent_brain' },
    status: { type: 'string', description: 'list 过滤：active,holding,closing', example: 'draft' },
    name: { type: 'string', description: '计划名（create 必填）' },
    horizon: { type: 'string', description: 'day | swing（create 用）', example: 'day' },
    spec: { type: 'object', additionalProperties: true, description: '计划 spec：targets/entry/exit/monitoring/schedule（create 必填）' },
    spec_patch: { type: 'object', additionalProperties: true, description: 'patch 用：要覆盖的 spec 片段' },
    expected_version: { type: 'number', description: '版本 CAS（patch/apply/activate/resume 必填）', example: 1 },
    reason: { type: 'string', description: '理由（apply/pause/close 用；反向修改必须写清上次为什么错）' },
    decision_audit_id: { type: 'string', description: '决策审计号（agent 写操作必填）' },
    hypothesis: { type: 'object', additionalProperties: true, description: '假设卡：change/evidence/expected' },
    verdict: { type: 'string', description: '反思结论：keep | adjust | close | observe', example: 'keep' },
    answers: { type: 'object', additionalProperties: true, description: '反思五问：q1..q5' },
    actions: { type: 'array', items: { type: 'object', additionalProperties: true }, description: '修改提案（adjust/close 必填）' },
    close_disposition: { type: 'string', description: '持仓处置方案（有持仓关闭必填）' },
    period: { type: 'string', description: '反思周期（如 2026-10-21）' },
  },

  output: {
    schema: { type: 'object', additionalProperties: true },
  },
};
