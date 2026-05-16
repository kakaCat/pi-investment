export async function fetchSinaFxRate(pair: string): Promise<number> {
  if (pair !== "HKDCNY") {
    throw new Error(`不支持的汇率对: ${pair}`);
  }

  const url = `https://hq.sinajs.cn/list=${pair}`;

  try {
    const response = await fetch(url, {
      headers: {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      }
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const text = await response.text();

    const match = text.match(/"([^"]+)"/);
    if (!match) {
      throw new Error(`汇率数据解析失败: ${text.substring(0, 100)}`);
    }

    const parts = match[1].split(",");
    if (parts.length < 2) {
      throw new Error(`汇率数据格式错误: 字段数不足 (${parts.length})`);
    }

    // Sina FX format: "time,buy_rate,sell_rate,..."
    // We use the buy rate (index 1)
    const rate = parseFloat(parts[1]);

    if (isNaN(rate) || rate <= 0) {
      throw new Error(`无效的汇率值: ${parts[1]}`);
    }

    return rate;
  } catch (error) {
    throw new Error(`获取汇率失败: ${error instanceof Error ? error.message : String(error)}`);
  }
}
