# Quote 端点可行动错误诊断 设计文档

日期：2026-07-28
状态：已批准（用户确认）
分支：feat/quote-error-diagnostics

## 背景与问题

agent 调用 `GET /api/stock/00836/quote`（港股华润电力）收到：

```json
{"success": false, "error": "无法获取 00836 的实时行情"}
```

该错误对 agent 不可行动：不知道为什么失败、该改什么。实际失败链（已复现确认）：

| Provider | 对裸 `00836` 的处理 | 结果 |
|---|---|---|
| tencent（首选，本环境唯一稳定可用） | `_convert_to_tencent_code` 无港股支持 → `sz00836` → 腾讯返回 `v_pv_none_match` | None |
| sina | 拼成 `000836`（不相干 A 股，错误数据隐患）；hq.sinajs.cn 当前超时 | 失败 |
| eastmoney | 港股需 `.HK` 后缀；且 eastmoney 接口被 IP 封禁 | RemoteDisconnected |
| akshare | 识别 ≤5 位为港股走 `stock_hk_spot_em()`（底层 eastmoney） | RemoteDisconnected |

底层能力其实已具备：`DataProviderManager._try_providers` 已返回
`provider_errors`（每个数据源的具体失败原因）与 `attempted_sources`，但
`RealtimeQuoteService.get_realtime_quote` 将其丢弃，端点只能返回笼统文案。

同代码库已有参考实现：K 线端点 `GET /api/stock/{symbol}/history`
（Flask `quote_market.py:183-260`）失败时返回 `provider_errors` +
`_kline_failure_suggestion()` 生成的分类建议。本设计把同一模式应用到 quote 端点。

## 目标

quote 端点取数失败时，返回让 agent 能自我纠正的结构化诊断：
失败的数据源及各自原因、按原因分类的可行动建议。

## 非目标

- 不修复港股取数能力本身（tencent HK 支持等），那是独立工作线
- 不推广到 kline/分红等其他端点（kline 已有此模式）
- 不改 HTTP 状态码（realtime 失败保持 502，db 失败保持 404）
- 不改 `RealtimeQuoteService.get_realtime_quote` 签名（20+ 调用方）

## 设计

### 1. 路由改为直连 provider_manager（FastAPI + Flask 同步）

quote 路由仿照 `get_stock_history` 的做法，直接调用
`get_data_provider_manager().get_quote(clean_symbol)`，取代经
`RealtimeQuoteService` 中转。成功路径字段映射逻辑不变；失败时从 result
取 `error` / `attempted_sources` / `provider_errors`。

`RealtimeQuoteService` 不改动，继续服务其他调用方。

### 2. 失败响应体（realtime 失败与 auto 兜底失败，HTTP 502）

保留 `success` / `error` 契约字段，新增两个字段：

```json
{
  "success": false,
  "error": "All data providers failed (尝试数据源: tencent, sina, eastmoney, akshare)",
  "provider_errors": {
    "tencent": "腾讯无 sz00836 数据（代码不存在或该市场不支持）",
    "sina": "Exception: 新浪财经查询失败: ...",
    "eastmoney": "Exception: ... RemoteDisconnected ...",
    "akshare": "Exception: ... RemoteDisconnected ..."
  },
  "suggestion": "疑似港股代码：本接口主要支持 6 位 A 股代码，港股请尝试 00836.HK 格式；存在网络型失败：数据源可能临时限流/封禁，可稍后重试；也可用 source=db 查询本地缓存"
}
```

db 模式 404 与 invalid source 400 响应不变（parity 严格比对用例，缩小爆炸半径）。

### 3. `_quote_failure_suggestion(symbol, provider_errors)` 分类规则

仿 `_kline_failure_suggestion`，按顺序命中、分号连接：

1. 5 位纯数字或 `.HK` 结尾 →
   "疑似港股代码：本接口主要支持 6 位 A 股代码，港股请尝试 {XXXXX}.HK 格式"
2. `provider_errors` 含 timeout/Timeout/Connection/RemoteDisconnected/502/Max retries →
   "存在网络型失败：数据源可能临时限流/封禁，可稍后重试"
3. 6 位纯数字 →
   "请检查代码是否正确、是否已上市/已退市"
4. 以上均未命中 →
   "请检查代码格式（A股为 6 位数字，可带 .SH/.SZ 后缀）"
5. 始终追加 → "也可用 source=db 查询本地缓存（如有）"

### 4. quote provider 设置 `last_error`

4 个 quote provider（tencent/sina/eastmoney/akshare）在 `get_quote` 开头
`self.last_error = None`，返回 None 前写入具体原因，仿
`providers/kline/tencent.py:58-67` 既有写法。manager 第 116 行已会读取
`provider.last_error`，无需改 manager。

关键 case：tencent 对空响应（`v_pv_none_match`）设置
`f"腾讯无 {tencent_code} 数据（代码不存在或该市场不支持）"`。

### 5. Parity 保持

Flask `adapters/inbound/api/routes/quote_market.py` 的 `get_stock_quote`
做与 FastAPI `stock_async.py` 完全相同的改动。现有 parity 用例：

- `test_stock_quote_db_mode`（999999, source=db，严格比对）→ 不受影响（db 路径不改）
- `test_stock_quote_invalid_source`（400，严格比对）→ 不受影响
- `test_stock_quote_realtime`（600519 成功，结构比对）→ 不受影响

realtime 失败 502 路径无 parity 用例覆盖（外部数据源不可Mock化，本就是结构比对豁免区），
新增字段不破坏既有契约。

## 改动文件

- `quantsys-v2/adapters/inbound/fastapi_app/routes/stock_async.py` — quote 路由
- `quantsys-v2/adapters/inbound/api/routes/quote_market.py` — Flask 同步
- `quantsys-v2/adapters/outbound/datasources/providers/quote/{tencent,sina,eastmoney,akshare}.py` — `last_error`
- 测试：
  - `_quote_failure_suggestion` 分类规则单测（港股 5 位 / .HK / 网络型 / A 股 6 位 / 兜底）
  - 路由测试：mock provider_manager 失败，断言响应含 `provider_errors` + `suggestion`
  - tencent provider 空响应 `last_error` 单测
  - 跑通 `tests/migration/test_stocks_parity.py`

## 验证

1. 上述测试全绿
2. 启动 FastAPI 实测 `GET /api/stock/00836/quote` 返回结构化诊断
   （502 状态不变，`provider_errors`/`suggestion` 齐全）
3. `GET /api/stock/600519/quote` 成功路径响应不变
