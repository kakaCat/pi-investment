# 错误事件处置：akshare get_index_daily DNS 解析失败（222154a8）

- **事件 ID**：`222154a8-77fe-478b-8042-28fdfd538ea7`（source=v2，severity=error，频次 1，首现/最近 2026-09-13 11:00）
- **处置窗口**：w-32314d00

## 1. 现象与日志上下文

```console
212468: akshare get_index_daily failed: HTTPSConnectionPool(host='finance.sina.com.cn', port=443):
        Max retries exceeded with url: /realstock/company/sh000300/hisdata/klc_kl.js?d=2020_2_4
        (Caused by NameResolutionError("Failed to resolve 'finance.sina.com.cn' [Errno 8] nodename nor servname provided"))
```

前后同一分钟的日志揭示了真正的性质——**机器级 DNS 抖动**：

```console
{"event": "Failed to fetch batch quotes: 全部数据源均未返回批量行情（tencent: HTTPConnectionPool(host='qt.gtimg.cn' ... 解析失败）"}
{"event": "获取指数历史: symbol=sh000300, start=2026-08-26, end=2026-09-11", "logger": "application.services.market_data_service"}
akshare get_index_daily failed: ... Failed to resolve 'finance.sina.com.cn'
基准指数获取失败: 暂无指数 sh000300 的历史数据
{"event": "GET /api/simulation/accounts - 200 - 33.788s"}
```

两个不同厂商的域名（sina / gtimg）在同一次运行里同时解析失败 → 不是某数据源故障。

## 2. 根因：环境抖动 + **代码缺口**（取数只有外网一条路）

`application/services/market_data_service.py::get_index_history` 当时**只调**
`provider_manager.get_index_daily(symbol)`（外网），从不读本地 `quant.index_daily`——
而库里 `000300.SH` 的数据当时完好（且当天刚由采集通道修好、每日刷新）。
于是一次 DNS 抖动就把「基准指数」整段打断，alpha/beta 基准丢失（调用方降级为无基准，只记 warning）。

## 3. 落地动作

1. **DB-first**：新增 `_index_daily_from_db()`，符号经 `utils.symbol_classifier.resolve_index_symbol`
   规范化（`sh000300` / `000300.SH` / `000300` → `000300.SH`；与指数同码的深市个股返回 None → 不走此路），
   命中本地库即直接返回（`source=db:quant.index_daily`）；本地无数据 / 非指数 / 读库异常 → 回退 provider（原行为不变）。
2. **契约对齐**：DB 路径返回键与 provider 路径完全一致（`date/open/high/low/close/volume/amount`），
   调用方无需改动；`amount=0` 视为"源未提供"（新浪指数接口无成交额列）→ 不再输出该键，避免误导成"成交额为 0"。
3. 重启 v2-api 生效。

## 4. 验证

```console
$ MarketDataService().get_index_history('sh000300','2026-08-26','2026-09-11')   # 线上直取
success= True  source= db:quant.index_daily  total= 13  elapsed= 0.05s
first= {'date': '2026-08-26', 'open': 4549.432, ..., 'close': 4590.794}
last = {'date': '2026-09-11', 'open': 4514.295, ..., 'close': 4510.155}

$ grep -c "get_index_daily failed" logs/launchd-stdout.log      → 1（仅 11:00 那次，此后 0 次）
$ DNS 现状: finance.sina.com.cn → 121.17.122.62 ; qt.gtimg.cn → 157.255.211.20   # 已恢复
$ GET /api/simulation/accounts                                  → 200 / 0.12s（10:59 那次 33.8s）

$ pytest tests/test_index_history_db_first.py -q                → 7 passed
```

用例覆盖：新浪风格符号规范化、空区间宽默认、非指数码不读库、读库异常降级为空、
**DB 有数时不得打外网（绊线）**、DB 空时回退 provider 且契约不带 DB 标记、amount=0 不输出。

## 5. 结论与遗留

- **事件性质**：环境（DNS 瞬时抖动）× 代码缺口（无 DB-first）叠加；缺口已修，抖动不再影响基准指数取数。
- 遗留：其它仍走外网的指数相关路径（如 `benchmark_comparison` 当日内存缓存之外的调用）也建议逐步收敛到 DB-first；
  需要的话我可以按"取数路径"再扫一遍，列出仍以网络为唯一来源的清单。