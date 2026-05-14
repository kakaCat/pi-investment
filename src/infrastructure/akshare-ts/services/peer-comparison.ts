/**
 * Peer comparison service
 */

import { get_stock_info, get_sector_list, get_stock_realtime_price, cleanSymbol } from "../data/market.js";
import { safeFloat, today } from "../../data-sources/http-client.js";

export async function compare_peers(symbol: string): Promise<string> {
  const clean = cleanSymbol(symbol);
  try {
    // 1. 获取目标股票基本信息（行业）
    const infoRaw = await get_stock_info(clean);
    const info = JSON.parse(infoRaw);
    if (info.error) return JSON.stringify({ error: info.error, symbol: clean });

    const sector: string = info.sector ?? info.industry ?? "";
    if (!sector) return JSON.stringify({ error: `无法获取 ${clean} 的行业信息`, symbol: clean });

    // 2. 获取同行业股票列表
    const sectorRaw = await get_sector_list();
    const sectorData = JSON.parse(sectorRaw);
    // sector_list 返回 { sectors: [...] } 或数组
    const sectors: Array<{ name: string; code?: string }> = Array.isArray(sectorData)
      ? sectorData
      : (sectorData.sectors ?? []);

    // 找匹配的板块名（模糊匹配）
    const matched = sectors.find(s => s.name && (s.name.includes(sector) || sector.includes(s.name)));
    const sectorName = matched?.name ?? sector;

    // 3. 并行：目标股票实时价
    const targetPriceRaw = await get_stock_realtime_price(clean);

    const targetPrice = JSON.parse(targetPriceRaw);

    // 4. 组装目标股信息
    const targetPE = safeFloat(info.pe ?? info.pe_dynamic ?? 0);
    const targetPB = safeFloat(info.pb ?? 0);
    const targetMktCap = safeFloat(info.market_cap_billion ?? info.total_market_cap ?? 0);
    const targetCurPrice = safeFloat(targetPrice.price ?? targetPrice.current_price ?? 0);
    const targetChangePct = safeFloat(targetPrice.change_pct ?? 0);

    return JSON.stringify({
      symbol: clean,
      name: info.name ?? clean,
      sector: sectorName,
      target: {
        symbol: clean,
        name: info.name ?? clean,
        current_price: targetCurPrice,
        change_pct: targetChangePct,
        pe: targetPE,
        pb: targetPB,
        market_cap_billion: targetMktCap,
        roe: safeFloat(info.roe ?? 0),
        gross_margin: safeFloat(info.gross_margin ?? 0),
      },
      peers_note: `同行业（${sectorName}）对比数据需调用 screen_stocks_quality("${sectorName}") 获取，` +
        `本工具已返回目标股基础数据，Agent 可并行调用 screen_stocks_quality 补充对比。`,
      usage_hint: `推荐工作流：1）已有目标股数据（见 target 字段）；2）调用 screen_stocks_quality(sector="${sectorName}") 拿同行 Top 10；3）对比 PE/ROE/毛利率/市值。`,
      data_date: today(),
    });
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}
