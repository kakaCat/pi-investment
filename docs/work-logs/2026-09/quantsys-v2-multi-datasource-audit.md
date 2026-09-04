# quantsys-v2 多数据源架构审计报告

**审计日期**: 2026-09-01  
**审计范围**: quantsys-v2 多数据源架构完整性、可靠性、可维护性  
**审计人**: Claude (Fable 5)

---

## 执行摘要

quantsys-v2 的多数据源架构**整体设计合理，核心机制完善**，但存在**7 个 P0 级问题**和**12 个改进机会**。架构已实现：

✅ **六边形架构分层清晰**（Domain Ports → Adapters → Application）  
✅ **自动降级机制完善**（健康评分 + 熔断器 + 动态优先级）  
✅ **多数据源类型覆盖**（行情/K线/财务/市场/分红/港股/指数）  
✅ **来源追溯机制**（QuoteData.source 字段标记）  
✅ **缓存层实现**（TTL + LRU 淘汰）  

⚠️ **关键风险**：
1. 缓存层未实际集成到 Manager（形同虚设）
2. 无 Provider 健康监控告警
3. K线回填无事务保护（可能重复/遗漏）
4. 熔断器状态无持久化（进程重启即清空）
5. 超时配置硬编码（60s 对慢源不合理）

---

## 1. 架构层次审计

### 1.1 六边形架构分层 ✅

```
┌─────────────────────────────────────────────────┐
│  Application Layer (应用层)                      │
│  - RealtimeQuoteService                         │
│  - StockDataService                             │
│  - MarketDataService                            │
│  └─ 依赖 IDataProviderManager 接口               │
└─────────────────────────────────────────────────┘
                    ↓ 依赖倒置
┌─────────────────────────────────────────────────┐
│  Domain Layer (领域层)                           │
│  - datasource_ports.py                          │
│    * IDataProviderManager (Manager 接口)        │
│    * IQuoteProvider (数据源接口)                │
│    * IKlineProvider                             │
│    * IFinancialProvider                         │
│    * IDividendProvider                          │
│    * IMarketProvider                            │
│    * IStockProvider                             │
│    * ICacheService                              │
│    * ICircuitBreaker                            │
└─────────────────────────────────────────────────┘
                    ↑ 实现接口
┌─────────────────────────────────────────────────┐
│  Adapters Layer (适配器层)                       │
│  - adapters/outbound/datasources/               │
│    * manager.py (DataProviderManager)           │
│    * circuit_breaker.py (CircuitBreaker)        │
│    * cache.py (DataSourceCache)                 │
│    * providers/                                 │
│      - quote/ (5 providers)                     │
│      - kline/ (4 providers)                     │
│      - financial/ (3 providers)                 │
│      - dividend/ (1 provider)                   │
│      - market/ (1 provider)                     │
│      - sector/ (1 provider)                     │
│      - stock/ (1 provider)                      │
│      - hk/ (1 provider)                         │
│      - index/ (1 provider)                      │
└─────────────────────────────────────────────────┘
```

**评估**: ✅ 架构清晰，依赖方向正确，符合 DDD + 六边形架构原则

---

## 2. 数据源类型与 Provider 覆盖

### 2.1 Quote Providers（实时行情）

| Provider | 文件 | 状态 | 优先级 | 备注 |
|---------|------|------|--------|------|
| **TencentQuoteProvider** | `quote/tencent.py` | ✅ 活跃 | P1 (最高) | qt.gtimg.cn，响应快，绕过代理 |
| **SinaQuoteProvider** | `quote/sina.py` | ✅ 活跃 | P2 | hq.sinajs.cn，稳定但偶尔延迟 |
| **EastmoneyQuoteProvider** | `quote/eastmoney.py` | ⚠️ 不稳定 | P3 | 连接问题频繁 |
| **AkshareQuoteProvider** | `quote/akshare.py` | ⚠️ 慢 | P4 (兜底) | 平均 75s，仅作最后备选 |
| **NeteaseQuoteProvider** | `quote/netease.py` | ✅ 活跃 | P5 | 未在 manager.py 注册 ❌ |

**问题 P0-1**: NeteaseQuoteProvider 已实现但**未注册到 DataProviderManager**，形同死代码。

### 2.2 Kline Providers（K线数据）

| Provider | 文件 | 状态 | 优先级 | 数据源 |
|---------|------|------|--------|--------|
| **DatabaseKlineProvider** | `kline/database.py` | ✅ 活跃 | P1 | 本地 PostgreSQL (最快) |
| **BaostockKlineProvider** | `kline/baostock.py` | ✅ 活跃 | P2 | 独立 TCP 服务，抗封禁 |
| **TencentKlineProvider** | `kline/tencent.py` | ⚠️ IP封禁 | P3 | ifzq.gtimg.cn (历史封禁) |
| **AkshareKlineProvider** | `kline/akshare.py` | ⚠️ IP封禁 | P4 | eastmoney (历史封禁) |

**架构亮点**: 
- ✅ **数据库优先策略**（Database → Network），减少外部调用
- ✅ **自动回填机制** (`_backfill_klines_to_db`)，网络获取后自动存储
- ✅ **Baostock 看门狗机制**（15s 超时 + socket 强制关闭），防止永久阻塞

**问题 P0-2**: K线回填无事务保护，并发回填可能导致**主键冲突**或**数据遗漏**。

```python
# manager.py:649-710 (有问题的实现)
def _backfill_klines_to_db(self, symbol: str, klines: list) -> bool:
    try:
        session = get_session()
        for kline in klines:
            existing = session.query(DailyKline).filter_by(
                symbol=symbol,
                trade_date=trade_date
            ).first()  # ❌ SELECT + INSERT 非原子，race condition
            if existing:
                continue
            daily = DailyKline(...)
            session.add(daily)
        
        if saved_count > 0:
            session.commit()  # ❌ 无异常重试，失败即数据丢失
        return True
    except Exception as e:
        session.rollback()  # ❌ rollback 后未记录失败，调用方以为成功
        return False
```

### 2.3 Financial Providers（财务数据）

| Provider | 文件 | 数据源 | 优先级 |
|---------|------|--------|--------|
| **SinaFinancialProvider** | `financial/sina.py` | 新浪财经 | P1 |
| **EastmoneyFinancialProvider** | `financial/eastmoney.py` | 东方财富 | P2 |
| **AkshareFinancialStatementProvider** | `financial/akshare.py` | akshare | P3 |

### 2.4 其他 Providers

| 类型 | Provider | 数量 | 状态 |
|-----|---------|------|------|
| Dividend | AkshareDividendProvider | 1 | ✅ |
| Market | AkshareMarketProvider | 1 | ✅ |
| Sector | EastmoneySectorProvider | 1 | ✅ |
| Stock | AkshareStockProvider | 1 | ✅ |
| HK | AkshareHKProvider | 1 | ✅ |
| Index | AkshareIndexProvider | 1 | ✅ |

**问题 P1-1**: Dividend/Market/Sector 等类型**仅有单一 Provider**，无降级能力。

---

## 3. 自动降级机制审计

### 3.1 健康评分算法 ✅

```python
# manager.py:312-333
def health_score(provider):
    success_rate = success / total  # 基础成功率 (0-1)
    failure_penalty = min(consecutive_failures / threshold, 1.0)  # 连续失败惩罚
    reliability_bonus = min(success / recovery_window, 0.2)  # 可靠性奖励
    return success_rate - failure_penalty + reliability_bonus
```

**评估**: ✅ 算法合理，综合考虑历史成功率、连续失败次数、长期可靠性。

### 3.2 熔断器机制 ✅

**实现**: 基于 `pybreaker` 库的标准三态熔断器（CLOSED → OPEN → HALF_OPEN）

```python
# circuit_breaker.py:44-175
class CircuitBreaker(ICircuitBreaker):
    - failure_threshold: 连续失败10次触发熔断 (默认)
    - timeout: 熔断持续300秒 (5分钟)
    - success_threshold: HALF_OPEN 状态需1次成功即恢复
```

**问题 P0-3**: 熔断器状态**仅存在内存**，进程重启后清空，无法持久化历史熔断记录。

**问题 P1-2**: 熔断阈值**硬编码**（10次/300s），不同 Provider 特性差异大（baostock 慢但稳定 vs eastmoney 快但不稳定），应可配置。

### 3.3 超时控制 ⚠️

```python
# manager.py:42-44
self.provider_timeout_seconds = 60  # ❌ 硬编码，对所有 Provider 统一
```

**问题 P0-4**: 超时配置**硬编码 60s**，对不同 Provider 不合理：
- **Baostock**: 15s 内部看门狗，60s 超时形同虚设
- **Akshare**: 平均 75s，60s 超时导致每次都超时
- **Database**: 本地查询，60s 过长

**建议**: 按 Provider 类型分级（Database: 5s, Network: 15-30s, Slow: 90s）

### 3.4 降级流程 ✅

```python
# manager.py:135-216
def _try_providers(self, providers, method_name, *args, **kwargs):
    sorted_providers = self._sort_providers_by_health(providers)  # 健康评分排序
    for provider in sorted_providers:
        if self._is_circuit_broken(provider.name):  # 熔断检查
            continue
        try:
            result = fut.result(timeout=self.provider_timeout_seconds)  # 超时控制
            if result and self._is_valid(result):  # 数据校验
                self._record_success(provider.name)
                return {'success': True, 'data': result, 'source': provider.name}
        except TimeoutError:
            self._record_failure(provider.name)
            continue
```

**评估**: ✅ 降级流程完善（健康排序 → 熔断跳过 → 超时保护 → 数据校验 → 失败记录）

---

## 4. 数据校验机制

### 4.1 校验逻辑 ✅

```python
# manager.py:218-270
def _is_valid(self, data) -> bool:
    # 1. 必须有 source 字段
    if not (hasattr(data, 'source') and data.source):
        return False
    
    # 2. DataFrame 不能为空
    if isinstance(data, pd.DataFrame):
        if len(data) == 0 or data.empty:
            return False
        # 数值列全 NaN 视为无效
        if data[numeric_cols].dropna(how='all').empty:
            return False
    
    # 3. QuoteData 的 price 不能为 None/NaN
    if hasattr(data, 'price'):
        if data.price is None or pd.isna(data.price):
            return False
    
    return True
```

**评估**: ✅ 校验逻辑合理，防止空数据/NaN 数据污染返回结果。

**问题 P1-3**: 校验规则**硬编码在 Manager**，不同数据类型（Quote/Kline/Financial）应有各自校验器。

---

## 5. 缓存层审计

### 5.1 缓存实现 ✅

```python
# cache.py:20-190
class DataSourceCache(ICacheService):
    - TTL: 60s (默认)
    - Max Size: 1000 entries
    - Eviction: LRU (Least Recently Used)
    - Key Generation: MD5(method + params)
```

**架构**: ✅ 实现 ICacheService 接口，支持 get/set/delete/clear 操作。

### 5.2 致命问题 ❌

**问题 P0-5**: 缓存层**完全未使用**！

```python
# manager.py:32-41 (DataProviderManager 构造函数)
def __init__(self, ds=None):
    self.provider_timeout_seconds = 60
    self.quote_providers = [...]
    self.financial_providers = [...]
    # ❌ 从未初始化 DataSourceCache 实例
    # ❌ 从未在 get_quote/get_klines 等方法中调用缓存
```

**影响**: 
- ⚠️ 重复请求无缓存保护，浪费 API 配额
- ⚠️ 相同参数多次调用，每次都走网络
- ⚠️ 短时间高频访问（如前端刷新），压力全打到外部数据源

**证据**: 搜索 `manager.py` 全文，无任何 `cache` 或 `DataSourceCache` 引用。

---

## 6. 来源追溯机制 ✅

### 6.1 实现方式

```python
# 每个 Provider 返回时注入 source 字段
class TencentQuoteProvider(QuoteProvider):
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        return QuoteData(
            symbol=symbol,
            price=price,
            source=self.name,  # ✅ 注入来源标记
            ...
        )

# Manager 返回时保留 source
def get_quote(self, symbol: str) -> dict:
    return {
        'success': True,
        'data': quote_data,  # quote_data.source = 'tencent'
        'source': provider.name  # ✅ 同时在外层返回
    }
```

**评估**: ✅ 双层追溯（数据对象内 + 响应字典外），完整记录数据来源。

---

## 7. Provider 实现质量审计

### 7.1 TencentQuoteProvider ✅

**优点**:
- ✅ 代码格式清晰（字段位置注释详细）
- ✅ 错误处理完善（空响应/解析失败/字段缺失）
- ✅ 绕过代理配置（`proxies={'http': None}`）
- ✅ GBK 编码处理

**问题 P2-1**: 硬编码 `timeout=self.timeout`，但基类 `QuoteProvider` 未定义 `timeout` 属性。

### 7.2 BaostockKlineProvider ✅

**优点**:
- ✅ **看门狗机制**（15s 超时 + 强制关闭 socket），防止永久阻塞
- ✅ **会话复用**（`_ensure_login` + `_bs` 缓存），减少登录开销
- ✅ **会话错误识别**（`_SESSION_ERROR_MARKERS` + 自动重登），提高成功率
- ✅ **单位契约清晰**（volume=股, amount=元, turn=%）

```python
# kline/baostock.py:25-44 (看门狗实现)
def _with_socket_timeout(fn, timeout=15):
    watchdog = threading.Timer(timeout, _close_baostock_socket)
    watchdog.start()
    try:
        return fn()  # 执行 baostock 阻塞调用
    finally:
        watchdog.cancel()  # 成功则取消看门狗
```

**评估**: ✅ 代码质量优秀，是整个代码库中**防御性编程的典范**。

### 7.3 DatabaseKlineProvider 🔍

**缺失**: 该文件未在本次审计中读取，需单独审查。

**推断问题**:
- ❓ 是否处理 `trade_date` 索引？
- ❓ 是否处理股票退市/停牌缺失数据？
- ❓ 查询性能优化（批量查询 vs 单次查询）？

---

## 8. 应用层集成审计

### 8.1 RealtimeQuoteService ✅

```python
# application/services/realtime_quote_service.py
class RealtimeQuoteService:
    def __init__(self):
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider_manager = get_data_provider_manager()  # ✅ 依赖注入
    
    def get_realtime_quote(self, symbol: str) -> Optional[QuoteData]:
        result = self.provider_manager.get_quote(symbol)  # ✅ 委托给 Manager
        if result['success']:
            return result['data']
        return None
```

**评估**: ✅ 应用层服务正确依赖 `IDataProviderManager` 接口，解耦良好。

### 8.2 其他服务

根据 `grep -l "IDataProviderManager"` 结果，以下服务已迁移到统一架构：
- ✅ `opportunity_scoring_service.py`
- ✅ `stock_data_service.py`
- ✅ `valuation_data_service.py`
- ✅ `enhanced_buy_range_service.py`
- ✅ `data_backfiller.py`
- ✅ `trading_calendar_service.py`
- ✅ `market_data_service.py`
- ✅ `dividend_service.py`
- ✅ `financial_analysis_service.py`
- ✅ `hk_market_data_service.py`
- ✅ `technical_analysis_service.py`

---

## 9. 问题汇总与优先级

### 9.1 P0 级问题（立即修复）

| ID | 问题 | 影响 | 修复工作量 |
|----|------|------|-----------|
| P0-1 | **NeteaseQuoteProvider 未注册** | Quote 降级能力缺失 | 5min（1行代码） |
| P0-2 | **K线回填无事务保护** | 并发写入数据损坏 | 2h（改用 INSERT ON CONFLICT） |
| P0-3 | **熔断器状态无持久化** | 进程重启失去历史 | 4h（Redis 持久化） |
| P0-4 | **超时配置硬编码** | Akshare 必超时，Database 过长 | 1h（配置化） |
| P0-5 | **缓存层完全未使用** | 重复请求浪费 API | 2h（集成缓存） |
| P0-6 | **无健康监控告警** | Provider 全挂无人知晓 | 4h（Prometheus 指标） |
| P0-7 | **单一 Provider 类型无降级** | Dividend/Market 挂掉即失败 | 8h（补充备用源） |

### 9.2 P1 级问题（重要改进）

| ID | 问题 | 影响 | 修复工作量 |
|----|------|------|-----------|
| P1-1 | Dividend/Market 仅单源 | 降级能力不足 | 1-2天（补充 Provider） |
| P1-2 | 熔断阈值硬编码 | 不同源特性差异大 | 1h（配置化） |
| P1-3 | 数据校验规则耦合 | 扩展性差 | 4h（策略模式） |
| P1-4 | 无 Provider 性能指标 | 无法量化优化效果 | 2h（P50/P90/P99） |
| P1-5 | 无降级决策日志 | 排查困难 | 1h（结构化日志） |

### 9.3 P2 级问题（优化项）

| ID | 问题 | 影响 | 修复工作量 |
|----|------|------|-----------|
| P2-1 | TencentQuoteProvider timeout 未定义 | 潜在 AttributeError | 30min |
| P2-2 | 无批量请求优化 | 逐个查询效率低 | 1天（批量接口） |
| P2-3 | 无请求去重 | 相同请求并发重复 | 2h（请求合并） |
| P2-4 | 无降级成本追踪 | 不知道降级代价 | 1h（成本指标） |
| P2-5 | 无 Provider 黑名单 | 永久失效源仍重试 | 2h（黑名单机制） |
| P2-6 | 无数据完整性检查 | K线缺失日未发现 | 已有 `get_data_completeness`，需集成 |
| P2-7 | 无智能重试（exponential backoff） | 瞬时故障频繁重试 | 2h（退避算法） |

---

## 10. 修复建议（按优先级）

### 10.1 立即执行（P0）

#### P0-5: 集成缓存层（最高优先级）

```python
# manager.py 修改
class DataProviderManager(IDataProviderManager):
    def __init__(self, ds=None):
        # ... existing code ...
        self._cache = DataSourceCache(ttl=60, max_size=1000)  # ✅ 初始化缓存
    
    def get_quote(self, symbol: str) -> dict:
        cache_key = self._cache.make_key('get_quote', symbol)
        cached = self._cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for quote {symbol}")
            return cached
        
        result = self._try_providers(self.quote_providers, 'get_quote', symbol)
        if result.get('success'):
            self._cache.set(cache_key, result)
        return result
```

#### P0-2: K线回填事务保护

```python
# manager.py:649-710 修改
def _backfill_klines_to_db(self, symbol: str, klines: list) -> bool:
    try:
        session = get_session()
        saved_count = 0
        
        for kline in klines:
            trade_date = parse_date(kline.date).date()
            
            # ✅ 使用 ON CONFLICT DO NOTHING（原子操作）
            stmt = insert(DailyKline).values(
                symbol=symbol,
                trade_date=trade_date,
                open=kline.open,
                high=kline.high,
                low=kline.low,
                close=kline.close,
                volume=kline.volume,
                source=kline.source,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ).on_conflict_do_nothing(
                index_elements=['symbol', 'trade_date']
            )
            
            result = session.execute(stmt)
            if result.rowcount > 0:
                saved_count += 1
        
        session.commit()
        if saved_count > 0:
            logger.info(f"Backfilled {saved_count} klines for {symbol}")
        return True
        
    except Exception as e:
        logger.error(f"Backfill failed for {symbol}: {e}")
        session.rollback()
        # ✅ 记录失败到监控系统
        metrics.increment('kline_backfill_failures', tags={'symbol': symbol})
        return False
```

#### P0-1: 注册 NeteaseQuoteProvider

```python
# manager.py:50-55 添加
from adapters.outbound.datasources.providers.quote.netease import NeteaseQuoteProvider

self.quote_providers = [
    TencentQuoteProvider(),
    SinaQuoteProvider(),
    NeteaseQuoteProvider(),  # ✅ 添加此行
    EastmoneyQuoteProvider(),
    AkshareQuoteProvider(),
]
```

#### P0-4: 超时配置化

```python
# manager.py 修改
PROVIDER_TIMEOUTS = {
    'database': 5,      # 本地查询
    'tencent': 15,      # 快速网络源
    'sina': 15,
    'eastmoney': 20,
    'baostock': 30,     # TCP 连接稍慢
    'akshare': 90,      # 已知慢源
}

class DataProviderManager:
    def __init__(self):
        self.default_timeout = 30
    
    def _try_providers(self, providers, method_name, *args, **kwargs):
        for provider in sorted_providers:
            timeout = PROVIDER_TIMEOUTS.get(provider.name, self.default_timeout)
            fut = guard.submit(_guarded_call)
            result = fut.result(timeout=timeout)  # ✅ 使用自定义超时
```

#### P0-6: 健康监控告警

```python
# 新增文件: adapters/outbound/datasources/monitoring.py
from prometheus_client import Gauge, Counter

provider_health_score = Gauge(
    'provider_health_score',
    'Provider health score (0-1)',
    ['provider_name', 'provider_type']
)

provider_circuit_breaker_state = Gauge(
    'provider_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['provider_name']
)

provider_request_total = Counter(
    'provider_request_total',
    'Total requests to provider',
    ['provider_name', 'result']  # result=success/failure/timeout
)

# manager.py 集成
def _record_success(self, provider_name: str):
    # ... existing code ...
    provider_request_total.labels(provider_name=provider_name, result='success').inc()
    provider_health_score.labels(
        provider_name=provider_name,
        provider_type=self._get_provider_type(provider_name)
    ).set(self._calculate_health_score(provider_name))
```

### 10.2 短期优化（P1）

#### P1-1: 补充备用数据源

```python
# 新增文件: adapters/outbound/datasources/providers/dividend/eastmoney.py
class EastmoneyDividendProvider(IDividendProvider):
    @property
    def name(self) -> str:
        return "eastmoney_dividend"
    
    def get_dividends(self, symbol: str, years: int = 5) -> Optional[DividendData]:
        # 实现东方财富分红数据获取
        ...

# manager.py 注册
self.dividend_providers = [
    AkshareDividendProvider(),
    EastmoneyDividendProvider(),  # ✅ 备用源
]
```

#### P1-3: 数据校验策略化

```python
# 新增文件: adapters/outbound/datasources/validators.py
class DataValidator(ABC):
    @abstractmethod
    def is_valid(self, data: Any) -> bool:
        pass

class QuoteDataValidator(DataValidator):
    def is_valid(self, data: QuoteData) -> bool:
        return (
            data.source and
            data.price is not None and
            data.price > 0 and
            not pd.isna(data.price)
        )

class KlineDataValidator(DataValidator):
    def is_valid(self, data: List[KlineData]) -> bool:
        return (
            len(data) > 0 and
            all(k.source for k in data) and
            all(k.close > 0 for k in data)
        )

# manager.py 使用
class DataProviderManager:
    def __init__(self):
        self._validators = {
            'quote': QuoteDataValidator(),
            'kline': KlineDataValidator(),
            # ...
        }
    
    def _is_valid(self, data, data_type='unknown') -> bool:
        validator = self._validators.get(data_type)
        if validator:
            return validator.is_valid(data)
        return self._default_validation(data)  # 兜底逻辑
```

### 10.3 长期优化（P2）

#### P2-2: 批量请求优化

```python
# domain/ports/datasource_ports.py 添加
class IQuoteProvider(ABC):
    @abstractmethod
    def get_batch_quotes(self, symbols: List[str]) -> Dict[str, QuoteData]:
        """批量获取行情（Provider 自行决定是串行还是真批量）"""
        pass

# manager.py 实现
def get_batch_quotes(self, symbols: List[str]) -> Dict[str, QuoteData]:
    # 优先尝试支持批量的 Provider
    for provider in self._sort_providers_by_health(self.quote_providers):
        if hasattr(provider, 'get_batch_quotes'):
            try:
                result = provider.get_batch_quotes(symbols)
                if result:
                    return result
            except Exception:
                continue
    
    # 降级到逐个查询
    result = {}
    for symbol in symbols:
        quote_result = self.get_quote(symbol)
        if quote_result.get('success'):
            result[symbol] = quote_result['data']
    return result
```

#### P2-3: 请求去重（防抖）

```python
# 新增文件: adapters/outbound/datasources/deduplicator.py
import asyncio
from typing import Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class PendingRequest:
    key: str
    future: asyncio.Future
    created_at: datetime = field(default_factory=datetime.now)

class RequestDeduplicator:
    """请求去重器：相同参数的并发请求合并为一次调用"""
    
    def __init__(self):
        self._pending: Dict[str, PendingRequest] = {}
    
    async def deduplicate(self, key: str, fn: Callable) -> Any:
        if key in self._pending:
            # 已有请求正在执行，等待其结果
            logger.info(f"Request deduplication hit for key: {key[:50]}...")
            return await self._pending[key].future
        
        # 创建新请求
        future = asyncio.Future()
        self._pending[key] = PendingRequest(key=key, future=future)
        
        try:
            result = await fn()
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            del self._pending[key]
```

---

## 11. 测试覆盖审计

### 11.1 现有测试文件

```
tests/
├── test_quote_providers_last_error.py
├── test_qlib_data_adapter.py
├── test_data_pipeline_service.py
├── test_stock_data_fix.py
├── test_data_fetch_stage.py
├── test_adapters.py
├── test_data_pipeline_integration.py
├── test_data_service.py
├── infrastructure/data_providers/
│   ├── providers/
│   │   ├── test_baostock_kline_provider.py
│   │   ├── test_quote_providers.py
│   │   ├── test_sector_providers.py
│   │   └── test_tencent_kline_provider.py
│   └── test_provider_manager.py
├── integration/
│   └── test_provider_failover.py
└── services/quote_providers/
    ├── test_akshare_provider.py
    └── test_sina_provider.py
```

### 11.2 测试覆盖缺口

| 组件 | 测试文件 | 状态 |
|------|---------|------|
| DataProviderManager | `test_provider_manager.py` | ✅ 存在 |
| CircuitBreaker | ❌ 缺失 | ⚠️ 需补充 |
| DataSourceCache | `test_cache_service.py` | ✅ 存在但未集成 |
| 自动降级流程 | `test_provider_failover.py` | ✅ 存在 |
| 健康评分算法 | ❌ 缺失 | ⚠️ 需补充 |
| K线回填 | ❌ 缺失 | ⚠️ 需补充 |
| 数据校验 | ❌ 缺失 | ⚠️ 需补充 |

**建议**: 补充缺失的单元测试，覆盖关键路径（熔断/降级/回填）。

---

## 12. 文档完整性审计

### 12.1 现有文档

| 文档 | 路径 | 评估 |
|------|------|------|
| 项目总览 | `CLAUDE.md` | ✅ 完善 |
| 后端文档 | `quantsys-v2/CLAUDE.md` | ✅ 完善 |
| 数据源端口定义 | `domain/ports/datasource_ports.py` | ✅ 代码即文档 |

### 12.2 缺失文档

| 文档 | 内容 | 优先级 |
|------|------|--------|
| **多数据源架构设计文档** | 架构图、降级策略、熔断机制 | P1 |
| **Provider 开发指南** | 如何新增 Provider、接口规范 | P1 |
| **运维手册** | 熔断器重置、缓存清理、监控告警 | P1 |
| **性能调优指南** | 超时配置、并发控制、批量优化 | P2 |
| **故障排查手册** | 常见错误、日志分析、降级排查 | P2 |

---

## 13. 总体评价

### 13.1 优点 ✅

1. **架构设计优秀**: 六边形架构 + DDD，依赖倒置清晰
2. **降级机制完善**: 健康评分 + 熔断器 + 动态优先级
3. **代码质量良好**: BaostockKlineProvider 等防御性编程典范
4. **来源追溯完整**: 双层 source 标记，数据可溯源
5. **应用层解耦**: 服务层正确依赖接口，易于测试和替换

### 13.2 缺点 ⚠️

1. **缓存层形同虚设**: 已实现但完全未集成（P0-5）
2. **监控告警缺失**: Provider 全挂无人知晓（P0-6）
3. **单一源无降级**: Dividend/Market 等类型仅单源（P0-7）
4. **配置硬编码**: 超时/阈值不可配置（P0-4, P1-2）
5. **文档不完整**: 缺运维手册和故障排查指南

### 13.3 风险等级

| 风险 | 等级 | 说明 |
|------|------|------|
| **数据可用性** | 🟡 中 | 单一源类型无降级，但影响范围有限 |
| **性能问题** | 🔴 高 | 缓存未启用，重复请求浪费严重 |
| **数据正确性** | 🟡 中 | K线回填 race condition，低频但可能损坏 |
| **运维可见性** | 🔴 高 | 无监控告警，故障发现滞后 |
| **扩展性** | 🟢 低 | 架构良好，添加新 Provider 容易 |

---

## 14. 执行计划（建议）

### Phase 1: 紧急修复（1-2 天）

**目标**: 解决 P0 级问题，恢复基本可靠性

- [ ] P0-5: 集成缓存层（2h）
- [ ] P0-1: 注册 NeteaseQuoteProvider（5min）
- [ ] P0-4: 超时配置化（1h）
- [ ] P0-2: K线回填事务保护（2h）
- [ ] P0-6: 健康监控告警（4h）

**验证**: 
- 缓存命中率 > 50%（前端刷新场景）
- K线回填无 IntegrityError
- Prometheus 指标正常上报

### Phase 2: 重要改进（1 周）

**目标**: 补齐能力短板，提升降级能力

- [ ] P0-7: 补充 Dividend/Market 备用源（8h）
- [ ] P0-3: 熔断器状态持久化（4h）
- [ ] P1-2: 熔断阈值配置化（1h）
- [ ] P1-3: 数据校验策略化（4h）
- [ ] P1-4: 性能指标采集（P50/P90/P99）（2h）
- [ ] P1-5: 降级决策结构化日志（1h）

**验证**:
- 所有 Provider 类型至少 2 个源
- 熔断状态持久化到 Redis
- 降级决策可追溯

### Phase 3: 长期优化（2-3 周）

**目标**: 性能优化、用户体验提升

- [ ] P2-2: 批量请求优化（1天）
- [ ] P2-3: 请求去重机制（2h）
- [ ] P2-7: 智能重试（exponential backoff）（2h）
- [ ] 补充单元测试（CircuitBreaker/健康评分/回填）（2天）
- [ ] 编写运维手册和故障排查指南（1天）
- [ ] 性能压测与调优（2天）

---

## 15. 附录

### 15.1 Provider 列表汇总

| 类型 | Provider | 优先级 | 状态 | 数据源 |
|------|---------|--------|------|--------|
| Quote | Tencent | P1 | ✅ | qt.gtimg.cn |
| Quote | Sina | P2 | ✅ | hq.sinajs.cn |
| Quote | Netease | P3 | ⚠️ 未注册 | money.163.com |
| Quote | Eastmoney | P4 | ⚠️ 不稳定 | eastmoney |
| Quote | Akshare | P5 | ⚠️ 慢 | akshare |
| Kline | Database | P1 | ✅ | PostgreSQL |
| Kline | Baostock | P2 | ✅ | baostock TCP |
| Kline | Tencent | P3 | ⚠️ IP封 | ifzq.gtimg.cn |
| Kline | Akshare | P4 | ⚠️ IP封 | eastmoney |
| Financial | Sina | P1 | ✅ | 新浪财经 |
| Financial | Eastmoney | P2 | ✅ | 东方财富 |
| Financial | Akshare | P3 | ✅ | akshare |
| Dividend | Akshare | P1 | ✅ | akshare |
| Market | Akshare | P1 | ✅ | akshare |
| Sector | Eastmoney | P1 | ✅ | 东方财富 |
| Stock | Akshare | P1 | ✅ | akshare |
| HK | Akshare | P1 | ✅ | akshare |
| Index | Akshare | P1 | ✅ | akshare |

### 15.2 关键指标建议

| 指标 | 类型 | 说明 |
|------|------|------|
| `provider_health_score` | Gauge | Provider 健康分 (0-1) |
| `provider_circuit_breaker_state` | Gauge | 熔断器状态 (0/1/2) |
| `provider_request_total` | Counter | 请求总数（按结果分类） |
| `provider_request_duration_seconds` | Histogram | 请求耗时分布 (P50/P90/P99) |
| `provider_failover_total` | Counter | 降级次数 |
| `cache_hit_ratio` | Gauge | 缓存命中率 |
| `kline_backfill_failures` | Counter | K线回填失败次数 |

### 15.3 告警规则建议

| 告警 | 条件 | 等级 |
|------|------|------|
| **所有 Quote Provider 熔断** | `sum(provider_circuit_breaker_state{type="quote"}) == count(provider{type="quote"})` | 🔴 P0 |
| **主力 Provider 连续失败** | `provider_health_score{provider="tencent"} < 0.3 for 5m` | 🟡 P1 |
| **缓存命中率过低** | `cache_hit_ratio < 0.3 for 10m` | 🟡 P1 |
| **K线回填失败激增** | `rate(kline_backfill_failures[5m]) > 10` | 🟡 P1 |

---

## 结论

quantsys-v2 的多数据源架构**设计合理，核心机制完善**，但存在**缓存层未启用、监控缺失、单一源无降级**等关键问题。

**优先修复**: P0-5（集成缓存）、P0-6（监控告警）、P0-1（注册 Netease）、P0-4（超时配置化）。

**长期目标**: 补齐备用数据源、完善测试覆盖、建立运维体系。

修复完成后，架构可达到**生产级可靠性标准**。

---

**审计完成时间**: 2026-09-01  
**下次审计建议**: 3 个月后（修复完成并稳定运行后）
