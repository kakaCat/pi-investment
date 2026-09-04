# 数据源失效修复与备用源扩容报告（D2）

**版本**: v1.0
**日期**: 2026-09-01
**作者**: investor (w-5b8aac2a)
**配套**: [工具覆盖度比对报告](./tool-coverage-gap-analysis.md)

---

## 一、背景

P0 情报工具落地时发现 akshare 数据源大面积失效。本报告记录根因诊断、修复与备用源扩容全过程。

## 二、根因诊断（5 个独立 bug，逐层抓出）

### Bug 1：akshare 接口签名变更（3 处 latent bug）

akshare 1.18.81 升级后接口签名变了，旧代码传参必炸：

| 位置 | 旧调用（必炸） | 正确调用 |
|---|---|---|
| `market/akshare.py` get_lhb_daily | `stock_lhb_stock_statistic_em(start_date=…)` —— 该参数已不存在（现 symbol=周期） | `stock_lhb_detail_em(start_date, end_date)` |
| `market/akshare.py` get_insider_trades | `stock_dzjy_hygtj(symbol=代码)` —— symbol 是周期'近三月'，传代码必 KeyError | `stock_inner_trade_xq()` 全市场按代码筛 |
| `stock/akshare.py` get_announcements | `stock_notice_report(symbol=代码)` —— symbol 是公告类型'全部' | `stock_individual_notice_report(security=代码, symbol='全部')` |
| `stock_data_service.py` get_insider_trades | 同上 dzjy bug | 同上修复 |

### Bug 2：FastAPI 路由注册顺序陷阱

`/lhb/{symbol}/{date}` 先于 `/lhb/daily/{date}` 注册 → "daily" 被当 symbol 吃掉。日志出现诡异记录 `No LHB data for daily on 2026-08-31`（"daily" 是 symbol 值），daily 端点从未到达。**固定路径必须先于参数路径注册**。

### Bug 3：float(None) 缓存格式化崩溃

`fund_flow_source._format_cache_response`：`float(item.get('large_net_inflow', 0))`——DB 里 sina 源只落了 main/small 两档，其余列为 NULL，`dict.get(key, 0)` 在 key 存在但值为 None 时返回 None → `float(None)` TypeError → **缓存命中却被误判失败** → 走 API → 东财 WAF 封禁 → 降级旧缓存 → 又炸 → 502。

修复：统一 `_f()` 安全转换（None/异常 → None）。

下游 `sentiment_service._analyze_fund_flow` 的 `large_rate > 0` 比较同样炸（None > 0 TypeError），一并修。

### Bug 4：NaN JSON 序列化崩溃

龙虎榜 DataFrame 含 NaN 列（上榜后5日/10日），`df.to_dict('records')` 直接返回 NaN → `ValueError: Out of range float values are not JSON compliant: nan` → 500。

**坑中坑**：`df.where(df.notna(), None)` 在 float64 列上**无效**（None 会被转回 NaN）！必须 `df.astype(object).where(df.notna(), None)`。共修 12 处（market 9 + stock 3）。

### Bug 5：东财 WAF 封禁（非代码问题）

`stock_individual_fund_flow` / `stock_sector_fund_flow_rank` / `stock_main_fund_flow` 等东财 push2 接口持续 ConnectionError——代码注释确认"2026-07-22 起观测到东财 WAF 对本机房 IP 的临时封禁，冷却后可恢复"。代码层无解，靠缓存+备用源兜底。

## 三、备用源扩容（新增 2 个 provider）

| 新 provider | 文件 | 接管能力 | 验证 |
|---|---|---|---|
| **ThsMarketProvider**（同花顺） | `providers/market/ths.py` | `get_sector_fund_flow`（行业资金流，东财被封时接管） | ✅ failover 生效：sector-flow 返回 `source: ths`，90 个行业 |
| **SinaMarketProvider**（新浪） | `providers/market/sina.py` | `get_lhb_daily` / `get_lhb_stock`（龙虎榜备用） | ✅ 直调 84 条 |

注册：`manager.market_providers = [akshare, ths, sina]`，按健康度动态排序 + 熔断器。

### 现有数据源全景（修复后）

| 数据域 | 主源 | 备用源 | 兜底 |
|---|---|---|---|
| K线 | DB → sina | baostock/tencent/akshare | 5 级链 |
| 个股资金流 | 东财（被封中） | — | **DB 缓存**（sina 每日落库 27709 行） |
| 板块资金流 | 东财（被封中） | **同花顺**（新） | — |
| 龙虎榜 | 东财 | **新浪**（新） | — |
| 涨停池 | 东财 | — | — |
| 公告/新闻 | 东财 | — | — |
| 内部人交易 | 东财（inner_trade_xq） | — | — |
| 两融 | sina | — | — |
| 北向 | akshare/ccass | — | — |

## 四、验证结果（7 端点全过）

| 端点 | 结果 |
|---|---|
| `/api/provider/lhb/daily/2026-08-31` | ✅ 84 条（source: akshare） |
| `/api/provider/lhb/detail/000011` | ✅ 2 条（空日期默认 30 天） |
| `/api/market/sector-flow` | ✅ **90 行业（source: ths——备用源接管）** |
| `/api/provider/stock/301591/insider-trades` | ✅ 49 条 |
| `/api/provider/stock/002241/announcements` | ✅ 50 条 |
| `/api/stock/002241/fund-flow` | ✅ source: cache（DB 缓存） |
| `/api/provider/zt-pool/2026-08-31` | ✅ 88 条 |

## 五、关键经验（已沉淀基因组候选）

1. **fastapi 路由顺序**：固定路径必须先于参数路径注册；日志里出现"daily 被当 symbol"这类诡异值时先怀疑路由匹配。
2. **pandas NaN 清理**：`df.where(df.notna(), None)` 在 float64 列上无效，必须 `astype(object)` 先行。修 NaN 后要用真实含 NaN 的数据验证 JSON 序列化（故障注入实测）。
3. **`dict.get(key, default)` 陷阱**：key 存在但值为 None 时返回 None 而非 default。`float(None)` 会炸。数值转换统一走安全转换函数。
4. **数据源封禁是常态**：东财 WAF 封 IP 是已观测现象，关键数据链路必须"实时源 + 每日落库缓存 + 备用源"三层兜底。
5. **直调 vs 服务差异**：直调正常但服务失败时，依次怀疑：进程未加载新代码（对比文件/进程时间戳）→ 路由匹配 → 中间层校验（_is_valid）→ 序列化。

## 六、产出文件

- 修复：`adapters/outbound/datasources/providers/market/akshare.py`（接口签名+NaN×9+默认日期）
- 修复：`adapters/outbound/datasources/providers/stock/akshare.py`（公告接口+NaN×3）
- 修复：`adapters/outbound/datasources/fund_flow_source.py`（_f 安全转换）
- 修复：`application/services/sentiment_service.py`（None 比较）
- 修复：`application/services/stock_data_service.py`（insider 接口）
- 修复：`adapters/inbound/fastapi_app/routes/data_provider_async.py`（路由顺序）
- 新增：`adapters/outbound/datasources/providers/market/ths.py`（同花顺）
- 新增：`adapters/outbound/datasources/providers/market/sina.py`（新浪）
- 注册：`adapters/outbound/datasources/manager.py`
