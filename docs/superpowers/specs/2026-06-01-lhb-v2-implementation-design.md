# 龙虎榜功能 V2 实现设计

**日期**: 2026-06-01  
**状态**: 设计完成，待实现  
**作者**: Claude (Brainstorming Skill)

## 背景

当前 `sentiment.lhb` 命令依赖旧的 v1 模块 (`quantsys.cli.sentiment_query`)，导致查询失败并返回 "Module not available" 错误。需要在 quantsys-v2 中实现原生龙虎榜功能，替代 v1 依赖。

## 目标

1. 在 quantsys-v2 中实现龙虎榜查询功能
2. 支持两种查询模式：单股查询、日期汇总
3. 返回完整信息（含席位明细）
4. 实时查询，不持久化到数据库
5. 复用现有 DividendService 模式，保持架构一致性

## 需求确认

### 查询场景
- ✅ **单股查询**: 查询某只股票的历史龙虎榜记录（如 600737 最近 30 天）
- ✅ **日期汇总**: 查询某一天所有上榜股票的龙虎榜数据（如 2026-05-31 全市场）

### 数据持久化
- ✅ **不持久化**: 每次查询实时调用 akshare API，不存储到数据库
- 理由：查询频率不高，避免维护数据更新任务

### 返回格式
- ✅ **完整信息**: 包含席位明细（买入/卖出前5大营业部）
- 理由：席位明细是龙虎榜最有价值的部分（游资动向分析）

## 架构设计

### 整体架构

复用 **DividendService + DividendDataSource** 模式：

```
quant_cli (sentiment.lhb)
    ↓
TypeScript Agent (QuantV2Client)
    ↓
HTTP API: /api/stock/{symbol}/lhb 或 /api/lhb/daily
    ↓
LhbService (业务逻辑层)
    ↓
LhbDataSource (数据源抽象层)
    ↓
AkshareLhbSource (akshare 实现)
```

### 为什么选择这个方案？

1. **复用成熟模式**: DividendService 已在 V2 中稳定运行，架构清晰
2. **易于测试**: Service 和 DataSource 分离，可 mock 数据源
3. **易于扩展**: 未来可添加其他数据源（如 tushare）
4. **符合规范**: 遵循 V2 分层架构（Service → DataSource）

## 组件设计

### 1. 数据源层 (`services/lhb_data_source.py`)

**职责**: 封装 akshare API 调用

```python
from abc import ABC, abstractmethod
import pandas as pd

class LhbDataSource(ABC):
    """龙虎榜数据源抽象基类"""
    
    @abstractmethod
    def fetch_stock_lhb(self, symbol: str) -> pd.DataFrame:
        """
        获取个股龙虎榜统计
        
        Args:
            symbol: 股票代码或名称（如 600737 或 中粮糖业）
        
        Returns:
            pd.DataFrame: 龙虎榜记录
        """
        pass
    
    @abstractmethod
    def fetch_daily_lhb(self, date: str) -> pd.DataFrame:
        """
        获取某日全市场龙虎榜
        
        Args:
            date: 日期（格式 YYYYMMDD，如 20260531）
        
        Returns:
            pd.DataFrame: 当日所有上榜股票
        """
        pass


class AkshareLhbSource(LhbDataSource):
    """akshare 数据源实现"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    def fetch_stock_lhb(self, symbol: str) -> pd.DataFrame:
        """
        使用 akshare API: ak.stock_lhb_stock_statistic_em(symbol='中粮糖业')
        
        注意：
        - akshare 需要股票名称，不是代码
        - 需要先通过代码查询股票名称
        """
        import akshare as ak
        # 实现细节：代码 → 名称转换 → 调用 API
        pass
    
    def fetch_daily_lhb(self, date: str) -> pd.DataFrame:
        """
        使用 akshare API: ak.stock_lhb_detail_daily_sina(date='20260531')
        
        注意：
        - 需要 lxml 解析器
        - 日期格式必须是 YYYYMMDD
        """
        import akshare as ak
        # 实现细节：调用 API → 返回 DataFrame
        pass
```

**关键点**:
- 处理 akshare 不同 API 的参数格式（股票名称 vs 代码）
- 统一异常处理（网络超时、API 错误、数据为空）
- 添加超时控制（默认 30 秒）

### 2. 服务层 (`services/lhb_service.py`)

**职责**: 业务逻辑、数据转换、格式化

```python
from typing import List, Dict, Optional
import pandas as pd
from services.base_service import ServiceBase
from services.lhb_data_source import LhbDataSource, AkshareLhbSource

class LhbService(ServiceBase):
    """龙虎榜数据服务"""
    
    def __init__(self, data_source: Optional[LhbDataSource] = None):
        super().__init__()
        self.data_source = data_source or AkshareLhbSource()
    
    def get_stock_lhb(self, symbol: str, days: int = 30) -> Dict:
        """
        获取个股龙虎榜记录
        
        Args:
            symbol: 股票代码（如 600737.SH 或 600737）
            days: 查询最近N天（用于过滤，默认 30）
        
        Returns:
            {
                "success": bool,
                "symbol": str,
                "name": str,
                "total_records": int,
                "records": [
                    {
                        "date": "2026-05-31",
                        "reason": "日涨幅偏离值达7%",
                        "close_price": 10.50,
                        "change_pct": 8.5,
                        "net_buy": 5000.0,      # 龙虎榜净买额（万元）
                        "buy_amount": 8000.0,   # 龙虎榜买入额（万元）
                        "sell_amount": 3000.0,  # 龙虎榜卖出额（万元）
                        "buy_seats": [          # 买入前5席位
                            {
                                "name": "某某营业部",
                                "amount": 2000.0
                            },
                            ...
                        ],
                        "sell_seats": [         # 卖出前5席位
                            {
                                "name": "某某营业部",
                                "amount": 1000.0
                            },
                            ...
                        ]
                    }
                ]
            }
        """
        try:
            # 1. 调用数据源
            df = self.data_source.fetch_stock_lhb(symbol)
            
            if df.empty:
                return {
                    "success": False,
                    "error": "该股票近期无龙虎榜记录"
                }
            
            # 2. 数据转换和清洗
            records = self._transform_stock_records(df, days)
            
            # 3. 返回结果
            return {
                "success": True,
                "symbol": symbol,
                "name": records[0].get("name", "") if records else "",
                "total_records": len(records),
                "records": records
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_daily_lhb(self, date: str) -> Dict:
        """
        获取某日全市场龙虎榜
        
        Args:
            date: 日期（格式 YYYYMMDD，如 20260531）
        
        Returns:
            {
                "success": bool,
                "date": "2026-05-31",
                "total_stocks": int,
                "stocks": [
                    {
                        "symbol": "600737",
                        "name": "中粮糖业",
                        "reason": "日涨幅偏离值达7%",
                        "close_price": 10.50,
                        "change_pct": 8.5,
                        "net_buy": 5000.0,
                        "buy_amount": 8000.0,
                        "sell_amount": 3000.0,
                        "buy_seats": [...],
                        "sell_seats": [...]
                    }
                ]
            }
        """
        try:
            # 1. 调用数据源
            df = self.data_source.fetch_daily_lhb(date)
            
            if df.empty:
                return {
                    "success": False,
                    "error": f"{date} 无龙虎榜数据"
                }
            
            # 2. 数据转换
            stocks = self._transform_daily_records(df)
            
            # 3. 返回结果
            return {
                "success": True,
                "date": self._format_date(date),
                "total_stocks": len(stocks),
                "stocks": stocks
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _transform_stock_records(self, df: pd.DataFrame, days: int) -> List[Dict]:
        """转换个股龙虎榜数据为标准格式"""
        # 实现细节：
        # - 过滤最近 N 天
        # - 提取席位明细（买入/卖出前5）
        # - 格式化金额（万元）
        # - 处理 NaN 值
        pass
    
    def _transform_daily_records(self, df: pd.DataFrame) -> List[Dict]:
        """转换日期汇总数据为标准格式"""
        # 实现细节：同上
        pass
    
    def _format_date(self, date: str) -> str:
        """格式化日期：YYYYMMDD → YYYY-MM-DD"""
        return f"{date[:4]}-{date[4:6]}-{date[6:]}"
```

**关键点**:
- 数据清洗（处理 NaN、格式化金额）
- 席位数据提取（买入/卖出前5）
- 统一错误返回格式
- 日期过滤（最近 N 天）

### 3. API 路由层 (`api/routes/sentiment.py`)

**修改现有路由**:

```python
from services.lhb_service import LhbService

# 初始化服务（在文件顶部，与其他服务一起）
lhb_service = LhbService()

@sentiment_bp.route('/api/stock/<symbol>/lhb', methods=['GET'])
@handle_api_error
def get_stock_lhb(symbol):
    """
    龙虎榜 - 个股查询
    
    Query Params:
        days: 查询最近N天（默认 30）
    
    Example:
        GET /api/stock/600737/lhb?days=30
    """
    days = request.args.get('days', 30, type=int)
    result = lhb_service.get_stock_lhb(symbol, days)
    return api_response(result)


@sentiment_bp.route('/api/lhb/daily', methods=['GET'])
@handle_api_error
def get_daily_lhb():
    """
    龙虎榜 - 日期汇总
    
    Query Params:
        date: 日期（格式 YYYYMMDD，必填）
    
    Example:
        GET /api/lhb/daily?date=20260531
    """
    date = request.args.get('date')
    if not date:
        return jsonify({
            'success': False,
            'error': '缺少必填参数: date（格式 YYYYMMDD）'
        }), 400
    
    result = lhb_service.get_daily_lhb(date)
    return api_response(result)
```

**变更点**:
- 移除 v1 依赖（删除 `sys.path.insert` 和 `from quantsys.cli.sentiment_query`）
- 调用新的 `LhbService`
- 新增 `/api/lhb/daily` 端点（日期汇总查询）
- 保持 `/api/stock/<symbol>/lhb` 端点路径不变（向后兼容）

## 数据流

### 单股查询流程

```
1. 用户调用: quant_cli({ command: "sentiment.lhb", params: { symbol: "600737" } })
2. TypeScript Agent → HTTP GET /api/stock/600737/lhb?days=30
3. API Route → lhb_service.get_stock_lhb("600737", 30)
4. LhbService → data_source.fetch_stock_lhb("600737")
5. AkshareLhbSource:
   - 查询股票名称: 600737 → 中粮糖业
   - 调用 akshare: ak.stock_lhb_stock_statistic_em(symbol='中粮糖业')
   - 返回 DataFrame
6. LhbService:
   - 过滤最近 30 天
   - 提取席位明细
   - 格式化数据
7. API Route → 返回 JSON
8. TypeScript Agent → 格式化展示给用户
```

### 日期汇总流程

```
1. 用户调用: quant_cli({ command: "sentiment.lhb", params: { date: "20260531" } })
2. TypeScript Agent → HTTP GET /api/lhb/daily?date=20260531
3. API Route → lhb_service.get_daily_lhb("20260531")
4. LhbService → data_source.fetch_daily_lhb("20260531")
5. AkshareLhbSource:
   - 调用 akshare: ak.stock_lhb_detail_daily_sina(date='20260531')
   - 返回 DataFrame
6. LhbService:
   - 提取席位明细
   - 格式化数据
7. API Route → 返回 JSON
8. TypeScript Agent → 格式化展示给用户
```

## 依赖处理

### Python 依赖

**问题**: akshare 的某些 API 需要 `lxml` 解析器

**解决方案**: 在 `quantsys-v2/requirements.txt` 中添加：

```txt
lxml>=4.9.0
```

**安装**:
```bash
cd quantsys-v2
pip install lxml
```

### akshare API 兼容性

**已知问题**:
- `ak.stock_lhb_stock_statistic_em()` 需要股票名称，不是代码
- `ak.stock_lhb_detail_daily_sina()` 需要 lxml 解析器

**解决方案**:
- 在 `AkshareLhbSource` 中实现代码 → 名称转换
- 添加 lxml 依赖

## 错误处理

### 常见错误场景

1. **股票代码不存在**
   - 返回: `{"success": false, "error": "股票代码不存在"}`

2. **日期无数据**
   - 返回: `{"success": false, "error": "20260531 无龙虎榜数据"}`

3. **网络超时**
   - 返回: `{"success": false, "error": "网络请求超时"}`

4. **akshare API 错误**
   - 返回: `{"success": false, "error": "数据源错误: <详细信息>"}`

### 错误处理策略

- 所有异常在 Service 层捕获
- 返回统一的错误格式 `{"success": false, "error": "..."}`
- 记录详细日志（logger.error）

## 测试策略

### 单元测试

**测试文件**: `quantsys-v2/tests/services/test_lhb_service.py`

```python
def test_get_stock_lhb_success():
    """测试个股查询成功"""
    # Mock DataSource
    # 验证返回格式
    pass

def test_get_stock_lhb_no_data():
    """测试个股无数据"""
    pass

def test_get_daily_lhb_success():
    """测试日期汇总成功"""
    pass

def test_get_daily_lhb_invalid_date():
    """测试无效日期"""
    pass
```

### 集成测试

**测试文件**: `quantsys-v2/tests/api/test_lhb_routes.py`

```python
def test_api_stock_lhb():
    """测试 /api/stock/{symbol}/lhb 端点"""
    pass

def test_api_daily_lhb():
    """测试 /api/lhb/daily 端点"""
    pass
```

### 手动测试

```bash
# 1. 启动服务
cd quantsys-v2
python api/server.py

# 2. 测试个股查询
curl "http://127.0.0.1:5001/api/stock/600737/lhb?days=30"

# 3. 测试日期汇总
curl "http://127.0.0.1:5001/api/lhb/daily?date=20260531"

# 4. 测试 TypeScript Agent
cd ..
npm run dev
# 输入: quant_cli({ command: "sentiment.lhb", params: { symbol: "600737" } })
```

## 实现清单

### 文件清单

1. **新增文件**:
   - `quantsys-v2/services/lhb_data_source.py` - 数据源抽象 + akshare 实现
   - `quantsys-v2/services/lhb_service.py` - 业务逻辑服务
   - `quantsys-v2/tests/services/test_lhb_service.py` - 服务层单元测试
   - `quantsys-v2/tests/api/test_lhb_routes.py` - API 路由集成测试

2. **修改文件**:
   - `quantsys-v2/api/routes/sentiment.py` - 更新路由实现
   - `quantsys-v2/requirements.txt` - 添加 lxml 依赖

3. **无需修改**:
   - `src/infrastructure/tools/core/quant-cli-tool.ts` - sentiment.lhb 命令定义保持不变
   - `src/infrastructure/quant/quant-v2-client.ts` - HTTP 客户端自动适配

### 实现步骤

1. **Phase 1: 数据源层**
   - 实现 `LhbDataSource` 抽象类
   - 实现 `AkshareLhbSource`
   - 单元测试（mock akshare）

2. **Phase 2: 服务层**
   - 实现 `LhbService`
   - 数据转换逻辑
   - 单元测试

3. **Phase 3: API 层**
   - 更新 `sentiment.py` 路由
   - 集成测试

4. **Phase 4: 依赖和验证**
   - 添加 lxml 依赖
   - 端到端测试
   - 文档更新

## 风险和缓解

### 风险 1: akshare API 变更

**风险**: akshare 可能更新 API 接口或返回格式

**缓解**:
- 使用 DataSource 抽象层，易于切换数据源
- 添加详细的错误日志
- 编写集成测试，及时发现 API 变更

### 风险 2: lxml 安装失败

**风险**: 某些环境下 lxml 安装可能失败（需要编译）

**缓解**:
- 使用预编译的 wheel 包（pip 默认行为）
- 文档中说明安装步骤
- 如果失败，考虑使用其他解析器（如 html5lib）

### 风险 3: 查询性能

**风险**: akshare API 响应慢（3-10秒）

**缓解**:
- 设置合理的超时时间（30秒）
- 在 API 文档中说明预期响应时间
- 未来可考虑添加缓存层（如果查询频率增加）

## 后续优化

### 短期（可选）

1. **缓存层**: 如果查询频率增加，添加 Redis 缓存（TTL 1小时）
2. **批量查询**: 支持一次查询多只股票的龙虎榜

### 长期（可选）

1. **数据持久化**: 如果需要历史分析，考虑定时任务将数据存入数据库
2. **多数据源**: 添加 tushare 等其他数据源支持
3. **数据分析**: 基于龙虎榜数据的游资追踪、席位分析等高级功能

## 参考

- **现有实现**: `quantsys-v2/services/dividend_service.py` - 分红服务（架构参考）
- **akshare 文档**: https://akshare.akfamily.xyz/data/stock/stock.html#id494
- **项目架构**: `quantsys-v2/CLAUDE.md` - V2 分层架构说明
