# 多数据源实时行情系统设计文档

**日期**: 2026-05-29  
**作者**: Claude (Kiro)  
**状态**: 设计阶段

## 1. 背景和问题

### 1.1 当前问题

用户在使用 `data_fetch_stock` 工具获取实时行情时遇到以下问题：

1. **数据源单一**：仅依赖新浪财经 API，失败率较高
2. **时间戳缺失**：数据库 fallback 返回的价格没有时间戳，无法判断数据新鲜度
3. **Fallback 不可控**：实时数据失败时自动 fallback 到数据库，用户无法控制
4. **数据来源不明确**：用户不知道获取的是实时数据还是历史数据

### 1.2 用户需求

1. **多数据源支持**：实时数据应支持多个数据源（akshare、新浪、东财、腾讯、网易）
2. **优先级 fallback**：akshare 优先，依次尝试其他数据源
3. **实时数据不走数据库**：所有实时源都失败时应报错，不自动 fallback 到数据库
4. **明确的参数控制**：通过 `source` 参数明确指定数据来源（realtime/db/auto）
5. **时间戳完整性**：
   - 实时数据返回 `timestamp`（ISO 8601 格式）
   - 数据库数据返回 `trade_date`（交易日期）

## 2. 设计目标

1. **可靠性**：多数据源 fallback 提高实时数据获取成功率
2. **可控性**：用户可明确控制数据来源和 fallback 行为
3. **可扩展性**：易于添加新的数据源
4. **可维护性**：逻辑集中在后端，易于测试和调试
5. **向后兼容**：尽量保持现有 API 兼容（有 Breaking Changes）

## 3. 整体架构

### 3.1 数据流

```
Agent 调用 data_fetch_stock(symbol, fields, source)
    ↓
TypeScript 工具层（fetch-stock-tool.ts）
    ↓
HTTP 请求 → quantsys-v2 API /api/stock/{symbol}/quote?source=realtime
    ↓
RealtimeQuoteService（新增）
    ↓
依次尝试数据源：
  1. AkshareQuoteProvider (优先)
  2. SinaQuoteProvider (当前已有)
  3. EastmoneyQuoteProvider (新增)
  4. TencentQuoteProvider (新增)
  5. NeteaseQuoteProvider (新增)
    ↓
成功 → 返回实时数据 {price, source: 'akshare', timestamp: '2026-05-29T14:30:00'}
失败 → 根据 source 参数决定：
  - realtime: 报错
  - auto: fallback 到数据库 {price, source: 'db_fallback', trade_date: '2026-05-28'}
  - db: 直接查数据库
```

### 3.2 核心组件

| 组件 | 职责 | 位置 |
|------|------|------|
| QuoteProvider 接口 | 数据源抽象 | `quantsys-v2/services/quote_providers/base.py` |
| AkshareQuoteProvider | akshare 数据源实现 | `quantsys-v2/services/quote_providers/akshare_provider.py` |
| SinaQuoteProvider | 新浪财经数据源实现 | `quantsys-v2/services/quote_providers/sina_provider.py` |
| EastmoneyQuoteProvider | 东方财富数据源实现 | `quantsys-v2/services/quote_providers/eastmoney_provider.py` |
| TencentQuoteProvider | 腾讯财经数据源实现 | `quantsys-v2/services/quote_providers/tencent_provider.py` |
| NeteaseQuoteProvider | 网易财经数据源实现 | `quantsys-v2/services/quote_providers/netease_provider.py` |
| RealtimeQuoteService | 多数据源协调服务 | `quantsys-v2/services/realtime_quote_service.py` |
| /api/stock/{symbol}/quote | HTTP API 端点 | `quantsys-v2/api/routes/quote_market.py` |
| data_fetch_stock | TypeScript 工具 | `src/infrastructure/tools/data/fetch-stock-tool.ts` |
| getStockData() | TypeScript 客户端 | `src/infrastructure/quant/quant-v2-client.ts` |
| formatStockPrice() | 数据格式化 | `src/infrastructure/quant/formatters.ts` |

## 4. 详细设计

### 4.1 后端实现

#### 4.1.1 QuoteProvider 接口

```python
# quantsys-v2/services/quote_providers/base.py

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class QuoteData:
    """实时行情数据模型"""
    symbol: str
    name: str
    price: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    prev_close: Optional[float] = None
    volume: Optional[int] = None
    amount: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    source: str = ''  # 'akshare', 'sina', 'eastmoney', 'tencent', 'netease'
    timestamp: str = ''  # ISO 8601 格式：'2026-05-29T14:30:00'

class QuoteProvider(ABC):
    """实时行情数据源接口"""
    
    def __init__(self):
        self.timeout = 5  # 默认超时 5 秒
        self.retry_count = 1  # 默认重试 1 次
    
    @abstractmethod
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        获取实时行情
        
        Args:
            symbol: 股票代码（支持 6位数字 或 带后缀格式）
        
        Returns:
            QuoteData 或 None（失败时）
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        pass
    
    def _normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码（去除特殊字符）"""
        import re
        return re.sub(r'[^A-Za-z0-9.]', '', symbol)
```

#### 4.1.2 RealtimeQuoteService

```python
# quantsys-v2/services/realtime_quote_service.py

import logging
import time
from typing import Optional, List
from services.quote_providers.base import QuoteData, QuoteProvider
from services.quote_providers.akshare_provider import AkshareQuoteProvider
from services.quote_providers.sina_provider import SinaQuoteProvider
from services.quote_providers.eastmoney_provider import EastmoneyQuoteProvider
from services.quote_providers.tencent_provider import TencentQuoteProvider
from services.quote_providers.netease_provider import NeteaseQuoteProvider

class RealtimeQuoteService:
    """实时行情服务 - 多数据源 fallback"""
    
    def __init__(self, providers: Optional[List[QuoteProvider]] = None):
        if providers is None:
            # 默认数据源优先级：akshare > sina > eastmoney > tencent > netease
            self.providers = [
                AkshareQuoteProvider(),
                SinaQuoteProvider(),
                EastmoneyQuoteProvider(),
                TencentQuoteProvider(),
                NeteaseQuoteProvider(),
            ]
        else:
            self.providers = providers
        
        self.logger = logging.getLogger(__name__)
        
        # 统计指标
        self.stats = {
            'total_requests': 0,
            'success_count': 0,
            'failure_count': 0,
            'provider_stats': {}
        }
    
    def get_realtime_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        依次尝试所有数据源，返回第一个成功的结果
        
        Args:
            symbol: 股票代码
        
        Returns:
            QuoteData 或 None（所有数据源都失败）
        """
        self.stats['total_requests'] += 1
        errors = []
        
        for provider in self.providers:
            provider_name = provider.name
            
            # 初始化 provider 统计
            if provider_name not in self.stats['provider_stats']:
                self.stats['provider_stats'][provider_name] = {
                    'attempts': 0,
                    'success': 0,
                    'failure': 0,
                    'total_time': 0.0
                }
            
            try:
                self.logger.info(f"[{symbol}] 尝试数据源: {provider_name}")
                start_time = time.time()
                
                self.stats['provider_stats'][provider_name]['attempts'] += 1
                
                quote = provider.get_quote(symbol)
                
                elapsed = time.time() - start_time
                self.stats['provider_stats'][provider_name]['total_time'] += elapsed
                
                if quote and quote.price:
                    self.stats['success_count'] += 1
                    self.stats['provider_stats'][provider_name]['success'] += 1
                    
                    self.logger.info(
                        f"[{symbol}] 成功获取实时行情: {provider_name}, "
                        f"耗时: {elapsed:.2f}s, 价格: {quote.price}"
                    )
                    return quote
                else:
                    self.stats['provider_stats'][provider_name]['failure'] += 1
                    self.logger.warning(f"[{symbol}] {provider_name} 返回空数据")
                    
            except Exception as e:
                self.stats['provider_stats'][provider_name]['failure'] += 1
                error_msg = f"{provider_name}: {str(e)}"
                self.logger.warning(f"[{symbol}] {error_msg}")
                errors.append(error_msg)
        
        # 所有数据源都失败
        self.stats['failure_count'] += 1
        self.logger.error(
            f"[{symbol}] 所有实时数据源失败 - " + 
            " | ".join(errors)
        )
        return None
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return self.stats
```

#### 4.1.3 AkshareQuoteProvider（优先级最高）

```python
# quantsys-v2/services/quote_providers/akshare_provider.py

import akshare as ak
import pandas as pd
from datetime import datetime
from typing import Optional
from services.quote_providers.base import QuoteProvider, QuoteData

class AkshareQuoteProvider(QuoteProvider):
    """akshare 实时行情数据源"""
    
    @property
    def name(self) -> str:
        return "akshare"
    
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        使用 akshare 的实时行情接口
        - A股: ak.stock_zh_a_spot_em()
        - 港股: ak.stock_hk_spot_em()
        """
        clean_symbol = self._normalize_symbol(symbol)
        is_hk = len(clean_symbol) <= 5 or '.HK' in symbol.upper()
        
        try:
            if is_hk:
                # 港股实时行情
                df = ak.stock_hk_spot_em()
                row = df[df['代码'] == clean_symbol]
                if row.empty:
                    return None
                
                return QuoteData(
                    symbol=clean_symbol,
                    name=str(row['名称'].iloc[0]),
                    price=float(row['最新价'].iloc[0]),
                    open=float(row['今开'].iloc[0]),
                    high=float(row['最高'].iloc[0]),
                    low=float(row['最低'].iloc[0]),
                    prev_close=float(row['昨收'].iloc[0]),
                    volume=int(row['成交量'].iloc[0]),
                    change_pct=float(row['涨跌幅'].iloc[0]),
                    source='akshare',
                    timestamp=datetime.now().isoformat()
                )
            else:
                # A股实时行情
                df = ak.stock_zh_a_spot_em()
                row = df[df['代码'] == clean_symbol]
                if row.empty:
                    return None
                
                return QuoteData(
                    symbol=clean_symbol,
                    name=str(row['名称'].iloc[0]),
                    price=float(row['最新价'].iloc[0]),
                    open=float(row['今开'].iloc[0]),
                    high=float(row['最高'].iloc[0]),
                    low=float(row['最低'].iloc[0]),
                    prev_close=float(row['昨收'].iloc[0]),
                    volume=int(row['成交量'].iloc[0]),
                    amount=float(row['成交额'].iloc[0]),
                    change_pct=float(row['涨跌幅'].iloc[0]),
                    source='akshare',
                    timestamp=datetime.now().isoformat()
                )
        except Exception as e:
            raise Exception(f"akshare 查询失败: {e}")
```

#### 4.1.4 SinaQuoteProvider（复用现有逻辑）

```python
# quantsys-v2/services/quote_providers/sina_provider.py

import requests
from datetime import datetime
from typing import Optional
from services.quote_providers.base import QuoteProvider, QuoteData

class SinaQuoteProvider(QuoteProvider):
    """新浪财经实时行情（复用现有逻辑）"""
    
    @property
    def name(self) -> str:
        return "sina"
    
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        复用 api/shared.py 中的新浪解析逻辑
        """
        clean_symbol = self._normalize_symbol(symbol)
        is_hk = len(clean_symbol) <= 5
        
        try:
            if is_hk:
                sina_code = f"hk{clean_symbol}"
            else:
                prefix = "1" if clean_symbol.startswith("60") else "0"
                sina_code = f"{prefix}{clean_symbol}"
            
            resp = requests.get(
                f"https://hq.sinajs.cn/list={sina_code}",
                headers={
                    "Referer": "https://finance.sina.com.cn",
                    "User-Agent": "Mozilla/5.0"
                },
                timeout=self.timeout,
            )
            resp.encoding = "gbk"
            raw = resp.text
            
            if is_hk:
                return self._parse_sina_hk_quote(raw, clean_symbol)
            else:
                return self._parse_sina_a_quote(raw, clean_symbol)
                
        except Exception as e:
            raise Exception(f"新浪财经查询失败: {e}")
    
    def _parse_sina_a_quote(self, raw: str, symbol: str) -> Optional[QuoteData]:
        """解析新浪 A股行情"""
        parts = raw.split('"')
        if len(parts) < 2:
            return None
        fields = parts[1].split(',')
        if len(fields) < 32:
            return None
        
        name = fields[0]
        open_p = float(fields[1]) if fields[1] else 0
        prev_close = float(fields[2]) if fields[2] else 0
        price = float(fields[3]) if fields[3] else 0
        high = float(fields[4]) if fields[4] else 0
        low = float(fields[5]) if fields[5] else 0
        volume = int(float(fields[8])) if fields[8] else 0
        amount = float(fields[9]) if fields[9] else 0
        
        change = round(price - prev_close, 2) if price and prev_close else 0
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0
        
        return QuoteData(
            symbol=symbol,
            name=name,
            price=price,
            open=open_p,
            high=high,
            low=low,
            volume=volume,
            amount=amount,
            prev_close=prev_close,
            change=change,
            change_pct=change_pct,
            source='sina',
            timestamp=datetime.now().isoformat()
        )
    
    def _parse_sina_hk_quote(self, raw: str, symbol: str) -> Optional[QuoteData]:
        """解析新浪港股行情"""
        parts = raw.split('"')
        if len(parts) < 2:
            return None
        fields = parts[1].split(',')
        if len(fields) < 20:
            return None
        
        name = fields[1]
        open_p = float(fields[2]) if fields[2] else 0
        prev_close = float(fields[3]) if fields[3] else 0
        price = float(fields[6]) if fields[6] else 0
        high = float(fields[4]) if fields[4] else 0
        low = float(fields[5]) if fields[5] else 0
        
        change = round(price - prev_close, 2) if price and prev_close else 0
        change_pct = round(change / prev_close * 100, 2) if prev_close else 0
        
        return QuoteData(
            symbol=symbol,
            name=name,
            price=price,
            open=open_p,
            high=high,
            low=low,
            prev_close=prev_close,
            change=change,
            change_pct=change_pct,
            source='sina',
            timestamp=datetime.now().isoformat()
        )
```

#### 4.1.5 其他 Provider（东财、腾讯、网易）

```python
# quantsys-v2/services/quote_providers/eastmoney_provider.py
# quantsys-v2/services/quote_providers/tencent_provider.py
# quantsys-v2/services/quote_providers/netease_provider.py

# 类似结构，每个 Provider 实现自己的 API 调用逻辑
# 具体实现在编写实现计划时详细说明
```

#### 4.1.6 API 路由修改

```python
# quantsys-v2/api/routes/quote_market.py

@quote_market_bp.route('/api/stock/<symbol>/quote', methods=['GET'])
@handle_api_error
def get_stock_quote(symbol):
    """
    实时行情端点 - 支持多数据源
    
    参数:
        source: 'realtime' | 'db' | 'auto' (默认 'realtime')
            - realtime: 依次尝试 akshare → 新浪 → 东财 → 腾讯 → 网易，全部失败报错
            - db: 直接查询数据库最新 K线
            - auto: 先尝试实时数据源，失败后 fallback 到数据库
    
    返回:
        {
            "success": true,
            "symbol": "600900",
            "name": "长江电力",
            "price": 27.45,
            "change_pct": 0.77,
            "source": "akshare",  // 或 'sina', 'eastmoney', 'db_fallback'
            "timestamp": "2026-05-29T14:30:00",  // 实时数据的时间戳
            "trade_date": "2026-05-28"  // 仅 db_fallback 时返回
        }
    """
    source = request.args.get('source', 'realtime')
    
    if source not in ['realtime', 'db', 'auto']:
        return jsonify({
            "success": False, 
            "error": f"无效的 source 参数: {source}，支持 realtime/db/auto"
        }), 400
    
    clean_symbol = re.sub(r'[^A-Za-z0-9.]', '', symbol)
    
    # 直接查数据库
    if source == 'db':
        return _get_db_quote(clean_symbol)
    
    # 尝试实时数据源
    realtime_service = RealtimeQuoteService()
    quote = realtime_service.get_realtime_quote(clean_symbol)
    
    if quote:
        return api_response({
            "symbol": quote.symbol,
            "name": quote.name,
            "price": quote.price,
            "open": quote.open,
            "high": quote.high,
            "low": quote.low,
            "prev_close": quote.prev_close,
            "volume": quote.volume,
            "amount": quote.amount,
            "change": quote.change,
            "change_pct": quote.change_pct,
            "source": quote.source,
            "timestamp": quote.timestamp,
        })
    
    # 实时数据失败
    if source == 'realtime':
        # 强制实时，报错
        return jsonify({
            "success": False,
            "error": f"无法获取 {symbol} 的实时行情，所有数据源均失败"
        }), 502
    
    # source == 'auto'，fallback 到数据库
    return _get_db_quote(clean_symbol)


def _get_db_quote(symbol: str):
    """从数据库获取最新 K线收盘价"""
    try:
        latest = ds.kline.get_latest_daily_kline(symbol)
        if not latest or not latest.get("close"):
            return jsonify({
                "success": False, 
                "error": f"数据库中无 {symbol} 的 K线数据"
            }), 404
        
        stock = ds.stock.get_by_symbol(symbol) or {}
        
        return api_response({
            "symbol": symbol,
            "name": stock.get("name", symbol),
            "price": float(latest["close"]),
            "change_pct": float(latest.get("change_pct", 0) or 0),
            "high": float(latest.get("high", 0) or 0),
            "low": float(latest.get("low", 0) or 0),
            "open": float(latest.get("open", 0) or 0),
            "volume": float(latest.get("volume", 0) or 0),
            "source": "db_fallback",
            "trade_date": latest.get("trade_date"),  # 新增：返回交易日期
        })
    except Exception as e:
        return jsonify({
            "success": False, 
            "error": f"数据库查询失败: {str(e)}"
        }), 500
```

### 4.2 TypeScript 工具层修改

#### 4.2.1 修改 fetch-stock-tool.ts

```typescript
// src/infrastructure/tools/data/fetch-stock-tool.ts

interface FetchStockParams {
  symbol: string;
  fields?: DataField[];
  news_num?: number;
  source?: 'realtime' | 'db' | 'auto';  // 新增参数
}

export const dataFetchStockTool: ToolDefinition = {
  name: "data_fetch_stock",
  label: "获取股票数据（支持多数据源实时行情）",
  description:
    "获取股票基础数据（info/price/news/announcements）。支持 A 股和港股。" +
    "price 字段支持多数据源实时行情（akshare → 新浪 → 东财 → 腾讯 → 网易），延迟 < 3秒。" +
    "source 参数控制数据来源：realtime（默认，强制实时）、db（数据库）、auto（实时失败后 fallback）。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码：A股6位数字（如 600519）或港股1-5位数字（如 9988 或 9988.HK）"
    }),
    fields: Type.Optional(
      Type.Array(
        Type.Union([
          Type.Literal("info"),
          Type.Literal("price"),
          Type.Literal("news"),
          Type.Literal("announcements")
        ]),
        {
          description: "要获取的数据字段。默认: ['info', 'price']"
        }
      )
    ),
    news_num: Type.Optional(
      Type.Integer({
        description: `新闻条数（仅当 fields 包含 'news' 时有效）。默认: ${DEFAULT_NEWS_COUNT}`,
        minimum: 1,
        maximum: 50
      })
    ),
    source: Type.Optional(
      Type.Union([
        Type.Literal("realtime"),
        Type.Literal("db"),
        Type.Literal("auto")
      ], {
        description: 
          "数据来源控制（仅影响 price 字段）：\n" +
          "- realtime（默认）: 强制实时数据，依次尝试 akshare/新浪/东财/腾讯/网易，全部失败报错\n" +
          "- db: 直接查询数据库最新 K线收盘价\n" +
          "- auto: 先尝试实时数据源，失败后 fallback 到数据库"
      })
    )
  }),

  execute: async (_toolCallId, params: FetchStockParams) => {
    const { 
      symbol, 
      fields = ["info", "price"], 
      news_num = DEFAULT_NEWS_COUNT,
      source = "realtime"  // 默认强制实时
    } = params;

    // 验证股票代码
    const market = detectMarket(symbol);
    if (market === "invalid") {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            error: `不支持的股票代码 "${symbol}"。本系统支持A股（6位数字）和港股（1-5位数字或含.HK后缀）。`,
            invalid_format: true
          })
        }],
        details: undefined
      };
    }

    // 调用 v2 API（传递 source 参数）
    try {
      const result = await getStockData(symbol, fields, news_num, source);
      
      // 格式化输出逻辑保持不变
      if (fields.includes('price') && result.price) {
        const formattedPrice = formatStockPrice(result.price);
        // ... 其他格式化逻辑
      }
      
      // ... 错误处理
    } catch (error) {
      // ... 错误处理
    }
  }
};
```

#### 4.2.2 修改 quant-v2-client.ts

```typescript
// src/infrastructure/quant/quant-v2-client.ts

export async function getStockData(
  symbol: string,
  fields: Array<'info' | 'price' | 'news' | 'announcements'> = ['info', 'price'],
  newsNum: number = 10,
  source: 'realtime' | 'db' | 'auto' = 'realtime',  // 新增参数
): Promise<StockData> {
  if (!symbol || symbol.trim() === '') {
    throw new QuantV2Error('股票代码不能为空', 400);
  }

  const result: StockData = { success: true };
  const fetchPromises: Promise<void>[] = [];

  // Fetch info
  if (fields.includes('info')) {
    fetchPromises.push(
      (async () => {
        try {
          const url = `${V2_API_BASE}/api/stocks/${encodeURIComponent(symbol)}`;
          const data = await fetchV2<StockInfo>(url);
          result.info = data;
        } catch (error) {
          result.info = null;
          result.info_error = error instanceof Error ? error.message : String(error);
        }
      })()
    );
  }

  // Fetch price（传递 source 参数）
  if (fields.includes('price')) {
    fetchPromises.push(
      (async () => {
        try {
          const url = `${V2_API_BASE}/api/stock/${encodeURIComponent(symbol)}/quote?source=${source}`;
          const data = await fetchV2<StockPrice>(url);
          result.price = data;
        } catch (error) {
          result.price = null;
          result.price_error = error instanceof Error ? error.message : String(error);
        }
      })()
    );
  }

  // Fetch news
  if (fields.includes('news')) {
    // ... 保持不变
  }

  // Fetch announcements
  if (fields.includes('announcements')) {
    // ... 保持不变
  }

  await Promise.all(fetchPromises);

  // Check if all fields failed
  const hasAnySuccess = fields.some(field => {
    if (field === 'info') return result.info !== null;
    if (field === 'price') return result.price !== null;
    if (field === 'news') return result.news !== null;
    if (field === 'announcements') return result.announcements !== null;
    return false;
  });

  if (!hasAnySuccess) {
    result.success = false;
    const firstError = result.info_error || result.price_error || result.news_error || result.announcements_error;
    result.error = firstError || '所有数据获取失败';
  }

  return result;
}
```

#### 4.2.3 修改 types.ts

```typescript
// src/infrastructure/quant/types.ts

export interface StockPrice {
  symbol: string;
  name: string;
  price: number;
  open?: number;
  high?: number;
  low?: number;
  prev_close?: number;
  volume?: number;
  amount?: number;
  change?: number;
  change_pct?: number;
  source: 'akshare' | 'sina' | 'eastmoney' | 'tencent' | 'netease' | 'db_fallback';
  timestamp?: string;      // 实时数据的时间戳（ISO 8601 格式）
  trade_date?: string;     // 数据库数据的交易日期（YYYY-MM-DD 格式）
}
```

#### 4.2.4 修改 formatters.ts

```typescript
// src/infrastructure/quant/formatters.ts

export function formatStockPrice(data: any): string {
  if (!data) return '价格数据不可用';

  const lines: string[] = [];
  const isRealtime = ['akshare', 'sina', 'eastmoney', 'tencent', 'netease'].includes(data.source);
  const isFallback = data.source === 'db_fallback';

  // Header with data source indicator
  if (isRealtime) {
    const sourceNames = {
      'akshare': 'akshare',
      'sina': '新浪财经',
      'eastmoney': '东方财富',
      'tencent': '腾讯财经',
      'netease': '网易财经'
    };
    const sourceName = sourceNames[data.source] || data.source;
    lines.push(`【实时行情】（数据源: ${sourceName}，延迟 < 3秒）`);
  } else if (isFallback) {
    lines.push('【最新收盘价】（数据库，非实时）');
  } else {
    lines.push('【行情数据】');
  }

  lines.push(`股票代码: ${data.symbol}`);
  lines.push(`股票名称: ${data.name}`);
  lines.push(`当前价格: ${formatNumber(data.price, 2)} 元`);

  if (data.change_pct !== undefined && data.change_pct !== null) {
    lines.push(`涨跌幅: ${formatPercent(data.change_pct)}`);
  }

  if (data.change !== undefined && data.change !== null) {
    const sign = data.change > 0 ? '+' : '';
    lines.push(`涨跌额: ${sign}${formatNumber(data.change, 2)} 元`);
  }

  if (data.open !== undefined && data.open !== null) {
    lines.push(`今开: ${formatNumber(data.open, 2)} 元`);
  }

  if (data.high !== undefined && data.high !== null) {
    lines.push(`最高: ${formatNumber(data.high, 2)} 元`);
  }

  if (data.low !== undefined && data.low !== null) {
    lines.push(`最低: ${formatNumber(data.low, 2)} 元`);
  }

  if (data.prev_close !== undefined && data.prev_close !== null) {
    lines.push(`昨收: ${formatNumber(data.prev_close, 2)} 元`);
  }

  if (data.volume !== undefined && data.volume !== null) {
    const volumeInWan = data.volume / 10000;
    lines.push(`成交量: ${formatNumber(volumeInWan, 0)} 万股`);
  }

  if (data.amount !== undefined && data.amount !== null) {
    const amountInYi = data.amount / 100000000;
    lines.push(`成交额: ${formatNumber(amountInYi, 2)} 亿元`);
  }

  // Data freshness note
  if (isRealtime && data.timestamp) {
    // 显示实时数据的时间戳
    lines.push(`\n💡 数据时间: ${data.timestamp}`);
    
    const now = new Date();
    const hour = now.getHours();
    const minute = now.getMinutes();
    const isTrading =
      (hour === 9 && minute >= 30) ||
      (hour >= 10 && hour < 11) ||
      (hour === 11 && minute < 30) ||
      (hour >= 13 && hour < 15);

    if (isTrading) {
      lines.push('💡 当前处于交易时段，数据为实时行情');
    } else {
      lines.push('💡 当前非交易时段，显示最新成交价');
    }
  } else if (isFallback && data.trade_date) {
    // 显示数据库数据的交易日期
    lines.push(`\n⚠️ 实时行情获取失败，显示数据库收盘价`);
    lines.push(`📅 数据日期: ${data.trade_date}`);
  }

  return lines.join('\n');
}
```

## 5. 测试策略

### 5.1 单元测试

#### 5.1.1 RealtimeQuoteService 测试

```python
# quantsys-v2/tests/services/test_realtime_quote_service.py

import pytest
from unittest.mock import Mock, patch
from services.realtime_quote_service import RealtimeQuoteService
from services.quote_providers.base import QuoteData

class TestRealtimeQuoteService:
    
    def test_first_provider_success(self):
        """测试第一个数据源成功返回"""
        service = RealtimeQuoteService()
        
        with patch.object(service.providers[0], 'get_quote') as mock_akshare:
            mock_akshare.return_value = QuoteData(
                symbol='600900',
                name='长江电力',
                price=27.45,
                source='akshare',
                timestamp='2026-05-29T14:30:00'
            )
            
            result = service.get_realtime_quote('600900')
            
            assert result is not None
            assert result.source == 'akshare'
            assert result.price == 27.45
            assert mock_akshare.call_count == 1
    
    def test_fallback_to_second_provider(self):
        """测试第一个数据源失败，fallback 到第二个"""
        service = RealtimeQuoteService()
        
        with patch.object(service.providers[0], 'get_quote') as mock_akshare, \
             patch.object(service.providers[1], 'get_quote') as mock_sina:
            
            mock_akshare.side_effect = Exception("akshare API error")
            mock_sina.return_value = QuoteData(
                symbol='600900',
                name='长江电力',
                price=27.45,
                source='sina',
                timestamp='2026-05-29T14:30:00'
            )
            
            result = service.get_realtime_quote('600900')
            
            assert result is not None
            assert result.source == 'sina'
            assert mock_akshare.call_count == 1
            assert mock_sina.call_count == 1
    
    def test_all_providers_fail(self):
        """测试所有数据源都失败"""
        service = RealtimeQuoteService()
        
        for i, provider in enumerate(service.providers):
            with patch.object(provider, 'get_quote') as mock:
                mock.side_effect = Exception("API error")
        
        result = service.get_realtime_quote('600900')
        assert result is None
```

#### 5.1.2 Provider 测试

```python
# quantsys-v2/tests/services/quote_providers/test_akshare_provider.py

import pytest
import pandas as pd
from unittest.mock import patch
from services.quote_providers.akshare_provider import AkshareQuoteProvider

class TestAkshareProvider:
    
    def test_get_a_stock_quote(self):
        """测试获取 A股实时行情"""
        provider = AkshareQuoteProvider()
        
        with patch('akshare.stock_zh_a_spot_em') as mock_ak:
            mock_ak.return_value = pd.DataFrame({
                '代码': ['600900'],
                '名称': ['长江电力'],
                '最新价': [27.45],
                '今开': [27.20],
                '最高': [27.50],
                '最低': [27.15],
                '昨收': [27.24],
                '成交量': [1000000],
                '成交额': [27450000],
                '涨跌幅': [0.77]
            })
            
            result = provider.get_quote('600900')
            
            assert result is not None
            assert result.symbol == '600900'
            assert result.price == 27.45
            assert result.source == 'akshare'
    
    def test_stock_not_found(self):
        """测试股票不存在"""
        provider = AkshareQuoteProvider()
        
        with patch('akshare.stock_zh_a_spot_em') as mock_ak:
            mock_ak.return_value = pd.DataFrame()
            
            result = provider.get_quote('999999')
            assert result is None
```

### 5.2 API 集成测试

```python
# quantsys-v2/tests/api/test_quote_routes.py

class TestQuoteRoutes:
    
    def test_realtime_source_success(self, client):
        """测试 source=realtime 成功获取实时数据"""
        response = client.get('/api/stock/600900/quote?source=realtime')
        
        assert response.status_code == 200
        data = response.json
        assert data['success'] is True
        assert data['source'] in ['akshare', 'sina', 'eastmoney', 'tencent', 'netease']
        assert 'timestamp' in data
        assert 'price' in data
    
    def test_realtime_source_all_fail(self, client):
        """测试 source=realtime 所有数据源失败"""
        with patch('services.realtime_quote_service.RealtimeQuoteService.get_realtime_quote') as mock:
            mock.return_value = None
            
            response = client.get('/api/stock/600900/quote?source=realtime')
            
            assert response.status_code == 502
            data = response.json
            assert data['success'] is False
            assert '所有数据源均失败' in data['error']
    
    def test_db_source(self, client):
        """测试 source=db 直接查询数据库"""
        response = client.get('/api/stock/600900/quote?source=db')
        
        assert response.status_code == 200
        data = response.json
        assert data['success'] is True
        assert data['source'] == 'db_fallback'
        assert 'trade_date' in data
        assert 'timestamp' not in data
    
    def test_auto_source_fallback(self, client):
        """测试 source=auto 实时失败后 fallback"""
        with patch('services.realtime_quote_service.RealtimeQuoteService.get_realtime_quote') as mock:
            mock.return_value = None
            
            response = client.get('/api/stock/600900/quote?source=auto')
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert data['source'] == 'db_fallback'
            assert 'trade_date' in data
    
    def test_invalid_source(self, client):
        """测试无效的 source 参数"""
        response = client.get('/api/stock/600900/quote?source=invalid')
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert '无效的 source 参数' in data['error']
```

### 5.3 TypeScript 工具测试

```typescript
// src/infrastructure/tools/data/fetch-stock-tool.test.ts

describe('data_fetch_stock tool', () => {
  
  it('should fetch realtime price with source=realtime', async () => {
    const result = await dataFetchStockTool.execute('test-id', {
      symbol: '600900',
      fields: ['price'],
      source: 'realtime'
    });
    
    expect(result.content[0].text).toContain('【实时行情】');
    expect(result.content[0].text).toContain('数据源:');
  });
  
  it('should fetch db price with source=db', async () => {
    const result = await dataFetchStockTool.execute('test-id', {
      symbol: '600900',
      fields: ['price'],
      source: 'db'
    });
    
    expect(result.content[0].text).toContain('【最新收盘价】');
    expect(result.content[0].text).toContain('数据日期:');
  });
  
  it('should default to realtime source', async () => {
    const result = await dataFetchStockTool.execute('test-id', {
      symbol: '600900',
      fields: ['price']
    });
    
    expect(result.content[0].text).toContain('【实时行情】');
  });
});
```

## 6. 错误处理

### 6.1 错误处理策略

1. **数据源级别错误**：单个 Provider 失败不影响其他 Provider，记录 warning 日志
2. **服务级别错误**：所有 Provider 都失败时，根据 `source` 参数决定：
   - `realtime`: 返回 502 错误，包含所有数据源的失败原因
   - `auto`: fallback 到数据库
   - `db`: 数据库查询失败返回 500 错误

### 6.2 日志记录

```python
# 日志级别
- INFO: 数据源尝试、成功获取、耗时统计
- WARNING: 单个数据源失败、返回空数据
- ERROR: 所有数据源失败

# 日志格式
[{symbol}] {action}: {provider_name}, 耗时: {elapsed}s, 价格: {price}
[{symbol}] 所有实时数据源失败 - akshare: timeout | sina: empty data | ...
```

## 7. 配置和扩展性

### 7.1 数据源配置

```python
# quantsys-v2/config/quote_sources.py

from dataclasses import dataclass
from typing import List

@dataclass
class QuoteSourceConfig:
    """数据源配置"""
    name: str
    enabled: bool
    timeout: int  # 秒
    priority: int  # 优先级（数字越小优先级越高）
    retry_count: int  # 重试次数

# 默认配置
DEFAULT_QUOTE_SOURCES = [
    QuoteSourceConfig(name='akshare', enabled=True, timeout=5, priority=1, retry_count=1),
    QuoteSourceConfig(name='sina', enabled=True, timeout=5, priority=2, retry_count=1),
    QuoteSourceConfig(name='eastmoney', enabled=True, timeout=5, priority=3, retry_count=1),
    QuoteSourceConfig(name='tencent', enabled=True, timeout=5, priority=4, retry_count=1),
    QuoteSourceConfig(name='netease', enabled=True, timeout=5, priority=5, retry_count=1),
]
```

### 7.2 监控端点

```python
# GET /api/quote/stats

{
  "total_requests": 100,
  "success_count": 95,
  "failure_count": 5,
  "success_rate": 0.95,
  "provider_stats": {
    "akshare": {
      "attempts": 100,
      "success": 90,
      "failure": 10,
      "success_rate": 0.90,
      "avg_time": 0.5
    },
    "sina": {
      "attempts": 10,
      "success": 5,
      "failure": 5,
      "success_rate": 0.50,
      "avg_time": 1.2
    }
  }
}
```

## 8. 迁移和向后兼容

### 8.1 迁移计划

#### 阶段 1：后端实现（不影响现有功能）
- 实现 QuoteProvider 接口和 5 个 Provider
- 实现 RealtimeQuoteService
- 修改 `/api/stock/{symbol}/quote` 支持 `source` 参数
- `source` 参数可选，默认值为 `realtime`
- 保持现有 API 响应格式兼容

#### 阶段 2：TypeScript 工具层更新
- 修改 `data_fetch_stock` 工具添加 `source` 参数
- `source` 参数可选，默认值为 `realtime`
- 修改 `getStockData()` 函数传递 `source` 参数
- 更新 `formatStockPrice()` 支持新的时间戳字段

#### 阶段 3：测试和验证
- 单元测试覆盖所有 Provider
- API 集成测试覆盖所有 source 参数组合
- 端到端测试验证工具调用
- 性能测试验证多数据源 fallback 耗时

#### 阶段 4：文档和发布
- 更新 CLAUDE.md 文档
- 更新 API 文档
- 发布 changelog

### 8.2 Breaking Changes

#### 默认行为变更

**旧版本**：
- 实时数据（新浪）失败 → 自动 fallback 到数据库
- 用户无法控制是否 fallback

**新版本**：
- 默认 `source=realtime`：实时数据失败 → 报错（不 fallback）
- 需要 fallback 行为：显式传 `source=auto`

#### 迁移建议

如果代码依赖旧版本的自动 fallback 行为，请：

**方案 A**：显式传 `source=auto`
```typescript
data_fetch_stock({
  symbol: "600900",
  fields: ["price"],
  source: "auto"  // 保持旧版本行为
})
```

**方案 B**：修改默认值配置
```python
# quantsys-v2/config/quote_sources.py
DEFAULT_SOURCE = 'auto'  # 改为 auto
```

#### 为什么这样设计？

根据用户反馈：
- "实时数据失败时不应该返回数据库数据"
- "应该明确知道获取的是实时数据还是历史数据"
- "需要参数控制是否允许 fallback"

新设计让用户明确控制数据来源，避免混淆。

### 8.3 回滚计划

如果新版本出现严重问题，可以快速回滚：

#### 后端回滚
```bash
# 1. 恢复旧版本的 quote_market.py
git checkout HEAD~1 quantsys-v2/api/routes/quote_market.py

# 2. 删除新增的 Provider 文件
rm -rf quantsys-v2/services/quote_providers/
rm quantsys-v2/services/realtime_quote_service.py

# 3. 重启服务
python api/server.py
```

#### TypeScript 回滚
```bash
# 1. 恢复旧版本的工具文件
git checkout HEAD~1 src/infrastructure/tools/data/fetch-stock-tool.ts
git checkout HEAD~1 src/infrastructure/quant/quant-v2-client.ts
git checkout HEAD~1 src/infrastructure/quant/formatters.ts

# 2. 重新构建
npm run build
```

#### 数据库回滚
无需数据库变更，无回滚操作。

## 9. API 文档

### 9.1 端点：GET /api/stock/{symbol}/quote

获取股票实时行情，支持多数据源自动 fallback。

#### 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| symbol | string | 是 | - | 股票代码（A股6位数字或港股1-5位数字） |
| source | string | 否 | realtime | 数据来源：realtime/db/auto |

#### source 参数说明

- **realtime**（默认）：强制实时数据
  - 依次尝试：akshare → 新浪 → 东方财富 → 腾讯 → 网易
  - 所有数据源失败返回 502 错误
  - 不会 fallback 到数据库

- **db**：直接查询数据库
  - 返回最新 K线收盘价
  - 包含 `trade_date` 字段（交易日期）
  - 适用于历史数据查询

- **auto**：自动 fallback
  - 先尝试实时数据源（同 realtime）
  - 所有实时源失败后 fallback 到数据库
  - 向后兼容旧版本行为

#### 响应格式

**实时数据成功：**
```json
{
  "success": true,
  "symbol": "600900",
  "name": "长江电力",
  "price": 27.45,
  "open": 27.20,
  "high": 27.50,
  "low": 27.15,
  "prev_close": 27.24,
  "volume": 1000000,
  "amount": 27450000,
  "change": 0.21,
  "change_pct": 0.77,
  "source": "akshare",
  "timestamp": "2026-05-29T14:30:00"
}
```

**数据库 fallback：**
```json
{
  "success": true,
  "symbol": "600900",
  "name": "长江电力",
  "price": 27.24,
  "change_pct": 0.0,
  "high": 27.50,
  "low": 27.00,
  "open": 27.10,
  "volume": 950000,
  "source": "db_fallback",
  "trade_date": "2026-05-28"
}
```

**错误响应：**
```json
{
  "success": false,
  "error": "无法获取 600900 的实时行情，所有数据源均失败"
}
```

#### 使用示例

```bash
# 获取实时行情（默认）
curl "http://127.0.0.1:5001/api/stock/600900/quote"

# 强制实时数据
curl "http://127.0.0.1:5001/api/stock/600900/quote?source=realtime"

# 查询数据库
curl "http://127.0.0.1:5001/api/stock/600900/quote?source=db"

# 自动 fallback
curl "http://127.0.0.1:5001/api/stock/600900/quote?source=auto"
```

### 9.2 TypeScript 工具使用示例

```typescript
// 示例 1：获取实时行情（默认行为）
data_fetch_stock({
  symbol: "600900",
  fields: ["price"]
})

// 示例 2：强制实时数据，失败就报错
data_fetch_stock({
  symbol: "600900",
  fields: ["price"],
  source: "realtime"
})

// 示例 3：直接查询数据库
data_fetch_stock({
  symbol: "600900",
  fields: ["price"],
  source: "db"
})

// 示例 4：自动 fallback（实时失败后用数据库）
data_fetch_stock({
  symbol: "600900",
  fields: ["price"],
  source: "auto"
})

// 示例 5：组合查询（info + 实时 price）
data_fetch_stock({
  symbol: "600900",
  fields: ["info", "price"],
  source: "realtime"
})
```

## 10. 文件清单

### 10.1 新增文件

| 文件路径 | 说明 |
|---------|------|
| `quantsys-v2/services/quote_providers/base.py` | QuoteProvider 接口和 QuoteData 模型 |
| `quantsys-v2/services/quote_providers/akshare_provider.py` | akshare 数据源实现 |
| `quantsys-v2/services/quote_providers/sina_provider.py` | 新浪财经数据源实现 |
| `quantsys-v2/services/quote_providers/eastmoney_provider.py` | 东方财富数据源实现 |
| `quantsys-v2/services/quote_providers/tencent_provider.py` | 腾讯财经数据源实现 |
| `quantsys-v2/services/quote_providers/netease_provider.py` | 网易财经数据源实现 |
| `quantsys-v2/services/realtime_quote_service.py` | 多数据源协调服务 |
| `quantsys-v2/config/quote_sources.py` | 数据源配置 |
| `quantsys-v2/tests/services/test_realtime_quote_service.py` | RealtimeQuoteService 单元测试 |
| `quantsys-v2/tests/services/quote_providers/test_akshare_provider.py` | AkshareProvider 单元测试 |
| `quantsys-v2/tests/services/quote_providers/test_sina_provider.py` | SinaProvider 单元测试 |

### 10.2 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `quantsys-v2/api/routes/quote_market.py` | 添加 `source` 参数支持，修改 `_get_db_quote()` 返回 `trade_date` |
| `src/infrastructure/tools/data/fetch-stock-tool.ts` | 添加 `source` 参数定义 |
| `src/infrastructure/quant/quant-v2-client.ts` | `getStockData()` 添加 `source` 参数 |
| `src/infrastructure/quant/types.ts` | `StockPrice` 接口添加 `timestamp` 和 `trade_date` 字段 |
| `src/infrastructure/quant/formatters.ts` | `formatStockPrice()` 支持多数据源和时间戳显示 |
| `quantsys-v2/tests/api/test_quote_routes.py` | 添加 `source` 参数测试用例 |
| `src/infrastructure/tools/data/fetch-stock-tool.test.ts` | 添加 `source` 参数测试用例 |

## 11. 性能考虑

### 11.1 预期性能

- **单数据源成功**：< 1秒（akshare 或新浪）
- **Fallback 到第二个数据源**：< 2秒
- **所有数据源失败**：< 10秒（5个数据源 × 2秒超时）
- **数据库查询**：< 100ms

### 11.2 优化策略

1. **超时控制**：每个数据源独立超时（默认 5秒）
2. **快速失败**：数据源返回空数据立即尝试下一个
3. **统计监控**：记录每个数据源的成功率和平均耗时
4. **动态调整**：未来可根据统计数据动态调整数据源优先级

## 12. 安全考虑

### 12.1 输入验证

- 股票代码格式验证（防止注入攻击）
- `source` 参数白名单验证
- 超时限制（防止 DoS）

### 12.2 错误信息

- 不暴露内部实现细节
- 不返回敏感的堆栈信息
- 统一的错误格式

## 13. 未来扩展

### 13.1 短期扩展（1-3个月）

1. **缓存机制**：实时数据缓存 1-3 秒，减少 API 调用
2. **WebSocket 支持**：推送实时行情更新
3. **批量查询**：一次请求获取多只股票行情

### 13.2 长期扩展（3-6个月）

1. **智能路由**：根据历史成功率动态选择数据源
2. **A/B 测试**：测试不同数据源组合的效果
3. **国际市场**：支持美股、欧股等国际市场

## 14. 总结

本设计通过引入多数据源架构，解决了当前实时行情获取的可靠性问题。核心改进包括：

1. **多数据源支持**：akshare → 新浪 → 东财 → 腾讯 → 网易，提高成功率
2. **明确的参数控制**：`source` 参数让用户明确控制数据来源
3. **时间戳完整性**：实时数据返回 `timestamp`，数据库数据返回 `trade_date`
4. **架构清晰**：逻辑集中在后端，易于维护和扩展
5. **可测试性**：完整的单元测试和集成测试覆盖

设计遵循 SOLID 原则，具有良好的可扩展性和可维护性。
