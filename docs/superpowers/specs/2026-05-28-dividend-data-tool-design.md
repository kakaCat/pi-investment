# 分红数据工具设计文档

**日期**: 2026-05-28  
**作者**: Claude (Opus 4.7)  
**状态**: 设计阶段

## 1. 概述

### 1.1 背景

当前 pi-investment 项目缺少分红数据查询能力，无法支持以下投资场景：
- 高股息策略筛选
- 分红稳定性分析
- 股息率估值
- 分红日历提醒

### 1.2 目标

为 TypeScript Agent 提供分红数据查询工具，支持：
1. 单股历史分红查询
2. 高股息股票批量筛选
3. 分红日历（即将除权除息的股票）

### 1.3 设计原则

- **轻量级实现** — 实时查询 akshare，无需数据库持久化
- **架构一致性** — 遵循现有六层架构，L1 数据管道层工具
- **易于扩展** — 预留数据源抽象层，支持未来切换到 tushare 或持久化存储
- **快速交付** — 2-3 天完成开发和测试

---

## 2. 架构设计

### 2.1 系统架构

```
TypeScript Agent (src/)
  └─ data_fetch_dividend 工具
      └─ QuantV2Client.getDividends()
          └─ HTTP 请求

quantsys-v2 Flask API (port 5001)
  └─ /api/stock/{symbol}/dividends
  └─ /api/dividends/screen
  └─ /api/dividends/calendar
      └─ DividendService
          └─ akshare API 调用
```

### 2.2 数据流

1. Agent 调用 `data_fetch_dividend` 工具
2. 工具通过 `QuantV2Client` 发送 HTTP 请求到 quantsys-v2
3. Flask 路由转发到 `DividendService`
4. Service 调用 akshare 获取实时数据
5. 格式化后返回给 Agent

### 2.3 技术栈

- **数据源**: akshare `stock_dividend_cninfo` (巨潮资讯)
- **后端**: Python 3.13 + Flask + pandas
- **前端**: TypeScript + @sinclair/typebox
- **通信**: HTTP REST API
- **缓存**: 可选 Redis (TTL 24小时)

---

## 3. 数据模型

### 3.1 分红记录 (DividendRecord)

```python
{
  "symbol": "600519.SH",           # 股票代码
  "name": "贵州茅台",               # 股票名称
  "fiscal_year": "2024",           # 分红年度
  "dividend_type": "年度分红",      # 分红类型（年度/中期）
  
  # 分红方案
  "cash_dividend": 21.00,          # 每10股派息（元）
  "cash_per_share": 2.10,          # 每股派息（元）
  "stock_dividend": 0.0,           # 每10股送股（股）
  "bonus_shares": 0.0,             # 每10股转增（股）
  "dividend_yield": 3.45,          # 股息率（%）
  "payout_ratio": 65.5,            # 分红率（分红/净利润，%）
  
  # 关键日期
  "announce_date": "2025-03-28",   # 预案公告日
  "shareholder_meeting_date": "2025-05-15",  # 股东大会日
  "ex_dividend_date": "2025-06-20",          # 除权除息日
  "record_date": "2025-06-19",               # 股权登记日
  "pay_date": "2025-06-21",                  # 派息日
  
  # 状态
  "status": "已实施",               # 状态（预案/股东大会通过/已实施）
  "total_dividend": 2520000000.0,  # 分红总额（元）
  "is_implemented": true           # 是否已实施
}
```

### 3.2 筛选参数 (ScreenParams)

```python
{
  "min_yield": 3.0,                # 最低股息率（%）
  "min_years": 5,                  # 最少连续分红年数
  "min_payout_ratio": 30.0,        # 最低分红率（%）
  "max_payout_ratio": 80.0,        # 最高分红率（%）
  "status": "已实施",               # 状态筛选
  "limit": 50                      # 返回数量限制
}
```

### 3.3 分红摘要 (DividendSummary)

```python
{
  "consecutive_years": 10,         # 连续分红年数
  "avg_yield": 3.2,                # 平均股息率（%）
  "total_cash_dividend": 18.50     # 累计每股派息（元）
}
```

---

## 4. API 端点设计

### 4.1 单股分红查询

**端点**: `GET /api/stock/{symbol}/dividends`

**请求参数**:
- `symbol` (path, required) — 股票代码（如 600519.SH）
- `years` (query, optional) — 查询最近N年，默认10年

**响应示例**:
```json
{
  "success": true,
  "symbol": "600519.SH",
  "name": "贵州茅台",
  "total_records": 10,
  "dividends": [
    {
      "fiscal_year": "2024",
      "cash_per_share": 2.10,
      "dividend_yield": 3.45,
      "ex_dividend_date": "2025-06-20",
      "status": "已实施"
    }
  ],
  "summary": {
    "consecutive_years": 10,
    "avg_yield": 3.2,
    "total_cash_dividend": 18.50
  }
}
```

**错误响应**:
```json
{
  "success": false,
  "error": "股票代码不存在或暂无分红记录"
}
```

### 4.2 批量筛选

**端点**: `POST /api/dividends/screen`

**请求体**:
```json
{
  "min_yield": 3.0,
  "min_years": 5,
  "min_payout_ratio": 30.0,
  "limit": 50
}
```

**响应示例**:
```json
{
  "success": true,
  "total": 45,
  "stocks": [
    {
      "symbol": "600519.SH",
      "name": "贵州茅台",
      "latest_yield": 3.45,
      "consecutive_years": 10,
      "avg_payout_ratio": 65.5
    }
  ]
}
```

### 4.3 分红日历

**端点**: `GET /api/dividends/calendar`

**请求参数**:
- `start_date` (query, required) — 开始日期 (YYYY-MM-DD)
- `end_date` (query, required) — 结束日期 (YYYY-MM-DD)
- `event` (query, optional) — 事件类型 (ex_dividend/record_date/pay_date)，默认 ex_dividend

**响应示例**:
```json
{
  "success": true,
  "period": "2026-06-01 至 2026-06-30",
  "event_type": "除权除息日",
  "total": 23,
  "events": [
    {
      "date": "2026-06-20",
      "symbol": "600519.SH",
      "name": "贵州茅台",
      "cash_per_share": 2.10,
      "dividend_yield": 3.45
    }
  ]
}
```

---

## 5. quantsys-v2 实现

### 5.1 DividendService

**文件**: `quantsys-v2/services/dividend_service.py`

**核心方法**:

```python
class DividendService(BaseService):
    """分红数据服务"""
    
    def __init__(self):
        super().__init__()
        self.data_source = AkshareDividendSource()
    
    def get_stock_dividends(self, symbol: str, years: int = 10) -> dict:
        """
        获取单股历史分红
        
        Args:
            symbol: 股票代码（如 600519.SH）
            years: 查询最近N年
            
        Returns:
            {
                "success": bool,
                "symbol": str,
                "name": str,
                "dividends": List[DividendRecord],
                "summary": DividendSummary
            }
        """
        try:
            # 1. 调用 akshare
            df = self.data_source.fetch_dividends(symbol)
            
            # 2. 数据清洗和转换
            records = self._transform_records(df, years)
            
            # 3. 计算摘要指标
            summary = self._calculate_summary(records)
            
            return {
                "success": True,
                "symbol": symbol,
                "name": records[0]["name"] if records else "",
                "total_records": len(records),
                "dividends": records,
                "summary": summary
            }
        except Exception as e:
            logger.error(f"Failed to get dividends for {symbol}: {e}")
            return {"success": False, "error": str(e)}
    
    def screen_dividend_stocks(self, params: dict) -> dict:
        """
        筛选高股息股票
        
        Args:
            params: {
                "min_yield": float,
                "min_years": int,
                "min_payout_ratio": float,
                "limit": int
            }
            
        Returns:
            {
                "success": bool,
                "total": int,
                "stocks": List[dict]
            }
        """
        try:
            # 1. 获取股票池（沪深300 + 创业板50 + 科创50）
            stock_pool = self._get_stock_pool()
            
            # 2. 并发查询分红数据
            results = self._batch_query_dividends(stock_pool)
            
            # 3. 应用筛选条件
            filtered = self._apply_filters(results, params)
            
            # 4. 排序并限制数量
            sorted_stocks = sorted(
                filtered, 
                key=lambda x: x["latest_yield"], 
                reverse=True
            )[:params.get("limit", 50)]
            
            return {
                "success": True,
                "total": len(sorted_stocks),
                "stocks": sorted_stocks
            }
        except Exception as e:
            logger.error(f"Failed to screen dividend stocks: {e}")
            return {"success": False, "error": str(e)}
    
    def get_dividend_calendar(
        self, 
        start_date: str, 
        end_date: str, 
        event: str = "ex_dividend"
    ) -> dict:
        """
        分红日历
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            event: 事件类型 (ex_dividend/record_date/pay_date)
            
        Returns:
            {
                "success": bool,
                "period": str,
                "event_type": str,
                "total": int,
                "events": List[dict]
            }
        """
        try:
            # 1. 获取股票池
            stock_pool = self._get_stock_pool()
            
            # 2. 批量查询分红数据
            results = self._batch_query_dividends(stock_pool)
            
            # 3. 筛选日期范围内的事件
            events = self._filter_by_date_range(
                results, start_date, end_date, event
            )
            
            # 4. 按日期排序
            sorted_events = sorted(events, key=lambda x: x["date"])
            
            event_type_map = {
                "ex_dividend": "除权除息日",
                "record_date": "股权登记日",
                "pay_date": "派息日"
            }
            
            return {
                "success": True,
                "period": f"{start_date} 至 {end_date}",
                "event_type": event_type_map.get(event, "未知事件"),
                "total": len(sorted_events),
                "events": sorted_events
            }
        except Exception as e:
            logger.error(f"Failed to get dividend calendar: {e}")
            return {"success": False, "error": str(e)}
    
    # 私有辅助方法
    def _transform_records(self, df: pd.DataFrame, years: int) -> List[dict]:
        """转换 akshare 数据为标准格式"""
        pass
    
    def _calculate_summary(self, records: List[dict]) -> dict:
        """计算分红摘要指标"""
        pass
    
    def _get_stock_pool(self) -> List[str]:
        """获取股票池（沪深300 + 创业板50 + 科创50）"""
        pass
    
    def _batch_query_dividends(self, symbols: List[str]) -> List[dict]:
        """并发批量查询分红数据"""
        pass
    
    def _apply_filters(self, results: List[dict], params: dict) -> List[dict]:
        """应用筛选条件"""
        pass
    
    def _filter_by_date_range(
        self, 
        results: List[dict], 
        start: str, 
        end: str, 
        event: str
    ) -> List[dict]:
        """筛选日期范围内的事件"""
        pass
```

### 5.2 数据源抽象层

**文件**: `quantsys-v2/services/dividend_data_source.py`

```python
from abc import ABC, abstractmethod
import pandas as pd

class DividendDataSource(ABC):
    """分红数据源抽象基类"""
    
    @abstractmethod
    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        """获取股票分红数据"""
        pass

class AkshareDividendSource(DividendDataSource):
    """akshare 数据源实现"""
    
    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        import akshare as ak
        # 移除后缀（akshare 只需要6位代码）
        code = symbol.split('.')[0]
        return ak.stock_dividend_cninfo(symbol=code)

class TushareDividendSource(DividendDataSource):
    """tushare 数据源实现（预留）"""
    
    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        # 预留实现
        raise NotImplementedError("Tushare source not implemented yet")
```

### 5.3 Flask 路由

**文件**: `quantsys-v2/api/routes/dividends.py`

```python
from flask import Blueprint, request, jsonify
from services.dividend_service import DividendService
from api.decorators import handle_errors
import logging

logger = logging.getLogger(__name__)
dividends_bp = Blueprint('dividends', __name__)
service = DividendService()

@dividends_bp.route('/api/stock/<symbol>/dividends', methods=['GET'])
@handle_errors
def get_dividends(symbol):
    """获取单股分红数据"""
    years = request.args.get('years', 10, type=int)
    logger.info(f"Fetching dividends for {symbol}, years={years}")
    
    result = service.get_stock_dividends(symbol, years)
    return jsonify(result)

@dividends_bp.route('/api/dividends/screen', methods=['POST'])
@handle_errors
def screen_dividends():
    """筛选高股息股票"""
    params = request.get_json()
    logger.info(f"Screening dividend stocks with params: {params}")
    
    result = service.screen_dividend_stocks(params)
    return jsonify(result)

@dividends_bp.route('/api/dividends/calendar', methods=['GET'])
@handle_errors
def dividend_calendar():
    """分红日历"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    event = request.args.get('event', 'ex_dividend')
    
    if not start_date or not end_date:
        return jsonify({
            "success": False,
            "error": "start_date and end_date are required"
        }), 400
    
    logger.info(f"Fetching dividend calendar: {start_date} to {end_date}, event={event}")
    
    result = service.get_dividend_calendar(start_date, end_date, event)
    return jsonify(result)
```

**注册 Blueprint** (`api/server.py`):

```python
from api.routes.dividends import dividends_bp
app.register_blueprint(dividends_bp)
```

---

## 6. TypeScript Agent 工具实现

### 6.1 类型定义

**文件**: `src/infrastructure/quant/types.ts` (扩展)

```typescript
export interface DividendRecord {
  symbol: string;
  name: string;
  fiscal_year: string;
  dividend_type: string;
  cash_dividend: number;
  cash_per_share: number;
  stock_dividend: number;
  bonus_shares: number;
  dividend_yield: number;
  payout_ratio: number;
  announce_date: string;
  shareholder_meeting_date: string;
  ex_dividend_date: string;
  record_date: string;
  pay_date: string;
  status: string;
  total_dividend: number;
  is_implemented: boolean;
}

export interface DividendSummary {
  consecutive_years: number;
  avg_yield: number;
  total_cash_dividend: number;
}

export interface DividendResponse {
  success: boolean;
  error?: string;
  
  // single 模式
  symbol?: string;
  name?: string;
  total_records?: number;
  dividends?: DividendRecord[];
  summary?: DividendSummary;
  
  // screen 模式
  total?: number;
  stocks?: Array<{
    symbol: string;
    name: string;
    latest_yield: number;
    consecutive_years: number;
    avg_payout_ratio: number;
  }>;
  
  // calendar 模式
  period?: string;
  event_type?: string;
  events?: Array<{
    date: string;
    symbol: string;
    name: string;
    cash_per_share: number;
    dividend_yield: number;
  }>;
}
```

### 6.2 QuantV2Client 扩展

**文件**: `src/infrastructure/quant/quant-v2-client.ts` (扩展)

```typescript
export async function getDividends(
  params: {
    mode: 'single' | 'screen' | 'calendar';
    symbol?: string;
    years?: number;
    min_yield?: number;
    min_years?: number;
    min_payout_ratio?: number;
    max_payout_ratio?: number;
    limit?: number;
    start_date?: string;
    end_date?: string;
    event?: string;
  }
): Promise<DividendResponse> {
  const { mode, symbol, years, ...rest } = params;
  
  try {
    if (mode === 'single') {
      if (!symbol) {
        throw new QuantV2Error('single 模式必须提供 symbol 参数');
      }
      
      const url = `${V2_API_BASE}/api/stock/${symbol}/dividends?years=${years || 10}`;
      const response = await fetch(url, {
        signal: AbortSignal.timeout(V2_TIMEOUT_MS)
      });
      
      if (!response.ok) {
        throw new QuantV2Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.json();
    }
    
    if (mode === 'screen') {
      const url = `${V2_API_BASE}/api/dividends/screen`;
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rest),
        signal: AbortSignal.timeout(V2_TIMEOUT_MS)
      });
      
      if (!response.ok) {
        throw new QuantV2Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.json();
    }
    
    if (mode === 'calendar') {
      const { start_date, end_date, event = 'ex_dividend' } = rest;
      
      if (!start_date || !end_date) {
        throw new QuantV2Error('calendar 模式必须提供 start_date 和 end_date 参数');
      }
      
      const url = `${V2_API_BASE}/api/dividends/calendar?start_date=${start_date}&end_date=${end_date}&event=${event}`;
      const response = await fetch(url, {
        signal: AbortSignal.timeout(V2_TIMEOUT_MS)
      });
      
      if (!response.ok) {
        throw new QuantV2Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.json();
    }
    
    throw new QuantV2Error(`未知查询模式: ${mode}`);
  } catch (error) {
    if (error instanceof QuantV2Error) {
      throw error;
    }
    throw new QuantV2Error(`分红数据查询失败: ${error instanceof Error ? error.message : String(error)}`);
  }
}
```

文档第一部分已写入。继续写入剩余部分？
### 6.3 工具定义

**文件**: `src/infrastructure/tools/data/fetch-dividend-tool.ts`

```typescript
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { getDividends } from "../../quant/quant-v2-client.js";
import { formatDividendData } from "../../quant/formatters.js";

export const dataFetchDividendTool: ToolDefinition = {
  name: "data_fetch_dividend",
  label: "获取分红数据",
  description:
    "L1 数据管道工具：获取股票分红数据。支持三种模式：" +
    "1) single - 查询单只股票历史分红记录；" +
    "2) screen - 筛选高股息股票；" +
    "3) calendar - 查询分红日历（即将除权除息的股票）。",

  parameters: Type.Object({
    mode: Type.Union([
      Type.Literal("single"),
      Type.Literal("screen"),
      Type.Literal("calendar")
    ], {
      description: "查询模式：single=单股查询, screen=批量筛选, calendar=分红日历"
    }),
    
    // single 模式参数
    symbol: Type.Optional(Type.String({
      description: "股票代码（single模式必填，如 600519.SH）"
    })),
    years: Type.Optional(Type.Number({
      description: "查询最近N年（single模式，默认10年）"
    })),
    
    // screen 模式参数
    min_yield: Type.Optional(Type.Number({
      description: "最低股息率%（screen模式）"
    })),
    min_years: Type.Optional(Type.Number({
      description: "最少连续分红年数（screen模式）"
    })),
    min_payout_ratio: Type.Optional(Type.Number({
      description: "最低分红率%（screen模式）"
    })),
    max_payout_ratio: Type.Optional(Type.Number({
      description: "最高分红率%（screen模式）"
    })),
    limit: Type.Optional(Type.Number({
      description: "返回数量限制（screen模式，默认50）"
    })),
    
    // calendar 模式参数
    start_date: Type.Optional(Type.String({
      description: "开始日期 YYYY-MM-DD（calendar模式必填）"
    })),
    end_date: Type.Optional(Type.String({
      description: "结束日期 YYYY-MM-DD（calendar模式必填）"
    })),
    event: Type.Optional(Type.String({
      description: "事件类型（calendar模式）：ex_dividend=除权除息日, record_date=股权登记日, pay_date=派息日"
    }))
  }),

  execute: async (_toolCallId, params) => {
    try {
      // 参数验证
      if (params.mode === 'single' && !params.symbol) {
        return {
          content: [{ type: "text", text: "single 模式必须提供 symbol 参数" }],
          details: undefined
        };
      }
      
      if (params.mode === 'calendar' && (!params.start_date || !params.end_date)) {
        return {
          content: [{ type: "text", text: "calendar 模式必须提供 start_date 和 end_date 参数" }],
          details: undefined
        };
      }
      
      // 调用 v2 API
      const data = await getDividends(params);
      
      if (!data.success) {
        return {
          content: [{ type: "text", text: `查询失败: ${data.error || '未知错误'}` }],
          details: undefined
        };
      }
      
      // 格式化输出
      const formattedText = formatDividendData(data, params.mode);
      
      return {
        content: [{ type: "text", text: formattedText }],
        details: undefined
      };
    } catch (error) {
      return {
        content: [{
          type: "text",
          text: `分红数据获取失败: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: undefined
      };
    }
  }
};
```

### 6.4 数据格式化

**文件**: `src/infrastructure/quant/formatters.ts` (扩展)

```typescript
export function formatDividendData(data: DividendResponse, mode: string): string {
  if (!data.success) {
    return `查询失败: ${data.error || '未知错误'}`;
  }
  
  if (mode === 'single') {
    const { symbol, name, dividends, summary } = data;
    let output = `【${name} (${symbol}) 分红历史】\n\n`;
    
    if (summary) {
      output += `连续分红: ${summary.consecutive_years}年\n`;
      output += `平均股息率: ${summary.avg_yield.toFixed(2)}%\n`;
      output += `累计每股派息: ${summary.total_cash_dividend.toFixed(2)}元\n\n`;
    }
    
    output += `近期分红记录:\n`;
    dividends?.slice(0, 5).forEach(d => {
      output += `  ${d.fiscal_year}年: 每股${d.cash_per_share.toFixed(2)}元, `;
      output += `股息率${d.dividend_yield.toFixed(2)}%, `;
      output += `除权日${d.ex_dividend_date}, ${d.status}\n`;
    });
    
    if (dividends && dividends.length > 5) {
      output += `\n... 共 ${dividends.length} 条记录\n`;
    }
    
    return output;
  }
  
  if (mode === 'screen') {
    const { total, stocks } = data;
    let output = `【高股息股票筛选结果】共 ${total} 只\n\n`;
    
    stocks?.slice(0, 20).forEach((s, i) => {
      output += `${i + 1}. ${s.name} (${s.symbol})\n`;
      output += `   股息率: ${s.latest_yield.toFixed(2)}%, `;
      output += `连续分红: ${s.consecutive_years}年, `;
      output += `平均分红率: ${s.avg_payout_ratio.toFixed(1)}%\n`;
    });
    
    if (stocks && stocks.length > 20) {
      output += `\n... 仅显示前20只，共 ${stocks.length} 只\n`;
    }
    
    return output;
  }
  
  if (mode === 'calendar') {
    const { period, event_type, total, events } = data;
    let output = `【分红日历 - ${event_type}】\n`;
    output += `时间范围: ${period}\n`;
    output += `共 ${total} 只股票\n\n`;
    
    events?.forEach(e => {
      output += `${e.date} - ${e.name} (${e.symbol})\n`;
      output += `  每股派息: ${e.cash_per_share.toFixed(2)}元, 股息率: ${e.dividend_yield.toFixed(2)}%\n`;
    });
    
    return output;
  }
  
  return '未知查询模式';
}
```

### 6.5 工具注册

**文件**: `src/infrastructure/tools/data/index.ts` (扩展)

```typescript
import { dataFetchDividendTool } from './fetch-dividend-tool.js';

export const dataTools = [
  dataFetchStockTool,
  dataFetchKlineTool,
  dataFetchFinancialTool,
  dataFetchDividendTool,  // 新增
];
```

---

## 7. 错误处理

### 7.1 错误类型

| 错误类型 | 处理策略 | 返回信息 |
|---------|---------|---------|
| 参数缺失 | 工具层验证，立即返回 | "single 模式必须提供 symbol 参数" |
| 股票代码不存在 | Service 层捕获，返回空结果 | "该股票暂无分红记录" |
| akshare API 失败 | Service 层捕获，记录日志 | "数据源查询失败: {error}" |
| 网络超时 | Client 层捕获，30秒超时 | "请求超时，请稍后重试" |
| 数据格式异常 | Service 层捕获，返回错误 | "数据解析失败" |

### 7.2 日志记录

**Service 层**:
```python
logger.info(f"Fetching dividends for {symbol}, years={years}")
logger.error(f"Failed to get dividends for {symbol}: {e}")
```

**工具层**:
```typescript
// 成功
logger.debug(`dividend tool executed: mode=${params.mode}, success=true`);

// 失败
logger.error(`dividend tool failed: mode=${params.mode}, error=${error.message}`);
```

### 7.3 降级策略

1. **akshare 不可用** — 返回友好错误，建议稍后重试
2. **部分股票查询失败** — screen/calendar 模式跳过失败的股票，返回成功的结果
3. **数据不完整** — 缺失字段填充默认值（如 dividend_yield = 0）

---

## 8. 性能优化

### 8.1 批量查询优化

**并发控制**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def _batch_query_dividends(self, symbols: List[str]) -> List[dict]:
    """并发批量查询分红数据"""
    results = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_symbol = {
            executor.submit(self._query_single_stock, symbol): symbol
            for symbol in symbols
        }
        
        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                data = future.result(timeout=5)
                if data:
                    results.append(data)
            except Exception as e:
                logger.warning(f"Failed to query {symbol}: {e}")
                continue
    
    return results
```

### 8.2 缓存策略（可选）

**Redis 缓存**:
```python
from functools import wraps
import redis
import json

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_result(ttl=86400):
    """缓存装饰器，TTL 默认 24 小时"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"dividend:{func.__name__}:{args}:{kwargs}"
            
            # 尝试从缓存读取
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 写入缓存
            redis_client.setex(cache_key, ttl, json.dumps(result))
            
            return result
        return wrapper
    return decorator

# 使用示例
@cache_result(ttl=86400)
def get_stock_dividends(self, symbol: str, years: int = 10):
    # ... 实现
```

### 8.3 性能指标

| 场景 | 目标响应时间 | 优化措施 |
|-----|------------|---------|
| 单股查询 | < 3秒 | akshare 直接查询 |
| 批量筛选（50只） | < 30秒 | 10线程并发 + 5秒超时 |
| 分红日历（30天） | < 20秒 | 限制股票池 + 并发查询 |

---

## 9. 测试策略

### 9.1 单元测试

**文件**: `quantsys-v2/tests/services/test_dividend_service.py`

**测试用例**:
- ✅ 单股查询成功
- ✅ 单股查询失败（无效代码）
- ✅ 批量筛选成功
- ✅ 批量筛选空结果
- ✅ 分红日历成功
- ✅ 分红日历空结果
- ✅ 数据转换正确性
- ✅ 摘要计算正确性

**覆盖率目标**: > 80%

### 9.2 集成测试

**文件**: `quantsys-v2/tests/api/test_dividends_routes.py`

**测试用例**:
- ✅ GET /api/stock/{symbol}/dividends 成功
- ✅ GET /api/stock/{symbol}/dividends 参数验证
- ✅ POST /api/dividends/screen 成功
- ✅ POST /api/dividends/screen 参数验证
- ✅ GET /api/dividends/calendar 成功
- ✅ GET /api/dividends/calendar 参数验证

**覆盖率目标**: > 90%

### 9.3 TypeScript 工具测试

**文件**: `src/infrastructure/tools/data/fetch-dividend-tool.test.ts`

**测试用例**:
- ✅ single 模式成功
- ✅ single 模式参数验证
- ✅ screen 模式成功
- ✅ calendar 模式成功
- ✅ 错误处理
- ✅ 格式化输出正确性

**覆盖率目标**: > 75%

### 9.4 端到端测试

**手动测试流程**:
1. 启动 quantsys-v2 服务
2. 启动 TypeScript Agent
3. 测试单股查询: `data_fetch_dividend(mode="single", symbol="600519.SH")`
4. 测试批量筛选: `data_fetch_dividend(mode="screen", min_yield=3.0)`
5. 测试分红日历: `data_fetch_dividend(mode="calendar", start_date="2026-06-01", end_date="2026-06-30")`

---

## 10. 实施计划

### 10.1 开发任务

**Phase 1: quantsys-v2 后端（1.5天）**

- [ ] 创建 `services/dividend_data_source.py` — 数据源抽象层
- [ ] 创建 `services/dividend_service.py` — 核心业务逻辑
  - [ ] `get_stock_dividends()` 方法
  - [ ] `screen_dividend_stocks()` 方法
  - [ ] `get_dividend_calendar()` 方法
  - [ ] 私有辅助方法
- [ ] 创建 `api/routes/dividends.py` — Flask 路由
  - [ ] GET /api/stock/{symbol}/dividends
  - [ ] POST /api/dividends/screen
  - [ ] GET /api/dividends/calendar
- [ ] 在 `api/server.py` 注册 Blueprint
- [ ] 编写单元测试 `tests/services/test_dividend_service.py`
- [ ] 编写集成测试 `tests/api/test_dividends_routes.py`

**Phase 2: TypeScript Agent 工具（0.5天）**

- [ ] 扩展 `src/infrastructure/quant/types.ts` — 添加类型定义
- [ ] 扩展 `src/infrastructure/quant/quant-v2-client.ts` — 添加 `getDividends()` 方法
- [ ] 创建 `src/infrastructure/tools/data/fetch-dividend-tool.ts` — 工具定义
- [ ] 扩展 `src/infrastructure/quant/formatters.ts` — 添加 `formatDividendData()` 函数
- [ ] 在 `src/infrastructure/tools/data/index.ts` 注册工具
- [ ] 编写工具测试 `src/infrastructure/tools/data/fetch-dividend-tool.test.ts`

**Phase 3: 测试和文档（0.5天）**

- [ ] 端到端测试（启动服务 + Agent 调用）
- [ ] 更新 `CLAUDE.md` 工具文档
- [ ] 编写使用示例
- [ ] 性能测试（响应时间、并发能力）

### 10.2 交付物清单

**quantsys-v2 后端**:
- `services/dividend_data_source.py`
- `services/dividend_service.py`
- `api/routes/dividends.py`
- `tests/services/test_dividend_service.py`
- `tests/api/test_dividends_routes.py`

**TypeScript Agent**:
- `src/infrastructure/quant/types.ts` (扩展)
- `src/infrastructure/quant/quant-v2-client.ts` (扩展)
- `src/infrastructure/tools/data/fetch-dividend-tool.ts`
- `src/infrastructure/tools/data/fetch-dividend-tool.test.ts`
- `src/infrastructure/quant/formatters.ts` (扩展)
- `src/infrastructure/tools/data/index.ts` (扩展)

**文档**:
- 更新 `CLAUDE.md` 工具说明
- 使用示例文档

### 10.3 验收标准

1. ✅ 所有单元测试通过（覆盖率 > 80%）
2. ✅ 所有集成测试通过（覆盖率 > 90%）
3. ✅ Agent 能成功调用三种模式
4. ✅ 错误处理完善，返回友好提示
5. ✅ 单股查询响应时间 < 3秒
6. ✅ 批量筛选（50只）响应时间 < 30秒
7. ✅ 分红日历（30天）响应时间 < 20秒
8. ✅ 文档完整，包含使用示例

---

## 11. 风险和依赖

### 11.1 技术风险

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| akshare API 不稳定 | 查询失败率高 | 添加重试机制 + 降级提示 |
| akshare 接口变更 | 数据解析失败 | 数据源抽象层 + 版本锁定 |
| 并发查询性能瓶颈 | 批量筛选超时 | 限制并发数 + 超时控制 |
| 数据质量问题 | 部分股票无数据 | 空结果处理 + 友好提示 |

### 11.2 依赖项

**外部依赖**:
- akshare >= 1.12.0
- pandas >= 2.0.0
- Flask >= 3.0.0
- redis (可选)

**内部依赖**:
- quantsys-v2 服务必须运行在 127.0.0.1:5001
- TypeScript Agent 需要配置 `QUANTSYS_V2_API_URL` 环境变量

### 11.3 数据质量

**已知问题**:
- 小盘股、新股可能无分红记录
- 部分历史数据可能不完整
- 股息率计算依赖当前股价，可能存在时间差

**处理策略**:
- 空数据返回友好提示
- 缺失字段填充默认值
- 在文档中说明数据来源和局限性

---

## 12. 未来扩展

### 12.1 持久化存储

**触发条件**:
- 查询量 > 1000次/天
- 需要历史趋势分析
- 需要复杂聚合查询

**实施方案**:
1. 新增数据库表 `quant.dividends`
2. 定时任务每日同步 akshare 数据
3. Service 层改为查询数据库
4. 保持 API 接口不变

### 12.2 数据源切换

**支持 tushare**:
```python
class TushareDividendSource(DividendDataSource):
    def __init__(self, token: str):
        self.pro = ts.pro_api(token)
    
    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        return self.pro.dividend(ts_code=symbol)
```

**配置切换**:
```bash
# .env
DIVIDEND_DATA_SOURCE=tushare
TUSHARE_TOKEN=your_token
```

### 12.3 高级分析功能

**分红增长率分析**:
- 计算近5年分红复合增长率
- 识别分红增长趋势

**股息率历史分位数**:
- 计算当前股息率在历史中的分位数
- 判断是否处于高股息区间

**分红稳定性评分**:
- 连续分红年数
- 分红波动率
- 分红率稳定性

---

## 13. 总结

### 13.1 核心价值

1. **快速交付** — 2-3天完成开发，立即为 Agent 提供分红查询能力
2. **架构清晰** — 遵循现有六层架构，易于维护和扩展
3. **功能完整** — 支持单股查询、批量筛选、分红日历三种场景
4. **易于扩展** — 预留数据源抽象层和持久化升级路径

### 13.2 技术亮点

- **轻量级实现** — 无需数据库，降低维护成本
- **并发优化** — 批量查询使用线程池，提升性能
- **错误处理完善** — 多层错误捕获，友好提示
- **类型安全** — TypeScript 类型定义完整

### 13.3 后续优化方向

1. **性能优化** — 添加 Redis 缓存，减少 akshare 调用
2. **数据持久化** — 如查询量大，升级到数据库存储
3. **高级分析** — 添加分红增长率、股息率分位数等分析功能
4. **数据源扩展** — 支持 tushare 等其他数据源

---

**设计完成日期**: 2026-05-28  
**预计开发周期**: 2-3天  
**预计上线日期**: 2026-05-31
