import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * 盯盘待办工具参数（2026-10-16）
 *
 * 闭环最后一段：规则自愈/元评审/补全指引派出的"工单"（quant.watch_todos），
 * 此前只有人能看到（超时回执卡），agent 手上没有任何读/认领/关闭的工具。
 */
export interface WatchTodoParams {
  /** list=看工单；claim=声明接手；close=收敛并回写结论 */
  action: 'list' | 'claim' | 'close';
  /** claim / close 必填：待办 ID（wake 载荷里的 todo_id、或 list 返回的 id） */
  todo_id?: number;
  /** claim 用：接手方标识（默认取本实例，agent-dh） */
  owner_ref?: string;

  // ── close 参数（服务端硬约束见 description）──
  /** handled=已处置 / ignored=不动（须给 next_condition）/ expired=已过期 */
  terminal?: 'handled' | 'ignored' | 'expired';
  /** 处置结论：做了什么、或为什么不动 */
  close_reason?: string;
  /** terminal=ignored 必填：下次什么条件下才动（NEXT 条件） */
  next_condition?: string;
  /** 动作类型；L3 待办以 trade / rule_change 关闭时必须带 decision_audit_id */
  action_kind?: 'trade' | 'rule_change';
  /** 决策审计 ID（先用 decision_audit 工具留痕；L3 + trade/rule_change 缺则 400） */
  decision_audit_id?: string;

  // ── list 过滤 ──
  /** P0..P3 */
  level?: string;
  /** L1 / L2 / L3 */
  flow_state?: string;
  /** 归属账户（account_name 全名） */
  account?: string;
  /** 返回条数，默认 30、上限 500 */
  limit?: number;
}

export const watchTodoPrompt: ToolPrompt<WatchTodoParams, any> = {
  name: 'watch_todo',
  description:
    '盯盘待办的读写（闭环工单）：list=查看未收敛待办；claim=声明接手（避免重复处置）；close=收敛并回写结论。\n' +
    '何时用：① 收到 wake 事件 watch_todo_assigned / watch_todo_timeout（载荷里有 todo_id）——**必须处置并 close**，' +
    '否则 SLA 会反复升级、把用户卷进来；② 盘前/盘后自查是否还有挂着的工单（action=list）。\n' +
    'close 的硬约束（服务端校验，缺一即 400）：terminal ∈ handled|ignored|expired；' +
    'terminal=ignored 必须给 next_condition（下次什么条件下才动）；' +
    'action_kind ∈ trade|rule_change（L3 待办）必须给 decision_audit_id（先用 decision_audit 工具落审计，否则 watch_todo_missing_audit）。\n' +
    '纪律：判不动就 terminal=ignored + next_condition 写清下次条件，**不要让它挂着**；' +
    '真要改规则用 watch_manage（create/enable/disable/delete），本工具只负责把工单收口。',

  parameters: {
    action: {
      type: 'string',
      enum: ['list', 'claim', 'close'],
      required: true,
      description: '操作类型：list=查看、claim=认领、close=收敛',
    },
    todo_id: {
      type: 'integer',
      description: '待办 ID（claim/close 必填；来自 wake 载荷的 todo_id 或 list 返回的 id）',
    },
    owner_ref: {
      type: 'string',
      description: 'claim 时的接手方标识，默认本实例（agent-dh）',
    },
    terminal: {
      type: 'string',
      enum: ['handled', 'ignored', 'expired'],
      description: 'close 的终态：handled=已处置 / ignored=不动（必带 next_condition）/ expired=已过期',
    },
    close_reason: {
      type: 'string',
      description: 'close 的处置结论：做了什么、或为什么不动（会进处置回执与台账）',
    },
    next_condition: {
      type: 'string',
      description: 'terminal=ignored 必填：下次什么条件下才动（NEXT 条件）',
    },
    action_kind: {
      type: 'string',
      enum: ['trade', 'rule_change'],
      description: '动作类型；L3 待办以 trade/rule_change 关闭时必须带 decision_audit_id',
    },
    decision_audit_id: {
      type: 'string',
      description: '决策审计 ID（decision_audit 工具产出）——L3 + trade/rule_change 必填',
    },
    level: { type: 'string', description: 'list 过滤：级别 P0..P3' },
    flow_state: { type: 'string', description: 'list 过滤：流转态 L1/L2/L3' },
    account: { type: 'string', description: 'list 过滤：归属账户' },
    limit: { type: 'integer', description: 'list 返回条数，默认 30、上限 500' },
  },

  output: {
    schema: {
      type: 'object',
      additionalProperties: true,
      properties: {
        success: { type: 'boolean', description: '是否成功' },
        action: { type: 'string', description: '本次动作' },
        count: { type: 'integer', description: 'list 返回条数' },
        todos: { type: 'array', description: '待办列表（list）', items: { type: 'object', additionalProperties: true } },
        todo_id: { type: 'integer', description: '本次操作的待办 ID' },
        terminal: { type: 'string', description: 'close 后的终态' },
        message: { type: 'string', description: '人读结果' },
      },
    },
    render: (_args: WatchTodoParams, value: any) => [
      { type: 'text', text: JSON.stringify(value, null, 2) },
    ],
  },

  examples: [
    {
      scenario: '收到 watch_todo_assigned 后认领并处置',
      params: { action: 'claim', todo_id: 91 },
      expectedBehavior: '认领工单 #91（记录接手方与时间），随后用 watch_manage 修规则并用 close 收口',
    },
    {
      scenario: '判不动但不想让它挂着',
      params: {
        action: 'close', todo_id: 91, terminal: 'ignored',
        close_reason: '抑噪阈值合理，规则条件无需调整',
        next_condition: '该规则单日再次触发 ≥3 次时重新评估',
        action_kind: 'rule_change',
        decision_audit_id: 'dec-20261016-003',
      },
      expectedBehavior: '收敛为 ignored，回写理由与 NEXT 条件，SLA 不再升级',
    },
    {
      scenario: '盘前自查未收敛工单',
      params: { action: 'list', limit: 20 },
      expectedBehavior: '返回未收敛待办（含 id/symbol/level/流转态/动作类型/是否逾期）',
    },
  ],

  useCases: [
    {
      title: '把唤醒变成闭环',
      description: '每收到一条 watch_todo_assigned / watch_todo_timeout 就必须处置并 close，否则 SLA 反复升级',
      example: 'watch_todo claim → 改规则 → watch_todo close（handled + 审计 ID）',
    },
    {
      title: '盘前自查积压',
      description: '开盘前看还有哪些工单没收敛，先清最老/级别最高的',
      example: 'watch_todo list → 逐条 claim/close',
    },
  ],

  notes: [
    '待办是"引擎内部工单"（规则自愈抑噪、元评审重叠/缺指引、补全预案都会派），不是行情事实',
    '挂着的工单每到一个 SLA 周期就会升级一次：P0/P1 会转成给用户的超时卡——尽早 close 是降噪的关键',
    'close 的结论会进入"处置后回执"（含全过程时间线），用户能看见你为什么这么处置',
    '未终态待办才可认领/关闭；已收敛的会返回 watch_todo_already_closed',
  ],

  relatedTools: [
    {
      name: 'watch_manage',
      relationship: '改规则（create/enable/disable/delete）',
      useCase: 'rule_change 类工单：先用 watch_manage 修好规则，再 watch_todo close 收口',
    },
    {
      name: 'decision_audit',
      relationship: '决策留痕（产出 decision_audit_id）',
      useCase: 'L3 待办以 trade/rule_change 关闭前，先留审计再 close',
    },
    {
      name: 'watch_list',
      relationship: '看规则与触发次数',
      useCase: '判断某条工单对应的规则是否真的在反复触发',
    },
  ],
};
