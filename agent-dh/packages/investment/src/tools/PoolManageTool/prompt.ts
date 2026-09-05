/**
 * PoolManageTool - 股票池管理（写操作）
 *
 * 股票池是"博弈战场"的载体：建池=选战场、改规则=调整战法、增删成员=调动兵力。
 * 全部 action 对齐 qv2 后端 /api/pools 系契约（2026-09-05 真机核对）。
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export type PoolAction =
  | 'create'          // 建池（static=手工成员 / dynamic=filter_template 驱动）
  | 'scan_create'     // 扫描自动建池：按筛选规则扫全市场打分后落池
  | 'update'          // 改池名/描述/整表替换 static symbols
  | 'delete'          // 删池（不可逆，务必先 pool_list/get 确认 + reason 留痕）
  | 'add_members'     // 批量增成员（可带买点/卖点/标签元数据）
  | 'remove_members'  // 批量删成员
  | 'update_member'   // 改单个成员的元数据（买点/卖点/标签/备注）
  | 'refresh'         // 刷新 dynamic 池（用 filter_template 重算成员）
  | 'sync_names'      // 同步成员名称展示字段
  | 'validate';       // 对池成员跑策略回测校验（需 strategy_ids）

export interface PoolManageParams {
  action: PoolAction;
  /** 目标池 id（update/delete/refresh/sync_names/validate/members 系必填） */
  pool_id?: number;
  /** 池名（create/scan_create 必填；update 可选） */
  name?: string;
  /** static（手工维护）/ dynamic（筛选规则驱动，refresh 重算） */
  pool_type?: string;
  /** 池描述（创建说明、战法注释） */
  description?: string;
  /** 成员代码列表：create(static)/add_members/remove_members 必填；update=整表替换 */
  symbols?: string[];
  /** 单个成员代码（update_member 必填） */
  symbol?: string;
  /**
   * 动态池筛选规则（JSON 对象）——create(dynamic)/scan_create 必填。
   * 支持键：{min_score?:number(默认0), max_risk_level?:"low"|"medium"|"high",
   *   top_n?:number(默认50), technical?:string[], fundamental?:string[],
   *   conditions?:[{field,operator,value}], logic?:"AND"|"OR"}
   * field 允许: roe/pe/pb/gross_margin/debt_ratio/net_profit_growth/market_cap/
   *   circulating_mv/avg_turnover_rate/rsi/macd/volume_ratio_5d
   * operator 允许: >=/<=/>/</==/!=（value 须为数值）
   * fundamental 常用键: roe_high/pe_low/pb_low/debt_ratio_low/gross_margin_high/growth_high
   * 现役样例：{min_score:60, technical:[], fundamental:["pe_low"], top_n:20}
   */
  filter_template?: Record<string, any>;
  /** 刷新周期（dynamic 池）：daily/weekly 等；不传=不自动刷新 */
  refresh_interval?: string;
  /** 成员买入参考价（add_members/update_member） */
  buy_point?: number;
  /** 成员卖出参考价（add_members/update_member） */
  sell_point?: number;
  /** 成员标签（add_members/update_member） */
  tags?: string[];
  /** 校验用策略 id 列表（validate；经 strategy_list 获取） */
  strategy_ids?: number[];
  /** 校验窗口起始（validate；YYYY-MM-DD） */
  start_date?: string;
  /** 校验窗口结束（validate；YYYY-MM-DD） */
  end_date?: string;
  /** 操作理由（破坏性动作如 delete 强烈建议填，agent 须另行 decision_audit 留痕） */
  reason?: string;
}

export const poolManagePrompt: ToolPrompt<PoolManageParams> = {
  description:
    '股票池管理（写操作）：创建/删除池、改筛选规则、批量增删成员、刷新动态池、策略校验。' +
    '股票池是"博弈战场"载体——建池=选战场（观察池/主题池/高股息池等），dynamic 池用 filter_template 规则驱动、refresh 时自动换血。' +
    '适用：把发现的候选标的落池跟踪、维护动态池规则、清理废弃池、为池建成员买点/卖点纪律。' +
    '破坏性动作（delete 等）前先 pool_list/pool_battlefield 确认，操作后按决策审计规范 decision_audit 留痕。',

  useCases: [
    '把机会扫描/主线挖掘出的候选批量加入某观察池，并给每只标买点/卖点/标签',
    '创建一个新的主题/策略池（static 手工成员 或 dynamic 筛选规则）',
    '调整动态池筛选规则（条件/评分阈值/top_n/刷新周期）或手动触发 refresh 换血',
    '清理空转/废弃/重复的池子，避免池子数量膨胀稀释注意力',
    '对池成员跑策略回测校验，验证"这个战场值不值得下注"',
  ],

  examples: [
    { title: '建 static 观察池（主题候选落池）', params: { action: 'create', name: 'AI应用观察池', pool_type: 'static', symbols: ['300308', '002230'], description: 'AI应用落地期候选，等回踩分批建仓', reason: '主线跟踪 2026-09' } },
    { title: '建 dynamic 高股息池（规则驱动）', params: { action: 'create', name: '高股息防御池', pool_type: 'dynamic', filter_template: { min_score: 60, technical: [], fundamental: ['pe_low', 'debt_ratio_low'], top_n: 20 }, refresh_interval: 'weekly', description: '股息率>3% + 低估值 + 低负债' } },
    { title: '批量增成员并带买/卖点纪律', params: { action: 'add_members', pool_id: 41, symbols: ['002472', '300124'], buy_point: 30.5, sell_point: 45, tags: ['机器人', '一梯队'], reason: 'Q3 订单验证补仓候选' } },
    { title: '扫描自动建池（RSI 超卖）', params: { action: 'scan_create', name: 'RSI超卖反弹候选池', pool_type: 'dynamic', filter_template: { conditions: [{ field: 'rsi', operator: '<', value: 30 }], top_n: 30 }, description: '技术面超卖扫描自动建池' } },
    { title: '更新成员元数据（调目标位）', params: { action: 'update_member', pool_id: 34, symbol: '600309', sell_point: 95, reason: '上调目标位' } },
    { title: '批量移除成员（基本面证伪）', params: { action: 'remove_members', pool_id: 41, symbols: ['688322'], reason: '基本面证伪，移出观察' } },
    { title: '刷新动态池换血', params: { action: 'refresh', pool_id: 3, reason: '周更动态池换血' } },
  ],

  notes: [
    'dynamic 池必须有 filter_template，否则 refresh 会失败；static 池不能 refresh（成员手工维护）',
    'update 的 symbols 是整表替换；仅增删个别成员用 add_members/remove_members',
    'create/scan_create/refresh 涉及全市场打分，耗时数秒~数十秒，属正常',
    '删除不可逆：delete 前先确认池内无价值信息（历史战绩/观察结论在 memory 里另存）',
    '所有写操作应在 agent 侧配 decision_audit(record) + memory_write 留痕，供复盘归因',
  ],

  relatedTools: ['pool_list', 'pool_battlefield', 'opportunity_scan', 'screening', 'strategy_list', 'mainline_stocks'],

  parameters: {
    action: {
      type: 'string',
      description: '操作类型（见枚举）：create/scan_create/update/delete/add_members/remove_members/update_member/refresh/sync_names/validate',
      required: true,
      enum: ['create', 'scan_create', 'update', 'delete', 'add_members', 'remove_members', 'update_member', 'refresh', 'sync_names', 'validate'],
    },
    pool_id: { type: 'number', description: '目标池 id（update/delete/refresh/sync_names/validate/成员系必填；经 pool_list 获取）' },
    name: { type: 'string', description: '池名（create/scan_create 必填；update 可选覆盖）' },
    pool_type: {
      type: 'string',
      description: 'static（手工维护成员）/ dynamic（filter_template 规则驱动、refresh 重算）',
      enum: ['static', 'dynamic'],
    },
    description: { type: 'string', description: '池描述：创建逻辑、战法注释、验证指标等' },
    symbols: {
      type: 'array',
      description: '成员 A股6位代码列表：create(static)/add_members/remove_members 必填；update=整表替换',
      items: { type: 'string' },
    },
    symbol: { type: 'string', description: '单个成员代码（update_member 必填），如 600519' },
    filter_template: {
      type: 'object',
      additionalProperties: true,
      description: '动态池筛选规则 JSON（见 description 详细键位说明），create(dynamic)/scan_create 必填',
    },
    refresh_interval: {
      type: 'string',
      description: '刷新周期（dynamic 池）：daily=每日/weekly=每周/不传=手动触发 refresh',
    },
    buy_point: { type: 'number', description: '成员买入参考价（add_members/update_member 元数据）' },
    sell_point: { type: 'number', description: '成员卖出参考价（add_members/update_member 元数据）' },
    tags: {
      type: 'array',
      description: '成员标签列表，如 ["机器人","一梯队"]（add_members/update_member）',
      items: { type: 'string' },
    },
    strategy_ids: {
      type: 'array',
      description: '校验用策略 id 列表（validate；经 strategy_list 获取）',
      items: { type: 'number' },
    },
    start_date: { type: 'string', description: '校验窗口起始 YYYY-MM-DD（validate）' },
    end_date: { type: 'string', description: '校验窗口结束 YYYY-MM-DD（validate）' },
    reason: { type: 'string', description: '操作理由：为什么建/删/改（破坏性动作必填，agent 须另存 decision_audit+memory）' },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        action: { type: 'string', description: '执行的操作' },
        pool_id: { type: 'number', description: '目标池 id' },
        name: { type: 'string', description: '池名' },
        data: { type: 'object', additionalProperties: true, description: '后端返回的池/成员/校验结果' },
      },
    },
    render: (_args: PoolManageParams, data: any) => {
      const rows = Array.isArray(data) ? data : data ? [data] : [];
      const summary = rows.length
        ? rows.map((r: any) => {
            const bits = [`#${r?.id ?? r?.pool_id ?? '?'}`];
            if (r?.name) bits.push(r.name);
            if (typeof r?.symbol_count === 'number') bits.push(`成员${r.symbol_count}`);
            if (r?.pool_type) bits.push(r.pool_type);
            if (r?.error) bits.push(`错误:${r.error}`);
            return bits.join(' ');
          }).join('\n')
        : JSON.stringify(data, null, 2);
      const reason = _args.reason ? `\n理由: ${_args.reason}` : '';
      return [{ type: 'text', text: `[pool_manage] ${_args.action}${reason}\n${summary}` }];
    },
  },
};
