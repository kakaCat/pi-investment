# data-health 端点设计

## 背景

`agent-ts/src/infrastructure/tools/examples/smart-analysis-integration.ts` 中调用 `runQuantV2('analysis.data_health', { symbol })` 做 K 线/数据预检，但：

1. `V2_ROUTES` 未注册 `analysis.data_health`，运行时会抛 `命令 analysis.data_health 没有 v2 端点映射`。
2. quantsys-v2 后端没有对应 HTTP 端点。
3. 后端其实已存在 `StockCodeValidator.validate(symbol)`，其返回字段与示例的 `DataHealthResult` 接口完全吻合——只是未暴露为 HTTP 接口。

本设计实现该端点，让示例中的 `checkStockDataHealth`、`batchHealthCheck`、`morningAnalysisWorkflow` 真正可用。

## 目标

- 暴露 `GET /api/stock/<symbol>/data-health`，返回单票数据健康状况。
- 保持与示例 `DataHealthResult` 一致的 snake_case 契约。
- 修复 `StockCodeValidator.validate()` 的性能问题，使其适合批量调用。
- 在 agent-ts 的 `V2_ROUTES` 中注册 `analysis.data_health`。

## 架构

```
agent-ts examples/                  quantsys-v2
runQuantV2('analysis.data_health',  V2_ROUTES["analysis.data_health"]
  { symbol })  ─────────────────▶  GET /api/stock/{symbol}/data-health
                                     │
                                     ▼
                          StockCodeValidator.validate(symbol)
                                     │
                                     ▼
                        KlineORMRepository.count_daily_klines()
                        KlineORMRepository.get_date_range()
```

## 组件

### 1. quantsys-v2 新路由

文件：`quantsys-v2/adapters/inbound/api/routes/analysis.py`

新增：

```python
@analysis_bp.route('/api/stock/<symbol>/data-health', methods=['GET'])
@handle_api_error
def get_data_health(symbol):
    """
    单票数据健康检查

    Returns:
        {
          "success": true,
          "data": {
            "valid": boolean,
            "exists": boolean,
            "has_recent_data": boolean,
            "data_summary": {
              "first_date": string | null,
              "last_date": string | null,
              "total_records": int,
              "days_since_update": int
            },
            "suggestions": List[string],
            "similar_codes": List[string]
          }
        }
    """
    from application.services.stock_code_validator import StockCodeValidator
    validator = StockCodeValidator()
    result = validator.validate(symbol)

    # validate() 内部异常时返回 {..., error: str}，不是 HTTP 错误
    if result.get('error'):
        return jsonify({'success': False, 'error': result['error']}), 500

    return jsonify({'success': True, 'data': result}), 200
```

> 注意：不使用 `api_response()`，避免 `convert_keys_to_camel()` 把 snake_case 键转成 camelCase，破坏与 agent-ts 示例的契约。

### 2. StockCodeValidator 性能修复

文件：`quantsys-v2/application/services/stock_code_validator.py`

当前 `validate()` 调用 `KlineORMRepository.get_daily_klines('1990-01-01', now)` 并 `to_dicts()`，对每只股票加载全部历史 K 线。示例 `batchHealthCheck` 会串行遍历整个股票池，不可接受。

仓库层已提供轻量聚合查询：

- `count_daily_klines(symbol) -> int`
- `get_date_range(symbol) -> Optional[tuple]`（最早日期，最晚日期）

将 `_build_valid_result` 的输入从完整 K 线 DataFrame 改为这两个查询结果。实现步骤：

1. `validate()` 中规范化 symbol 后调用：
   - `count = kline_repo.count_daily_klines(normalized_symbol)`
   - `date_range = kline_repo.get_date_range(normalized_symbol)`
2. 若 `count == 0` 或 `date_range is None`，返回 `_build_invalid_result(normalized_symbol)`。
3. 否则调用新的 `_build_valid_result_from_range(symbol, count, date_range)`，返回结构与原 `_build_valid_result` 完全一致。

`has_recent_data` 阈值保持 **30 天** 不变（覆盖 A 股正常停牌/退市判断）。`days_since_update` 以最近交易日到当前日期的自然日差计算。

原 `_build_valid_result(self, symbol, klines_df)` 可保留作为兼容入口，或改为调用新方法后返回；唯一现有调用方 `SwingPointService` 的行为不变。

### 3. agent-ts 命令注册

文件：`agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`

在 `V2_ROUTES` 中与其他 `analysis.*` 命令放在一起：

```typescript
"analysis.swing_points": { path: "/api/analysis/swing-points", method: "POST" },
"analysis.data_health":  { path: "/api/stock/{symbol}/data-health", method: "GET" },
```

示例文件已修复信封解包和泛型，运行时调用链：`runQuantV2('analysis.data_health', { symbol })` → `result.data` 即 `DataHealthResult`。

## 数据流

### 成功路径（有效且有最近数据）

```
GET /api/stock/600519/data-health
  └─ StockCodeValidator.validate("600519")
      ├─ count_daily_klines("600519")  → 1200
      ├─ get_date_range("600519")      → ("2020-01-02", "2026-07-18")
      └─ _build_valid_result_from_range(...)
         → { valid:true, exists:true, has_recent_data:true,
             data_summary:{ first_date, last_date, total_records, days_since_update:1 },
             suggestions:[], similar_codes:[] }
  └─ jsonify({ success:true, data: result }) 200
```

### 无效/无数据路径

```
GET /api/stock/999999/data-health
  └─ count == 0
  └─ _build_invalid_result("999999")
     → { valid:false, exists:false, has_recent_data:false,
         suggestions:["该股票代码不存在或尚未录入数据", ...],
         similar_codes:[] }
  └─ jsonify({ success:true, data: result }) 200
```

> 无效代码不返回 4xx，让调用方按业务逻辑选择跳过或提示。

## 错误处理

| 场景 | 响应 | 触发条件 |
|---|---|---|
| symbol 有效且有最近数据 | 200 + `valid:true` | 正常 |
| symbol 无效或数据库无数据 | 200 + `valid:false` | 代码错误/未录入 |
| 数据陈旧 | 200 + `valid:true, has_recent_data:false` | 停牌/退市/未更新 |
| 服务内部异常 | 500 + `success:false` | DB 连接失败等 |

## 测试

### 后端测试

1. **路由测试** `quantsys-v2/tests/api/test_data_health_route.py`
   - 有效 symbol mock → 200 + `valid:true`
   - 无效 symbol mock → 200 + `valid:false`
   - 服务异常 mock → 500

2. **StockCodeValidator 单元测试** `quantsys-v2/tests/services/test_stock_code_validator.py`（新增或扩展现有）
   - 正常：验证 `count_daily_klines` 和 `get_date_range` 被调用，返回结构正确
   - 无数据：count == 0 时返回 invalid
   - 陈旧数据：last_date 超过 30 天，返回 `has_recent_data:false`

### 集成验证

1. 启动 quantsys-v2。
2. `curl http://127.0.0.1:5001/api/stock/600519/data-health`，确认 snake_case 字段。
3. agent-ts 跑 `runQuantV2('analysis.data_health', { symbol: '600519' })`，确认 `result.data.has_recent_data` 可访问。
4. `npm run build` 通过。

## 风险与回退

- **键名风格不一致**：新路由是唯一显式绕过 `api_response()` 的端点。原因：该契约最初就由 `StockCodeValidator` 和 agent-ts 示例共同定义，改为 camelCase 会同时修改两端。风险可控，因为消费者仅 agent 示例/工具。
- **StockCodeValidator 改动影响 SwingPointService**：返回结构不变，且现有 `swing_points` 测试应继续通过；若发现行为差异，回退该优化即可。

## 待实现清单

- [ ] 实现 `quantsys-v2/adapters/inbound/api/routes/analysis.py` 新路由
- [ ] 优化 `quantsys-v2/application/services/stock_code_validator.py` 使用聚合查询
- [ ] 在 `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts` 注册 `analysis.data_health`
- [ ] 后端路由测试
- [ ] 后端 StockCodeValidator 单元测试
- [ ] 手动集成验证
- [ ] `npm run build` 通过

## 决策记录

- 保持 snake_case 响应契约，以匹配现有 `DataHealthResult` 和 `StockCodeValidator` 输出。
- `has_recent_data` 阈值维持 30 天，覆盖 A 股正常停牌场景。
- 优化 `validate()` 使用聚合查询，避免 `batchHealthCheck` 加载全量历史 K 线。
