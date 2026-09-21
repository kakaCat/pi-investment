/**
 * 可交易性前置闸门（P1 / RFC 015 §4.6，2026-09-11，w-f436d4ea）
 *
 * 业务接线：把 trading_status 能力接进**真实下单路径**，使「可交易性」成为
 * 交易时段校验之后的又一道硬闸门——而不是一个躺在接口里没人用的能力。
 *
 * 方向语义（关键，勿简化成"一律 fail-closed"）：
 *   BUY  —— fail-closed：状态未知 / 停牌 / 涨停 / 跨源冲突 一律拒单
 *           （不盲目建仓；涨停价买入既难成交又易被套在情绪顶）
 *   SELL —— **仅确证停牌时拒单**；状态未知或涨停不阻塞
 *           （风险削减动作——止损/减仓——不得被"状态查不到"阻断）
 *
 * 复用后端 TradingStatusPolicy 的跨源保守裁决结果（cross_source_conflict 非空即
 * 已按不可交易裁决），此处只做**方向差异化**处置。
 */

export interface TradabilityGateResult {
  /** 非 null 即拒单（形状与 PortfolioTradeTool 既有闸门一致） */
  rejection: Record<string, any> | null;
  /** 放行说明（含数据时点，供留痕与 R-013 标注） */
  note: string;
}

export async function checkTradabilityGate(
  qv2: any, symbol: string, action: 'BUY' | 'SELL',
): Promise<TradabilityGateResult> {
  let st: any = null;
  try {
    const res: any = await qv2.getTradingStatus(symbol);
    if (res?.success === true) st = res.data ?? res;
  } catch {
    // 落到下面"状态未知"分支统一处理
  }

  // ---- 状态未知
  if (!st || st.tradeable === undefined) {
    if (action === 'BUY') {
      return {
        rejection: {
          success: false,
          blocked: true,
          reason:
            `可交易性校验未通过（fail-closed）：无法确认 ${symbol} 的交易状态，买入拒单。` +
            `RFC 015 §4.6 要求下单前必须通过 trading_status 校验——状态未知时不得盲目建仓。`,
          tradability: { symbol, status: 'unknown', action },
        },
        note: '',
      };
    }
    return { rejection: null, note: `⚠️ ${symbol} 交易状态未知；SELL 不阻塞（不阻断减仓/止损）` };
  }

  const limitPct = st.limit_ratio != null ? `${Math.round(Number(st.limit_ratio) * 100)}%` : '?';
  const asOf = st.as_of ?? '?';

  // ---- 停牌/退市：双方向都拒（交易所不会接受委托）
  if (st.is_suspended === true) {
    return {
      rejection: {
        success: false,
        blocked: true,
        reason: `${symbol} 停牌/退市，${action} 拒单。交易状态：${st.reason ?? ''}（as_of ${asOf}）`,
        tradability: { symbol, ...st, action },
      },
      note: '',
    };
  }

  // ---- 跨源冲突：后端已按保守裁决（不可交易）
  if (st.cross_source_conflict) {
    const detail = JSON.stringify(st.cross_source_conflict).slice(0, 300);
    if (action === 'BUY') {
      return {
        rejection: {
          success: false,
          blocked: true,
          reason: `${symbol} 交易状态跨源冲突，买入拒单（保守裁决）：${detail}`,
          tradability: { symbol, ...st, action },
        },
        note: '',
      };
    }
    return { rejection: null, note: `⚠️ ${symbol} 跨源冲突（${detail}）；SELL 不阻塞` };
  }

  // ---- 方向差异化
  if (action === 'BUY' && st.limit_up === true) {
    return {
      rejection: {
        success: false,
        blocked: true,
        reason: `${symbol} 涨停（限幅 ${limitPct}），买入拒单——涨停价难以成交，且易在情绪顶部接盘（as_of ${asOf}）`,
        tradability: { symbol, ...st, action },
      },
      note: '',
    };
  }

  if (action === 'BUY' && st.tradeable === false) {
    return {
      rejection: {
        success: false,
        blocked: true,
        reason: `${symbol} 当前不可交易，买入拒单。交易状态：${st.reason ?? ''}（as_of ${asOf}）`,
        tradability: { symbol, ...st, action },
      },
      note: '',
    };
  }

  return {
    rejection: null,
    note: `✅ 可交易性校验通过（${st.reason ?? ''}；限幅 ${limitPct}；as_of ${asOf}）`,
  };
}
