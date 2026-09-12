/**
 * 任务业务线分类（host / client 共用唯一实现）— 2026-09-12 新建，w-c8cae280
 *
 * 为什么抽出来：分类原本只存在于 client/view.ts 的一张硬编码名单里，host 无法复用；
 * 而 host 需要基于同一口径算「对账/未归类」指标。两处各写一份必然漂移（本仓已有前例：
 * candidates.ts 的注释就在记录同类事故），故设为共享模块并配单测。
 *
 * 分类优先级（2026-09-12 定的口径）：
 *   ① 任务自带字段（OS 的 agent_line / v2 的 domain）—— **事实优先**
 *   ② 回退到任务名名单（历史口径，兼容字段尚未在接口暴露的过渡期）
 *   ③ 都认不出 → 'other' 且标记 unclassified=true（供对账显式暴露，不静默）
 *
 * 已知现状（2026-09-12 实测）：DB 里 public.tasks.agent_line 已存在（22 profit_engine / 5 autonomy），
 * 量化 domain 也在（但 13 个 NULL），**但两个接口都不返回这两个字段**（Go/SQLAlchemy 均为显式列读写）
 * → 今天 ① 恒不命中，实际仍走 ②。本模块把 ① 的通道准备好，接口一接通即自动生效。
 *
 * 注意：v2 的 `domain` 是"六域"（data/signal/trading/analysis/report/monitor），与"业务线"**正交**，
 * 不能拿来当 line 用；它只作为「该 v2 任务是否已打标」的对账信号。
 */

export type LineKey = 'engine' | 'autonomy' | 'account' | 'other';

/* 业务线分组（用户 2026-09-08 确认口径）：盈利引擎线（M 系生产）/ Autonomy 线（L 系自我改进）/
   账户定时任务（账户专属例行 + 模拟撮合）/ 临时·核验·其他（一次性或未归类，宁显不藏）。 */
export const LINE_META: { key: LineKey; zh: string }[] = [
  { key: 'engine', zh: '盈利引擎线' },
  { key: 'autonomy', zh: 'Autonomy 线' },
  { key: 'account', zh: '账户定时任务' },
  { key: 'other', zh: '临时/核验/其他' },
];
export const LINE_ZH: Record<string, string> = {
  engine: '盈利引擎线', autonomy: 'Autonomy 线', account: '账户定时任务', other: '临时/核验/其他',
};

/** OS 任务 agent_line 字段 → 业务线（DB 实测取值：profit_engine / autonomy） */
export const OS_AGENT_LINE_MAP: Record<string, LineKey> = {
  profit_engine: 'engine',
  autonomy: 'autonomy',
};

/** 归属名单（过渡期兜底）：raw name 精确匹配 + 前缀兜底；未知一律 other */
const ENGINE_KEYS = new Set<string>([
  '每日数据更新', '每日数据质量检查', '每日财报时效性检查', '每周财务数据更新',
  'market_daily_snapshot', 'chan-scan-daily', 'chan_scan_daily', 'market-style-update', 'market_style_update',
  'fund_flow_update', 'market_perception_daily',
  'daily-pool-refresh', 'daily_pool_refresh',
  'pre-market-scan', 'pre_market_scan', '每日信号生成', '每日信号执行',
  'signal-perf-backfill-daily', 'signal_perf_backfill_daily', 'signal_generate_sell',
  'v13-risk-check', 'v13_risk_check', 'daily_trade_verify', '每日模型重训',
  'pre-market-routine', 'afternoon-open-check-live', 'm4-circuit-breaker-live', 'post-market-routine-live',
  'data-quality-monitor-daily', 'event-calendar-check',
  'attribution-daily', 'intraday-surge-scan-am', 'intraday-surge-scan-pm', 'equity-snapshot-daily',
]);
const AUTONOMY_KEYS = new Set<string>([
  'daily-strategy-validation', 'daily_strategy_validation', 'v13-verification', 'v13_verification',
  'weekly-strategy-discovery', 'weekly_strategy_discovery',
  // 2026-09-13 实体改中文名（用户要求）；旧名保留兼容历史记录
  '每周策略发现',
  'chan-knowledge-distill-weekly', 'chan_knowledge_distill_weekly',
  'v13-weekly-report', 'v13_weekly_report', '每周报告生成',
  'evolution-distill-daily', 'evolution-gate-adjudicate', 'evolution-weekly-variant',
  'meta-learning-weekly', 'weekly-report-m6',
  'weekly_evolution', 'weekly_memory_distill', 'daily_ai_review', 'daily_recall_audit', 'weekly_tool_roi_review',
]);
const ACCOUNT_KEYS = new Set<string>(['v13-simulation-trading', 'v13_simulation_trading', 'v14-simulation-trading']);

/** 名单口径（仅按名），保留给"只有名字"的调用点 */
export function lineOfName(name: unknown): LineKey {
  const n = String(name ?? '');
  if (ENGINE_KEYS.has(n)) return 'engine';
  if (AUTONOMY_KEYS.has(n)) return 'autonomy';
  if (ACCOUNT_KEYS.has(n) || n.startsWith('agent-brain-')) return 'account';
  return 'other';
}

/** 已知的"其它"类前缀：归 other 属正常，不算未归类 */
function isKnownOther(n: string): boolean {
  return n.startsWith('board-') || n.startsWith('geer-') || n === 'v2_health_check';
}

export interface Classified {
  line: LineKey;
  /** 判定依据：field=任务自带字段 / name=名单 / fallback=都没认出来 */
  source: 'field' | 'name' | 'fallback';
  /** 需要人工补录（名单与字段都认不出） */
  unclassified: boolean;
}

/** 分类入口：优先任务自带字段，其次名单，最后 other 并标记未归类 */
export function classifyTask(t: { name?: unknown; agentLine?: unknown } | null | undefined): Classified {
  const name = String(t?.name ?? '');
  const fieldRaw = String(t?.agentLine ?? '').trim();
  if (fieldRaw) {
    const mapped = OS_AGENT_LINE_MAP[fieldRaw] ?? (fieldRaw as LineKey);
    if (mapped === 'engine' || mapped === 'autonomy' || mapped === 'account' || mapped === 'other') {
      return { line: mapped, source: 'field', unclassified: false };
    }
  }
  const byName = lineOfName(name);
  if (byName !== 'other') return { line: byName, source: 'name', unclassified: false };
  if (isKnownOther(name)) return { line: 'other', source: 'name', unclassified: false };
  return { line: 'other', source: 'fallback', unclassified: true };
}

/** 双线口径：今日执行总览 / 时间轴主视图只计这两条业务线（用户 2026-09-08） */
export function isDualLine(t: { name?: unknown; agentLine?: unknown } | null | undefined): boolean {
  const k = classifyTask(t).line;
  return k === 'engine' || k === 'autonomy';
}

export interface TaskCoverage {
  total: number;
  byLine: Record<string, number>;
  /** 靠任务自带字段判定的任务数（>0 说明接口已打通分类字段） */
  fieldTagged: number;
  /** 未从接口拿到分类字段的任务数（字段未打通时=总数） */
  fieldMissing: number;
  /** 名单与字段都认不出、需补录的任务名 */
  unclassified: string[];
  /** OS 侧对账（若上游提供）：接口返回总数 / 实际并入数 / 被排除数 / 其中带 line 字段数 */
  os?: { apiTotal: number; included: number; excluded: number; byReason: Record<string, number>; lineTagged?: number };
  /** v2 侧对账（2026-09-12 接口接通后新增）：domain 是六域，与业务线正交，只作「是否已打标」信号，不计入 line 字段 */
  v2?: { total: number; domainTagged: number; domainMissing: number; domainByValue: Record<string, number>; missingNames: string[] };
}

/** 对账：把"分类字段是否打通 / 有无未归类"变成可读指标，供页面显式展示 */
export function computeTaskCoverage(
  tasks: Array<{ name?: unknown; agentLine?: unknown; domain?: unknown; src?: unknown }>,
  os?: TaskCoverage['os'],
): TaskCoverage {
  const byLine: Record<string, number> = { engine: 0, autonomy: 0, account: 0, other: 0 };
  let fieldTagged = 0, fieldMissing = 0, osLineTagged = 0;
  const unclassified: string[] = [];
  // v2 侧单独对账：domain 与业务线正交，不能拿来当 line，只能证明「这条 v2 任务已打标」
  let v2Total = 0, domainTagged = 0;
  const domainByValue: Record<string, number> = {};
  const missingNames: string[] = [];
  for (const t of tasks ?? []) {
    const c = classifyTask(t);
    byLine[c.line] = (byLine[c.line] ?? 0) + 1;
    if (c.source === 'field') fieldTagged += 1; else fieldMissing += 1;
    if (c.unclassified) unclassified.push(String(t?.name ?? ''));
    const src = t?.src;
    if (src === 'os') {
      if (String(t?.agentLine ?? '').trim()) osLineTagged += 1;
    } else if (src === 'v2') {
      v2Total += 1;
      const d = String(t?.domain ?? '').trim();
      if (d) { domainTagged += 1; domainByValue[d] = (domainByValue[d] ?? 0) + 1; }
      else missingNames.push(String(t?.name ?? ''));
    }
  }
  const v2 = v2Total > 0
    ? { total: v2Total, domainTagged, domainMissing: v2Total - domainTagged, domainByValue, missingNames }
    : undefined;
  return {
    total: (tasks ?? []).length, byLine, fieldTagged, fieldMissing, unclassified,
    os: os ? { ...os, lineTagged: osLineTagged } : undefined,
    v2,
  };
}
