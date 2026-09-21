/**
 * 熔断输入可信度闸门（共享模块，2026-09-11 从 trading 包提升到 core-tool）
 *
 * 提升原因：M4 熔断工具与 regime_position_limit 工具都需要"别在坏输入上做不可逆风控动作"，
 * 而 agent_brain 2026-09-11 的假熔断（holdings_proxy 口径 -8.88% vs 真实 -0.13%）正是
 * 后者缺这道闸门所致——两处各写一套必然漂移，故收敛到本模块。
 *
 * 熔断输入可信度闸门（2026-09-11，w-f4aa1f6a，事故驱动）
 *
 * 事故：2026-09-10 08:30 熔断依据 -10.71% 触发并**真实卖出** 600887，但该读数源自净值快照
 * 收益口径错误（w-8f2c4cc5 修正 61 行后同一账户回撤为 -1.83%），账户同期总盈亏仍为 +1.13%。
 * 单点数据触发了不可逆的真实卖单——必须有独立复核，且复核不通过时**只报待复核、不下单**。
 *
 * 复核方式：用**净值序列自身**（/api/simulation/performance 的 total_value 峰谷）重新计算最大回撤，
 * 与熔断判定所用读数比对。这条路径与风险服务（基于快照日收益）是两条独立计算链，
 * 收益口径被写坏时二者会分离，正是要抓的破绽。
 *
 * 注意：/api/simulation/performance 自带的 data.max_drawdown 字段**不可用于此比对**
 * （实测为 0.43，符号与量纲均与风险口径 -1.83% 不一致），故只用 total_value 自行复算。
 */
export interface DrawdownTrust {
  trusted: boolean;
  reason: string;
  detail: Record<string, unknown>;
}

/** 峰谷法复算最大回撤（%）。样本不足或无有效值返回 null。 */
export function recomputeMaxDrawdown(values: number[]): { maxDrawdownPct: number; points: number } | null {
  const navs = values.filter((v) => Number.isFinite(v) && v > 0);
  if (!navs.length) return null;
  let peak = navs[0];
  let mdd = 0;
  for (const v of navs) {
    if (v > peak) peak = v;
    const dd = v / peak - 1;
    if (dd < mdd) mdd = dd;
  }
  return { maxDrawdownPct: +(mdd * 100).toFixed(4), points: navs.length };
}

/** 样本量门槛：净值点数 < 20 时回撤无统计意义 */
export const MIN_NAV_POINTS = 20;
/** 允许偏差（百分点）：两条独立链的口径差异容忍上限 */
export const DRAWDOWN_TOLERANCE_PP = 1.0;

export function assessDrawdownTrust(claimedPct: number, values: number[]): DrawdownTrust {
  const r = recomputeMaxDrawdown(values);
  if (!r) {
    return { trusted: false, reason: '净值序列为空或不可解析，无法复核回撤——按保守原则不下单', detail: {} };
  }
  if (r.points < MIN_NAV_POINTS) {
    return {
      trusted: false,
      reason: '净值样本仅 ' + r.points + ' 点（< ' + MIN_NAV_POINTS + '），回撤无统计意义——按保守原则不下单',
      detail: { points: r.points },
    };
  }
  const diff = Math.abs(r.maxDrawdownPct - claimedPct);
  if (diff > DRAWDOWN_TOLERANCE_PP) {
    return {
      trusted: false,
      reason:
        '声明回撤 ' + claimedPct.toFixed(2) + '% 无法由净值序列复现（复算 ' + r.maxDrawdownPct.toFixed(2) +
        '%，相差 ' + diff.toFixed(2) + 'pp > ' + DRAWDOWN_TOLERANCE_PP + 'pp）→ 判定输入不可信，待人工复核',
      detail: { claimed: claimedPct, recomputed: r.maxDrawdownPct, diff: +diff.toFixed(4), points: r.points },
    };
  }
  return {
    trusted: true,
    reason: '声明回撤可由净值序列复现（复算 ' + r.maxDrawdownPct.toFixed(2) + '%，样本 ' + r.points + ' 点）',
    detail: { claimed: claimedPct, recomputed: r.maxDrawdownPct, diff: +diff.toFixed(4), points: r.points },
  };
}
/**
 * 熔断触发判定（2026-09-11，agent_brain 假熔断事故驱动，w-f4aa1f6a）。
 *
 * 事故：agent_brain 仅 2 条净值快照 → 主口径 account_nav 不可用，risk_metrics 静默回退到
 * holdings_proxy（持仓等权、忽略现金权重、自述会高估风险）→ -8.88% → 被当账户回撤触发"强制减仓一半"；
 * 而原始净值序列复算仅 -0.13%、账户总盈亏 -0.53%、现金 75.6%。
 *
 * 规则（任一不满足即不触发，只记录）：
 *   ① 口径必须是 account_nav（代理/直传口径一律不触发）；
 *   ② 回撤必须可由净值序列复现（样本 >= 20、与复算差值 <= 容差）。
 */
export const BREAKER_THRESHOLD_PCT = -8;

export interface BreakerAssessment {
  triggered: boolean;
  untrusted: boolean;
  caliber: string;
  reason: string;
  detail: Record<string, unknown>;
}

export function assessBreakerTrigger(
  claimedDrawdownPct: number,
  caliber: string,
  navValues: number[],
): BreakerAssessment {
  const c = (caliber || '').trim();
  if (c && c !== 'account_nav') {
    return {
      triggered: false,
      untrusted: true,
      caliber: c,
      reason:
        '口径为 ' + c + '（非账户净值序列；holdings_proxy 忽略现金权重会高估风险）→ 熔断不触发，仅记录',
      detail: { claimed: claimedDrawdownPct, caliber: c },
    };
  }
  const trust = assessDrawdownTrust(claimedDrawdownPct, navValues);
  if (!trust.trusted) {
    return {
      triggered: false,
      untrusted: true,
      caliber: c || 'account_nav',
      reason: '未通过可信度闸门：' + trust.reason,
      detail: trust.detail,
    };
  }
  const triggered = claimedDrawdownPct <= BREAKER_THRESHOLD_PCT;
  return {
    triggered,
    untrusted: false,
    caliber: c || 'account_nav',
    reason: triggered
      ? '口径与复算均通过，回撤 ' + claimedDrawdownPct.toFixed(2) + '% <= 阈值 ' + BREAKER_THRESHOLD_PCT + '% → 熔断触发'
      : '口径与复算均通过，回撤 ' + claimedDrawdownPct.toFixed(2) + '% 未达阈值 ' + BREAKER_THRESHOLD_PCT + '%',
    detail: trust.detail,
  };
}
