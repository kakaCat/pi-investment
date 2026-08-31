#!/usr/bin/env python3
"""生成沪深300 csi300_data.json（M6-4 市场过滤验证）
从新浪源拉取 sh000300 日线，写出引擎 _inject_market_filter 读取的 JSON 格式：
{dates: [...], closes: [...]}
"""
import json, os, re, sys, time, requests

def fetch_sina_klines(symbol='sh000300', datalen=1100):
    url = (f'https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_='
           f'/CN_MarketDataService.getKLineData?symbol={symbol}&scale=240&ma=no&datalen={datalen}')
    r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
    r.raise_for_status()
    m = re.search(r'\((\[.*\])\)', r.text, re.S)
    if not m:
        raise ValueError(f'无法解析新浪响应: {r.text[:200]}')
    return json.loads(m.group(1))

def main():
    data = fetch_sina_klines()
    dates = [d['day'] for d in data]
    closes = [float(d['close']) for d in data]
    out = {'dates': dates, 'closes': closes}
    print(f'拉取 {len(dates)} 根日线: {dates[0]} ~ {dates[-1]}')
    targets = ['/tmp/csi300_data.json', os.path.join(os.path.dirname(__file__), '../.pi-invest/csi300_data.json')]
    os.makedirs(os.path.dirname(targets[1]), exist_ok=True)
    for t in targets:
        with open(t, 'w') as f:
            json.dump(out, f)
        print(f'写入: {t}')
    # 自检：注入逻辑要求 >=200 根
    assert len(closes) >= 200, f'数据不足: {len(closes)} < 200'

if __name__ == '__main__':
    main()
