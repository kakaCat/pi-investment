# 资金流数据本地缓存系统设计

**日期：** 2026-06-05  
**作者：** Claude Code  
**状态：** 设计阶段

## 1. 背景与问题

### 1.1 当前问题

`strategy_execute` 工具在执行策略时需要注入资金流数据，但现状是：

1. **每次都从东方财富 API 实时拉取** - 无本地持久化
2. **接口不稳定** - 超时重试机制（最多 3 次，总耗时 7 秒 + 请求超时）
3. **策略执行被阻塞** - 用户体验差，卡顿明显

**调用链：**
```
strategy_execute (TS)
  → StrategyCodeService.execute_strategy()
    → _inject_fund_flow_data()
      → SentimentService.get_stock_fund_flow()
        → FundFlowDataSource.get_stock_fund_flow()
          → EastMoneyFundFlowSource.fetch()  # 每次都调用 API
            → akshare.stock_individual_fund_flow()  # 东方财富接口
```

### 1.2 性能对比

| 场景 | 当前耗时 | 优化后 |
|------|---------|--------|
| API 成功 | 3-5 秒 | < 50ms（缓存命中） |
| API 超时重试 | 7-15 秒 | < 50ms（缓存命中） |
| 批量查询（10只） | 30-50 秒 | < 500ms（缓存命中） |

## 2. 设计目标

1. **性能提升** - 缓存命中时响应时间从秒级降至毫秒级（< 50ms）
2. **高可用** - API 故障时仍可使用缓存数据（容忍 24 小时内的旧数据）
3. **自动化** - 定时任务自动更新热门股票，无需手动维护
4. **可维护** - 单层缓存架构，逻辑清晰，易于调试
5. **渐进式** - 不破坏现有接口，向后兼容

## 3. 方案选择

**选定方案：单层缓存 + 定时任务调度器**

- 数据库持久化（PostgreSQL）
- Repository 层统一数据访问
- 优先本地查询，miss 时调用 API
- 定时任务批量更新主要指数成分股（约 1200 只）
- 保留 90 天历史数据

**不采用的方案：**
- ❌ 双层缓存（Redis + PostgreSQL）- 增加复杂度，暂无必要
- ❌ 事件驱动异步更新 - 实现复杂，首次查询可能返回空数据

## 4. 数据库设计

### 4.1 表结构

```sql
CREATE TABLE IF NOT EXISTS quant.stock_fund_flow (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,           -- 股票代码（不带后缀，如 600519）
    trade_date DATE NOT NULL,              -- 交易日期
    close_price DECIMAL(10,2),             -- 收盘价
    change_pct DECIMAL(8,4),               -- 涨跌幅(%)
    
    -- 主力资金
    main_net_inflow DECIMAL(18,2),         -- 主力净流入（万元）
    main_net_inflow_rate DECIMAL(8,4),     -- 主力净流入率(%)
    
    -- 超大单
    large_net_inflow DECIMAL(18,2),        -- 超大单净流入（万元）
    large_net_inflow_rate DECIMAL(8,4),    -- 超大单净流入率(%)
    
    -- 大单
    big_net_inflow DECIMAL(18,2),          -- 大单净流入（万元）
    big_net_inflow_rate DECIMAL(8,4),      -- 大单净流入率(%)
    
    -- 中单
    medium_net_inflow DECIMAL(18,2),       -- 中单净流入（万元）
    medium_net_inflow_rate DECIMAL(8,4),   -- 中单净流入率(%)
    
    -- 小单
    small_net_inflow DECIMAL(18,2),        -- 小单净流入（万元）
    small_net_inflow_rate DECIMAL(8,4),    -- 小单净流入率(%)
    
    -- 元数据
    source VARCHAR(50) DEFAULT 'eastmoney', -- 数据源
    created_at TIMESTAMP DEFAULT NOW(),     -- 创建时间
    updated_at TIMESTAMP DEFAULT NOW(),     -- 更新时间
    
    UNIQUE(symbol, trade_date)              -- 防止重复
);

-- 索引优化
CREATE INDEX idx_fund_flow_symbol_date ON quant.stock_fund_flow(symbol, trade_date DESC);
CREATE INDEX idx_fund_flow_updated_at ON quant.stock_fund_flow(updated_at);
CREATE INDEX idx_fund_flow_trade_date ON quant.stock_fund_flow(trade_date DESC);
```

### 4.2 数据量估算

- **90 天 × 1200 股票 = 108,000 行**
- 每行约 150 字节
- **总数据量：约 15-20 MB**

### 4.3 迁移文件

**文件：** `quantsys-v2/migrations/add_stock_fund_flow_table.sql`

## 5. Repository 层设计

### 5.1 接口定义

**文件：** `quantsys-v2/repositories/fund_flow_repository.py`

```python
from typing import List, Dict
from infrastructure.database.base_repository import BaseRepository

class FundFlowRepository(BaseRepository):
    """资金流数据 Repository"""
    
    def get_fund_flow(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str
    ) -> List[Dict]:
        """
        查询资金流数据（按日期升序）
        
        Args:
            symbol: 股票代码（不带后缀，如 600519）
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            
        Returns:
            资金流记录列表，每条记录包含所有字段
        """
        
    def get_latest_fund_flow(
        self, 
        symbol: str, 
        days: int = 5
    ) -> List[Dict]:
        """
        查询最近 N 天资金流数据
        
        Args:
            symbol: 股票代码（不带后缀）
            days: 天数
            
        Returns:
            最近 N 天资金流记录（按日期降序）
        """
        
    def batch_upsert(
        self, 
        records: List[Dict]
    ) -> int:
        """
        批量插入或更新资金流数据
        
        Args:
            records: 资金流记录列表，每条记录必须包含：
                     - symbol (str)
                     - trade_date (str, YYYY-MM-DD)
                     - main_net_inflow (float)
                     - 其他字段（可选）
            
        Returns:
            影响行数
            
        Note:
            使用 INSERT ... ON CONFLICT (symbol, trade_date) DO UPDATE
            实现 upsert 语义，自动更新 updated_at 字段
        """
        
    def get_stale_symbols(
        self, 
        threshold_hours: int = 24
    ) -> List[str]:
        """
        查询数据过期的股票列表
        
        Args:
            threshold_hours: 过期阈值（小时）
            
        Returns:
            需要更新的股票代码列表
            
        Logic:
            SELECT DISTINCT symbol FROM quant.stock_fund_flow
            WHERE updated_at < NOW() - INTERVAL '{threshold_hours} hours'
        """
        
    def delete_old_data(
        self, 
        retention_days: int = 90
    ) -> int:
        """
        删除超过保留期的历史数据
        
        Args:
            retention_days: 保留天数
            
        Returns:
            删除行数
            
        Logic:
            DELETE FROM quant.stock_fund_flow
            WHERE trade_date < NOW() - INTERVAL '{retention_days} days'
        """
```

### 5.2 设计要点

- 继承 `BaseRepository` 复用数据库连接和错误处理
- 所有日期参数统一使用 `YYYY-MM-DD` 格式
- `batch_upsert` 使用 PostgreSQL upsert 语法，避免重复数据
- `symbol` 参数统一不带后缀（与 kline_repository 保持一致）

## 6. 数据源层改造

### 6.1 改造策略

**文件：** `quantsys-v2/data_sources/fund_flow_source.py`

**核心改动：**

```python
class FundFlowDataSource:
    """资金流向数据源 - 优先本地缓存，miss 时调用 API"""
    
    def __init__(self):
        self.repository = FundFlowRepository()  # 新增
        self.api_sources = [
            EastMoneyFundFlowSource(),
            AkShareFundFlowSource(),
        ]
        self.cache_ttl_hours = 24  # 缓存有效期（小时）
    
    def get_stock_fund_flow(self, symbol: str, days: int = 5) -> Dict:
        """
        获取个股资金流向（优先本地缓存）
        
        数据流：
        1. 查询本地数据库最近 N 天数据
        2. 检查缓存是否完整且新鲜（updated_at < 24小时）
        3. 有效 → 返回缓存数据
        4. 无效 → 调用 API → 写入数据库 → 返回
        
        Args:
            symbol: 股票代码（支持带/不带后缀）
            days: 查询天数
            
        Returns:
            {
                'symbol': str,
                'days': int,
                'data': [资金流记录列表],
                'summary': {汇总统计},
                'source': 'cache' | 'api' | 'stale_cache',
                'timestamp': str
            }
        """
        # 1. 标准化股票代码（去除后缀）
        clean_symbol = symbol.split('.')[0]
        
        # 2. 查询本地缓存
        cached_data = self.repository.get_latest_fund_flow(clean_symbol, days)
        
        # 3. 检查缓存是否完整且新鲜
        if self._is_cache_valid(cached_data, days):
            logger.info(f"命中本地缓存: {symbol}")
            return self._format_response(cached_data, clean_symbol, 'cache')
        
        # 4. 缓存 miss，调用 API
        logger.info(f"缓存 miss，调用 API: {symbol}")
        try:
            api_data = self._fetch_from_api(clean_symbol, days)
            
            # 5. 写入数据库
            if api_data:
                self.repository.batch_upsert(api_data)
            
            # 6. 返回格式化结果
            return self._format_response(api_data, clean_symbol, 'api')
            
        except Exception as e:
            # API 失败，降级使用旧缓存（如果存在）
            logger.warning(f"API 调用失败，尝试使用旧缓存: {e}")
            fallback_data = self.repository.get_latest_fund_flow(clean_symbol, days=30)
            if fallback_data:
                logger.info(f"使用旧缓存数据: {symbol}")
                return self._format_response(fallback_data, clean_symbol, 'stale_cache')
            raise
    
    def _is_cache_valid(self, cached_data: List[Dict], days: int) -> bool:
        """
        判断缓存是否有效
        
        条件：
        1. 数据条数 >= max(1, days - 3)（考虑周末节假日）
        2. 最新数据的 updated_at < 24 小时
        
        Args:
            cached_data: 缓存数据列表
            days: 期望天数
            
        Returns:
            True = 缓存有效，False = 需要更新
        """
        if not cached_data:
            return False
        
        # 检查数据量（容忍周末节假日缺失）
        min_expected = max(1, days - 3)
        if len(cached_data) < min_expected:
            return False
        
        # 检查最新数据的更新时间
        latest = cached_data[0]  # 降序排列，第一条是最新
        updated_at = latest.get('updated_at')
        if not updated_at:
            return False
        
        from datetime import datetime, timedelta
        age_hours = (datetime.now() - updated_at).total_seconds() / 3600
        
        return age_hours < self.cache_ttl_hours
    
    def _fetch_from_api(self, symbol: str, days: int) -> List[Dict]:
        """
        从 API 获取数据（保持现有多数据源 failover 逻辑）
        
        【保持现有实现不变】
        遍历 self.api_sources，依次尝试，直到成功
        """
        # 现有代码逻辑保持不变
        pass
    
    def _format_response(
        self, 
        data: List[Dict], 
        symbol: str, 
        source: str
    ) -> Dict:
        """
        格式化为标准响应格式
        
        【新增】统一缓存数据和 API 数据的输出格式
        """
        summary = self._calculate_summary(data)
        
        return {
            'symbol': symbol,
            'days': len(data),
            'data': data,
            'summary': summary,
            'source': source,
            'timestamp': datetime.now().isoformat()
        }
```

### 6.2 关键改动总结

1. **新增 `FundFlowRepository` 依赖**
2. **`get_stock_fund_flow()` 添加缓存查询逻辑**
3. **保持现有 API failover 机制不变**（EastMoney → AkShare）
4. **新增容错机制**：API 失败时降级使用旧缓存
5. **缓存判断考虑交易日因素**（周末节假日没有数据）

## 7. 定时任务设计

### 7.1 任务逻辑

**文件：** `quantsys-v2/runtime/jobs/update_fund_flow_job.py`

```python
import time
import logging
from typing import List, Dict
from data_sources.fund_flow_source import FundFlowDataSource
from services.stock_pool_service import StockPoolService

logger = logging.getLogger(__name__)

class UpdateFundFlowJob:
    """资金流数据定时更新任务"""
    
    def __init__(self):
        self.fund_flow_source = FundFlowDataSource()
        self.stock_pool_service = StockPoolService()
        self.batch_size = 50  # 每批处理股票数
        self.delay_between_batches = 2  # 批次间延迟（秒），避免 API 限流
    
    def execute(self) -> Dict:
        """
        执行定时更新
        
        流程：
        1. 获取主要指数成分股列表（沪深300 + 中证500 + 中证1000）
        2. 分批更新（每批 50 只，避免 API 限流）
        3. 更新完成后清理过期数据（> 90天）
        4. 记录更新统计（成功/失败/耗时）
        
        Returns:
            {
                'total': 总股票数,
                'success': 成功数,
                'failed': [失败股票列表],
                'deleted': 清理的过期记录数,
                'elapsed': 耗时（秒）
            }
        """
        logger.info("开始定时更新资金流数据")
        start_time = time.time()
        
        # 1. 获取股票池
        symbols = self._get_target_symbols()
        logger.info(f"待更新股票数: {len(symbols)}")
        
        # 2. 分批更新
        success_count = 0
        failed_symbols = []
        
        for i in range(0, len(symbols), self.batch_size):
            batch = symbols[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (len(symbols) + self.batch_size - 1) // self.batch_size
            
            logger.info(f"处理批次 {batch_num}/{total_batches}，股票数: {len(batch)}")
            
            for symbol in batch:
                try:
                    # 调用 API 并写入数据库（通过 FundFlowDataSource）
                    self.fund_flow_source.get_stock_fund_flow(symbol, days=5)
                    success_count += 1
                except Exception as e:
                    logger.error(f"更新失败: {symbol} - {e}")
                    failed_symbols.append(symbol)
            
            # 批次间延迟，避免 API 限流
            if i + self.batch_size < len(symbols):
                time.sleep(self.delay_between_batches)
        
        # 3. 清理过期数据（保留 90 天）
        deleted = self.fund_flow_source.repository.delete_old_data(retention_days=90)
        
        # 4. 记录统计
        elapsed = time.time() - start_time
        logger.info(
            f"资金流更新完成: 成功 {success_count}/{len(symbols)}, "
            f"失败 {len(failed_symbols)}, 清理 {deleted} 条过期记录, "
            f"耗时 {elapsed:.1f}秒"
        )
        
        if failed_symbols:
            logger.warning(f"失败股票列表: {', '.join(failed_symbols[:10])}{'...' if len(failed_symbols) > 10 else ''}")
        
        return {
            'total': len(symbols),
            'success': success_count,
            'failed': failed_symbols,
            'deleted': deleted,
            'elapsed': elapsed
        }
    
    def _get_target_symbols(self) -> List[str]:
        """
        获取目标股票池（约 1200 只）
        
        来源：
        - 沪深300 成分股
        - 中证500 成分股
        - 中证1000 成分股
        
        实现方式：
        1. 优先使用 akshare 获取最新指数成分股
        2. 失败时回退到项目现有 StockPoolService
        
        Returns:
            股票代码列表（不带后缀）
        """
        try:
            import akshare as ak
            
            # 获取沪深300成分股
            hs300 = ak.index_stock_cons(symbol="000300")
            symbols_hs300 = hs300['品种代码'].tolist() if not hs300.empty else []
            
            # 获取中证500成分股
            zz500 = ak.index_stock_cons(symbol="000905")
            symbols_zz500 = zz500['品种代码'].tolist() if not zz500.empty else []
            
            # 获取中证1000成分股
            zz1000 = ak.index_stock_cons(symbol="000852")
            symbols_zz1000 = zz1000['品种代码'].tolist() if not zz1000.empty else []
            
            # 合并去重
            all_symbols = list(set(symbols_hs300 + symbols_zz500 + symbols_zz1000))
            
            logger.info(f"获取指数成分股: 沪深300={len(symbols_hs300)}, 中证500={len(symbols_zz500)}, 中证1000={len(symbols_zz1000)}, 合并后={len(all_symbols)}")
            
            return all_symbols
            
        except Exception as e:
            logger.warning(f"获取指数成分股失败，使用默认股票池: {e}")
            
            # 回退方案：使用 StockPoolService 的热门股票池
            pool_symbols = self.stock_pool_service.get_hot_stock_pool()
            return [s.split('.')[0] for s in pool_symbols]  # 去除后缀
```

### 7.2 调度配置

**文件：** `quantsys-v2/runtime/scheduler/jobs_config.yaml`（或通过代码注册）

```yaml
fund_flow_update:
  job_class: "runtime.jobs.update_fund_flow_job.UpdateFundFlowJob"
  trigger: "cron"
  cron: "30 21 * * *"  # 每天 21:30 执行（A股收盘后，数据已更新）
  enabled: true
  description: "更新主要指数成分股的资金流数据"
  max_instances: 1  # 防止并发执行
  coalesce: true    # 如果错过执行时间，只执行一次
```

### 7.3 性能估算

- **股票数量：** 约 1200 只
- **批次数量：** 1200 ÷ 50 = 24 批
- **单次 API 调用：** 约 1-2 秒
- **每批耗时：** 50 × 1.5秒 = 75 秒
- **批次间延迟：** 2 秒 × 24 = 48 秒
- **总耗时：** 约 **18-22 分钟**

### 7.4 监控和告警

建议添加以下监控指标：

1. **成功率监控** - 失败率 > 10% 发送告警
2. **耗时监控** - 超过 30 分钟发送告警
3. **数据量监控** - 更新后数据量 < 50,000 条发送告警
4. **失败重试** - 失败股票列表记录到日志，可手动重试

## 8. 服务层集成

### 8.1 透明集成

**关键点：** 现有服务层**无需修改**，自动享受缓存加速。

**文件：** `quantsys-v2/services/sentiment_service.py`

```python
class SentimentService:
    """市场情绪服务"""
    
    def __init__(self, fund_flow_source):
        """
        初始化情绪服务
        
        Args:
            fund_flow_source: 资金流向数据源（已改造为缓存版本）
        """
        self.fund_flow_source = fund_flow_source
    
    def get_stock_fund_flow(self, symbol: str, days: int = 5) -> Dict:
        """
        获取个股资金流向并生成分析
        
        【无需修改】
        底层 FundFlowDataSource 已改造为优先本地缓存，
        此方法透明享受缓存加速
        
        性能提升：
        - 缓存命中：< 50ms（数据库查询）
        - 缓存 miss：3-5秒（API 调用 + 写入）
        - 整体命中率预期：> 90%（定时任务覆盖热门股票）
        """
        try:
            # 获取原始数据（自动走缓存）
            flow_data = self.fund_flow_source.get_stock_fund_flow(symbol, days)
            
            # 生成分析（保持不变）
            analysis = self._analyze_fund_flow(flow_data)
            signals = self._generate_signals(flow_data, analysis)
            
            return {
                **flow_data,
                'analysis': analysis,
                'signals': signals,
            }
        except Exception as e:
            logger.error(f"获取 {symbol} 资金流向失败: {e}", exc_info=True)
            return {'error': str(e)}
```

### 8.2 影响范围

**受益模块：**
1. `StrategyCodeService._inject_fund_flow_data()` - 策略执行时注入资金流数据
2. `SentimentService.get_stock_fund_flow()` - 市场情绪分析
3. API 端点 `/api/sentiment/stock/{symbol}/fund-flow`

**无需修改：**
- 所有调用方保持不变
- 依赖注入保持不变
- 接口签名保持不变

## 9. 错误处理和容错

### 9.1 容错策略

#### 1. API 调用失败 → 降级使用旧缓存

```python
try:
    api_data = self._fetch_from_api(symbol, days)
except Exception as e:
    logger.warning(f"API 调用失败，尝试使用旧缓存: {e}")
    # 放宽查询范围，查询最近 30 天数据
    fallback_data = self.repository.get_latest_fund_flow(symbol, days=30)
    if fallback_data:
        logger.info(f"使用旧缓存数据: {symbol}")
        return self._format_response(fallback_data, symbol, 'stale_cache')
    raise  # 无缓存可用，向上抛出异常
```

**适用场景：**
- 东方财富接口限流/超时
- 网络故障
- 旧数据（2-3 天前）比完全失败更好

#### 2. 数据库查询失败 → 降级为纯 API 模式

```python
try:
    cached_data = self.repository.get_latest_fund_flow(symbol, days)
except Exception as e:
    logger.error(f"数据库查询失败，降级为纯 API 模式: {e}")
    # 直接调用 API，不写缓存
    return self._fetch_from_api_direct(symbol, days)
```

**适用场景：**
- 数据库连接故障
- 表损坏
- 保证服务可用性

#### 3. 定时任务批量容错

```python
for symbol in batch:
    try:
        self.fund_flow_source.get_stock_fund_flow(symbol, days=5)
        success_count += 1
    except Exception as e:
        logger.error(f"更新失败: {symbol} - {e}")
        failed_symbols.append(symbol)
        # 继续处理下一个股票，不中断批次
```

**适用场景：**
- 单个股票 API 调用失败
- 数据格式异常
- 网络抖动

#### 4. 数据完整性校验

```python
def _validate_record(self, record: Dict) -> bool:
    """验证资金流记录的完整性"""
    required_fields = ['symbol', 'trade_date', 'main_net_inflow']
    
    for field in required_fields:
        if field not in record or record[field] is None:
            logger.warning(f"记录缺少必填字段: {field}")
            return False
    
    # 验证数值合理性
    if not isinstance(record['main_net_inflow'], (int, float)):
        logger.warning(f"main_net_inflow 类型错误: {type(record['main_net_inflow'])}")
        return False
    
    return True

# 在 batch_upsert 中使用
valid_records = [r for r in records if self._validate_record(r)]
if len(valid_records) < len(records):
    logger.warning(f"过滤了 {len(records) - len(valid_records)} 条无效记录")
```

### 9.2 日志记录

**关键日志点：**
1. 缓存命中/miss - INFO 级别
2. API 调用失败 - WARNING 级别
3. 降级使用旧缓存 - WARNING 级别
4. 数据库操作失败 - ERROR 级别
5. 定时任务统计 - INFO 级别

## 10. 测试策略

### 10.1 单元测试

**测试文件：** `quantsys-v2/tests/repositories/test_fund_flow_repository.py`

```python
def test_get_fund_flow_returns_data_in_date_range()
def test_get_fund_flow_empty_when_no_data()
def test_get_latest_fund_flow_returns_recent_data()
def test_get_latest_fund_flow_respects_days_limit()
def test_batch_upsert_inserts_new_records()
def test_batch_upsert_updates_existing_records()
def test_batch_upsert_updates_timestamp()
def test_get_stale_symbols_returns_outdated_stocks()
def test_get_stale_symbols_excludes_fresh_stocks()
def test_delete_old_data_removes_expired_records()
def test_delete_old_data_preserves_recent_records()
```

**测试文件：** `quantsys-v2/tests/data_sources/test_fund_flow_source.py`

```python
def test_cache_hit_returns_local_data()
def test_cache_miss_calls_api_and_saves()
def test_cache_invalid_when_data_stale()
def test_cache_invalid_when_insufficient_records()
def test_api_failure_fallback_to_stale_cache()
def test_api_failure_raises_when_no_cache()
def test_database_failure_fallback_to_api()
def test_symbol_normalization_removes_suffix()
def test_format_response_includes_summary()
```

**测试文件：** `quantsys-v2/tests/runtime/jobs/test_update_fund_flow_job.py`

```python
def test_job_updates_target_symbols()
def test_job_handles_single_stock_failure()
def test_job_handles_batch_failures()
def test_job_cleans_old_data()
def test_job_returns_statistics()
def test_job_respects_batch_size()
def test_get_target_symbols_fallback()
```

### 10.2 集成测试

**测试文件：** `quantsys-v2/tests/integration/test_fund_flow_caching.py`

```python
def test_end_to_end_caching():
    """
    端到端测试缓存流程
    
    步骤：
    1. 清空测试数据
    2. 首次查询 → 触发 API 调用 → 写入数据库
    3. 验证数据库中存在记录
    4. 再次查询 → 命中缓存 → 验证 source='cache'
    5. 验证性能提升（< 100ms vs 3-5s）
    """

def test_stale_cache_fallback():
    """
    测试 API 失败时降级使用旧缓存
    
    步骤：
    1. 插入 3 天前的数据到数据库
    2. Mock API 调用抛出异常
    3. 查询股票资金流
    4. 验证返回旧缓存数据，source='stale_cache'
    """

def test_scheduled_job_integration():
    """
    测试定时任务完整流程
    
    步骤：
    1. 执行 UpdateFundFlowJob
    2. 验证数据库中数据量增加
    3. 验证过期数据被清理
    4. 验证返回统计信息正确
    """
```

### 10.3 性能测试

**测试文件：** `quantsys-v2/tests/performance/test_fund_flow_performance.py`

```python
def test_cache_hit_performance():
    """
    缓存命中性能测试
    
    预期：< 100ms（数据库查询 + 格式化）
    """
    import time
    
    # 预先插入数据
    repository.batch_upsert([...])
    
    # 测试查询性能
    start = time.time()
    result = fund_flow_source.get_stock_fund_flow('600519', days=5)
    elapsed = time.time() - start
    
    assert elapsed < 0.1  # 100ms
    assert result['source'] == 'cache'

def test_batch_update_performance():
    """
    批量更新性能测试
    
    预期：50 只股票 < 60 秒
    """
    symbols = ['600519', '000858', ...]  # 50 只
    
    start = time.time()
    for symbol in symbols:
        fund_flow_source.get_stock_fund_flow(symbol, days=5)
    elapsed = time.time() - start
    
    assert elapsed < 60

def test_database_query_performance():
    """
    数据库查询性能测试
    
    预期：单次查询 < 50ms
    """
    # 插入 10,000 条数据
    # 测试查询性能
```

### 10.4 测试覆盖率目标

- Repository 层：> 90%
- 数据源层：> 85%
- 定时任务：> 80%
- 整体：> 85%

## 11. 实施计划

### 11.1 阶段划分

**Phase 1: 基础设施（2-3 天）**
- 创建数据库表和迁移脚本
- 实现 FundFlowRepository
- 编写 Repository 单元测试

**Phase 2: 数据源改造（2-3 天）**
- 修改 FundFlowDataSource 添加缓存逻辑
- 实现缓存判断和容错机制
- 编写数据源层测试

**Phase 3: 定时任务（1-2 天）**
- 实现 UpdateFundFlowJob
- 配置调度器
- 编写任务测试

**Phase 4: 集成测试和优化（1-2 天）**
- 端到端集成测试
- 性能测试和调优
- 文档更新

**总耗时：约 6-10 天**

### 11.2 上线计划

1. **灰度发布**
   - 先在测试环境运行 1 周
   - 验证缓存命中率和性能提升
   - 验证定时任务稳定性

2. **生产部署**
   - 执行数据库迁移脚本
   - 部署新代码
   - 启动定时任务
   - 监控首次批量更新

3. **监控指标**
   - 缓存命中率（目标 > 90%）
   - 平均响应时间（目标 < 100ms）
   - 定时任务成功率（目标 > 95%）
   - 数据库容量增长

### 11.3 回滚方案

如果出现严重问题，可快速回滚：

1. **代码回滚** - 回退到旧版本 FundFlowDataSource（纯 API 模式）
2. **保留数据库表** - 不删除表，保留已缓存数据
3. **暂停定时任务** - 禁用 cron job
4. **修复后重新部署**

## 12. 预期收益

### 12.1 性能提升

| 指标 | 当前 | 优化后 | 提升 |
|------|------|--------|------|
| 单次查询（缓存命中） | 3-5 秒 | < 50ms | **100x** |
| 单次查询（缓存 miss） | 3-5 秒 | 3-5 秒 | 无变化 |
| 批量查询（10只） | 30-50 秒 | < 500ms | **60-100x** |
| 策略执行耗时 | +3-5 秒 | +50ms | **60-100x** |

### 12.2 可用性提升

- **API 故障容忍** - 即使东方财富接口不可用，仍可使用缓存数据
- **降低 API 依赖** - 减少对第三方接口的依赖，提升系统稳定性
- **缓存命中率预期** - > 90%（定时任务覆盖热门股票）

### 12.3 用户体验提升

- **策略执行不再卡顿** - 从秒级等待降至几乎无感知
- **支持高频查询** - 不再担心 API 限流
- **数据更新及时** - 定时任务保证热门股票数据新鲜

## 13. 风险和限制

### 13.1 风险

1. **定时任务失败** - 可能导致缓存数据过期
   - 缓解：失败时降级使用旧缓存
   - 监控：任务失败率告警

2. **数据库容量增长** - 长期运行数据量可能超预期
   - 缓解：90 天自动清理机制
   - 监控：数据库容量告警

3. **API 限流** - 批量更新可能触发东方财富限流
   - 缓解：批次间延迟 2 秒
   - 降级：失败时记录日志，下次重试

### 13.2 限制

1. **冷门股票首次查询慢** - 不在定时任务覆盖范围的股票首次查询仍需调用 API
2. **数据实时性** - 缓存数据最多延迟 24 小时（可接受）
3. **依赖调度器** - 定时任务依赖 scheduler 服务正常运行

## 14. 后续优化方向

1. **增量更新** - 只更新最近有交易的股票，减少 API 调用
2. **Redis 二级缓存** - 热点股票（如茅台）加 Redis 缓存，进一步提升性能
3. **缓存预热** - 系统启动时预加载热门股票数据
4. **动态股票池** - 基于查询频率动态调整定时任务覆盖范围
5. **WebSocket 实时推送** - 对于活跃股票，接入实时推送减少轮询

## 15. 总结

本设计方案通过**单层数据库缓存 + 定时任务**的架构，实现了资金流数据的本地持久化，解决了策略执行时 API 调用卡顿的问题。

**核心优势：**
- ✅ 性能提升 100 倍（缓存命中时）
- ✅ 高可用（API 故障时可用缓存）
- ✅ 架构简单，易于维护
- ✅ 向后兼容，无需修改调用方
- ✅ 渐进式实施，风险可控

**实施周期：** 6-10 天  
**预期命中率：** > 90%  
**预期响应时间：** < 50ms（缓存命中）

