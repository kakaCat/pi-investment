/**
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
