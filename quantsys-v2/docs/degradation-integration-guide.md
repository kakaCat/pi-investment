# 降级信息透明化集成指南

## 目标
让所有降级/回退/数据缺失在 API 响应中可见，提高系统可观测性。

## 集成点

### 1. 评分服务（OpportunityScoringService）

#### 1.1 初始化降级追踪器

```python
# application/services/opportunity_scoring_service.py

from application.services.scoring.degradation_tracker import DegradationTracker

def _score_single_stock(self, symbol, klines, fundamental, ...):
    # 为每只股票创建独立的降级追踪器
    degradation_tracker = DegradationTracker()
    
    # ... 评分逻辑 ...
    
    # 在返回结果中添加降级信息
    result = {
        'symbol': symbol,
        'score': total_score,
        'technical_score': tech_score,
        'fundamental_score': fund_score,
        'capital_score': capital_score,
        'score_breakdown': score_breakdown,
        'reasons': reasons,
        'applied_context': applied_context,
        # ✅ 新增：降级信息
        'degradations': degradation_tracker.get_degradations(),
        'degradation_summary': degradation_tracker.get_summary(),
        'confidence': base_confidence * degradation_tracker.get_confidence_penalty(),
    }
```

#### 1.2 记录因子计算降级

```python
def _calculate_factors(self, klines, degradation_tracker=None):
    factors = {}
    
    # 计算 RSI
    try:
        rsi14 = self.factor_adapter.calculate('rsi14', klines)
        if rsi14 is not None:
            factors['rsi'] = rsi14
        else:
            # ✅ 记录降级：RSI 计算失败
            if degradation_tracker:
                degradation_tracker.record(
                    component='technical_factors',
                    factor='rsi14',
                    reason='RSI calculation returned None (possible TA-Lib issue)',
                    fallback='excluded from technical score',
                    severity='warning'
                )
    except Exception as e:
        # ✅ 记录降级：RSI 计算异常
        if degradation_tracker:
            degradation_tracker.record(
                component='technical_factors',
                factor='rsi14',
                reason=f'RSI calculation failed: {str(e)}',
                fallback='excluded from technical score',
                severity='error'
            )
        logger.warning(f'RSI calculation failed: {e}')
    
    # 同样处理 MACD、ADX 等
    ...
```

#### 1.3 记录 K 线数据降级

```python
def _score_single_stock(self, symbol, klines, ...):
    degradation_tracker = DegradationTracker()
    
    # 检查 K 线数据质量
    report = self.quality_gate.check(symbol, klines)
    
    if report.get('needs_repair'):
        # ✅ 记录降级：K 线数据需要修复
        degradation_tracker.record(
            component='kline_data',
            reason=f"Data gap detected: {report.get('gap_info')}",
            fallback='attempted backfill',
            severity='warning',
            details={'report': report}
        )
    
    if report.get('stale'):
        # ✅ 记录降级：K 线数据过期
        degradation_tracker.record(
            component='kline_data',
            reason=f"Data is stale (last: {report.get('last_date')})",
            fallback='using outdated data',
            severity='warning',
            details={'last_date': report.get('last_date')}
        )
```

#### 1.4 记录基本面数据降级

```python
# 基本面数据缺失
if fundamental is None:
    degradation_tracker.record(
        component='fundamental_data',
        reason='No fundamental data available',
        fallback='excluded fundamental score',
        severity='error'
    )
    return None  # 或者使用默认值

# PE/ROE 缺失
if fundamental.get('pe_ratio') is None:
    degradation_tracker.record(
        component='fundamental_data',
        factor='pe_ratio',
        reason='PE ratio not available',
        fallback='excluded from fundamental score',
        severity='warning'
    )
```

### 2. TA-Lib 导入检查

#### 2.1 启动时检查（application/__init__.py）

```python
import sys
import structlog

logger = structlog.get_logger(__name__)

def check_dependencies():
    """检查关键依赖"""
    missing = []
    
    # 检查 TA-Lib
    try:
        import talib
        logger.info(f"✅ TA-Lib {talib.__version__} loaded")
    except ImportError:
        logger.error("❌ TA-Lib not installed!")
        missing.append('TA-Lib')
    
    if missing:
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        logger.error("Technical factors will fail! Please install: pip install TA-Lib")
        # 可选：严格模式下直接退出
        # sys.exit(1)
    
    return len(missing) == 0

# 在应用启动时调用
check_dependencies()
```

#### 2.2 因子计算器检查（momentum.py）

```python
# domain/factors/library/momentum.py

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    talib = None
    TALIB_AVAILABLE = False
    logger.warning("⚠️ TA-Lib not available, technical factors will be degraded")

class MomentumFactors(TechnicalFactorCalculator):
    def _calc_rsi(self, klines, period):
        if not TALIB_AVAILABLE:
            raise RuntimeError(
                "TA-Lib not available. Install with: pip install TA-Lib"
            )
        
        # ... 正常计算 ...
```

### 3. API 响应示例

#### 3.1 正常响应（无降级）

```json
{
  "success": true,
  "data": {
    "symbol": "002463",
    "name": "沪电股份",
    "score": 82,
    "technical_score": 80,
    "fundamental_score": 83,
    "capital_score": 85,
    "confidence": 0.85,
    "degradations": [],
    "degradation_summary": {
      "total": 0,
      "by_severity": {},
      "by_component": {},
      "confidence_penalty": 1.0
    }
  }
}
```

#### 3.2 部分降级响应

```json
{
  "success": true,
  "data": {
    "symbol": "688981",
    "name": "中芯国际",
    "score": 65,
    "technical_score": 70,
    "confidence": 0.7,
    "degradations": [
      {
        "component": "technical_factors",
        "factor": "rsi14",
        "reason": "RSI calculation returned None",
        "fallback": "excluded from technical score",
        "severity": "warning",
        "details": {}
      },
      {
        "component": "kline_data",
        "reason": "Data gap detected: missing 3 days",
        "fallback": "attempted backfill",
        "severity": "warning",
        "details": {"gap_days": 3}
      }
    ],
    "degradation_summary": {
      "total": 2,
      "by_severity": {"warning": 2},
      "by_component": {"technical_factors": 1, "kline_data": 1},
      "confidence_penalty": 0.8
    }
  }
}
```

#### 3.3 严重降级响应

```json
{
  "success": false,
  "error": "Unable to score stock due to critical data issues",
  "degradations": [
    {
      "component": "kline_data",
      "reason": "No kline data available",
      "fallback": "none",
      "severity": "critical"
    },
    {
      "component": "fundamental_data",
      "reason": "Stock not found in database",
      "fallback": "none",
      "severity": "critical"
    }
  ],
  "degradation_summary": {
    "total": 2,
    "by_severity": {"critical": 2},
    "confidence_penalty": 0.0
  }
}
```

## 实施计划

### Phase 1: 基础设施（已完成）
- ✅ 创建 `DegradationTracker` 类
- ✅ 定义降级记录格式

### Phase 2: 核心集成（TODO）
1. 修改 `OpportunityScoringService._score_single_stock`
   - 初始化 `degradation_tracker`
   - 传递给子方法
   - 在结果中添加降级信息

2. 修改 `OpportunityScoringService._calculate_factors`
   - 接受 `degradation_tracker` 参数
   - 记录每个因子的计算失败

3. 修改 `DataQualityGate.check`
   - 接受 `degradation_tracker` 参数
   - 记录数据质量问题

### Phase 3: 依赖检查（TODO）
1. 添加 `application/dependencies.py`
2. 在应用启动时调用 `check_dependencies()`
3. 修改因子计算器，明确抛出 TA-Lib 缺失错误

### Phase 4: API 层传递（TODO）
1. 修改 `/api/signals/scan` 路由
2. 确保降级信息传递到前端

### Phase 5: 前端展示（TODO）
1. 在机会列表显示降级警告图标
2. 点击图标显示详细降级信息
3. 低置信度的机会用不同颜色标注

## 测试检查清单

- [ ] 正常情况：无降级，`degradations` 为空数组
- [ ] TA-Lib 缺失：记录 `technical_factors` 降级
- [ ] K 线数据缺失：记录 `kline_data` 降级，severity=critical
- [ ] K 线数据过期：记录 `kline_data` 降级，severity=warning
- [ ] 基本面数据缺失：记录 `fundamental_data` 降级
- [ ] 置信度惩罚：2个 warning = -20%，1个 error = -30%
- [ ] 严重降级：返回 `success: false` 并附带降级信息

## 监控指标

### 建议添加的指标
1. **降级率**：`degraded_scores / total_scores`
2. **降级类型分布**：warning / error / critical 占比
3. **组件降级分布**：technical_factors / kline_data / fundamental_data 占比
4. **平均置信度惩罚**：降级对置信度的平均影响

### 告警规则
- 降级率 > 10%：警告
- 降级率 > 30%：错误
- critical 降级数量 > 5：立即告警
