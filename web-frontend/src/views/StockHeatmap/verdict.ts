/** agent 判断对错判定（spec §5.3）：判断方向与验证窗实际涨跌是否同向 */

export type Verdict = 'right' | 'wrong' | 'none'

/** 买信号后涨=对；卖信号后跌=对；涨跌幅为 0 不判 */
export function judgeSignal(type: 'buy' | 'sell', changePct: number): Verdict {
  if (changePct === 0) return 'none'
  const up = changePct > 0
  return (type === 'buy') === up ? 'right' : 'wrong'
}

/** 调入后涨=对；调出后跌=对 */
export function judgePoolEvent(action: 'add' | 'remove', changePct: number): Verdict {
  if (changePct === 0) return 'none'
  const up = changePct > 0
  return (action === 'add') === up ? 'right' : 'wrong'
}

/** 看好且行业涨=对；回避且行业跌=对；neutral 不判 */
export function judgeStance(
  stance: 'bullish' | 'bearish' | 'neutral',
  industryChangePct: number
): Verdict {
  if (stance === 'neutral' || industryChangePct === 0) return 'none'
  const up = industryChangePct > 0
  return (stance === 'bullish') === up ? 'right' : 'wrong'
}
