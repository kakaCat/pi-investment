# 策略系统统一实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一策略执行系统，将 `strategy_execute` 工具和 `signal.generate` 命令合并到 `quant_cli` 的 `strategy.execute` 命令，支持单股分析、批量生成、完整流程三种模式。

**Architecture:** 三层架构 - quant_cli 工具（参数验证、格式化）→ QuantV2Client（HTTP 客户端）→ quantsys-v2 Flask API（策略执行、持久化）。使用 Action 驱动接口（single/batch/pipeline），默认持久化到数据库，批量模式支持 NDJSON 流式响应。

**Tech Stack:** TypeScript (Node.js), Python (Flask), PostgreSQL, @sinclair/typebox

---

## 文件结构规划

### 后端（Python）
- **Create**: `quantsys-v2/api/routes/strategy_execution.py` - 策略执行路由
- **Create**: `quantsys-v2/services/strategy_execution_service.py` - 策略执行业务逻辑
- **Create**: `quantsys-v2/tests/api/test_strategy_execution_routes.py` - API 路由测试
- **Create**: `quantsys-v2/tests/services/test_strategy_execution_service.py` - 服务层测试
- **Modify**: `quantsys-v2/api/server.py` - 注册新路由

### 前端（TypeScript）
- **Modify**: `src/infrastructure/quant/types.ts` - 添加类型定义
- **Modify**: `src/infrastructure/quant/quant-v2-client.ts` - 添加客户端方法
- **Modify**: `src/infrastructure/quant/formatters.ts` - 添加格式化函数
- **Modify**: `src/infrastructure/tools/core/quant-cli-tool.ts` - 添加 strategy.execute 命令
- **Create**: `src/infrastructure/tools/core/quant-cli-tool-strategy-execute.test.ts` - 命令测试
- **Modify**: `src/infrastructure/tools/index.ts` - 移除 strategyExecuteTool
- **Modify**: `CLAUDE.md` - 更新文档

---

## Phase 1: 后端 API 实现

### Task 1: 类型定义和数据模型

**Files:**
- Create: `quantsys-v2/models/strategy_execution.py`
- Create: `quantsys-v2/tests/models/test_strategy_execution.py`

- [ ] **Step 1: 写失败测试 - 验证请求模型**

```python
# quantsys-v2/tests/models/test_strategy_execution.py
import pytest
from models.strategy_execution import (
    StrategyExecuteRequest,
    StrategyBatchExecuteRequest,
    StrategyPipelineExecuteRequest
)

def test_strategy_execute_request_validation():
    """测试单股执行请求验证"""
    # 有效请求
    req = StrategyExecuteRequest(
        symbol="600519.SH",
        strategy_name="Turtle",
        persist=True
    )
    assert req.symbol == "600519.SH"
    assert req.strategy_name == "Turtle"
    assert req.persist is True
    
    # 缺少必需字段
    with pytest.raises(ValueError):
        StrategyExecuteRequest(symbol="600519.SH")

def test_batch_execute_request_validation():
    """测试批量执行请求验证"""
    req = StrategyBatchExecuteRequest(
        symbols=["600519.SH", "000001.SZ"],
        strategy_name="Turtle",
        min_confidence=0.6
    )
    assert len(req.symbols) == 2
    assert req.min_confidence == 0.6
    
    # 空列表
    with pytest.raises(ValueError):
        StrategyBatchExecuteRequest(symbols=[], strategy_name="Turtle")
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd quantsys-v2
python -m pytest tests/models/test_strategy_execution.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'models.strategy_execution'"

- [ ] **Step 3: 实现数据模型**

```python
# quantsys-v2/models/strategy_execution.py
from typing import Optional, List
from pydantic import BaseModel, Field, validator

class StrategyExecuteRequest(BaseModel):
    """单股策略执行请求"""
    symbol: str = Field(..., description="股票代码")
    strategy_name: str = Field(..., description="策略名称")
    date: Optional[str] = Field(None, description="执行日期 YYYY-MM-DD")
    persist: bool = Field(True, description="是否持久化")
    return_details: bool = Field(True, description="是否返回详细指标")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not v or not v.strip():
            raise ValueError("symbol cannot be empty")
        return v.strip()
    
    @validator('strategy_name')
    def validate_strategy_name(cls, v):
        if not v or not v.strip():
            raise ValueError("strategy_name cannot be empty")
        return v.strip()

class StrategyBatchExecuteRequest(BaseModel):
    """批量策略执行请求"""
    symbols: List[str] = Field(..., description="股票代码列表")
    strategy_name: str = Field(..., description="策略名称")
    date: Optional[str] = Field(None, description="执行日期")
    persist: bool = Field(True, description="是否持久化")
    min_confidence: Optional[float] = Field(None, ge=0, le=1, description="最低置信度")
    
    @validator('symbols')
    def validate_symbols(cls, v):
        if not v or len(v) == 0:
            raise ValueError("symbols cannot be empty")
        return [s.strip() for s in v if s.strip()]

class StrategyPipelineExecuteRequest(BaseModel):
    """完整流程执行请求"""
    symbols: List[str] = Field(..., description="股票代码列表")
    strategy_name: str = Field(..., description="策略名称")
    create_orders: bool = Field(False, description="是否创建订单")
    risk_check: bool = Field(True, description="是否风控检查")
    
    @validator('symbols')
    def validate_symbols(cls, v):
        if not v or len(v) == 0:
            raise ValueError("symbols cannot be empty")
        return [s.strip() for s in v if s.strip()]

class StrategySignalResponse(BaseModel):
    """策略信号响应"""
    signal_id: Optional[str] = None
    symbol: str
    signal_type: str  # BUY/SELL/HOLD
    confidence: float
    entry_price: float
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    position_size: Optional[float] = None
    indicators: Optional[dict] = None

class PipelineExecutionResponse(BaseModel):
    """流程执行响应"""
    execution_date: str
    duration_ms: int
    signals_generated: int
    signals_approved: int
    signals_rejected: int
    orders_created: int
    rejection_reasons: dict
    orders: List[dict]
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd quantsys-v2
python -m pytest tests/models/test_strategy_execution.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: 提交**

```bash
git add quantsys-v2/models/strategy_execution.py quantsys-v2/tests/models/test_strategy_execution.py
git commit -m "feat(models): add strategy execution request/response models"
```

### Task 2: 策略执行服务层

**Files:**
- Create: `quantsys-v2/services/strategy_execution_service.py`
- Create: `quantsys-v2/tests/services/test_strategy_execution_service.py`

- [ ] **Step 1: 写失败测试 - 单股执行**

```python
# quantsys-v2/tests/services/test_strategy_execution_service.py
import pytest
from unittest.mock import Mock, patch
from services.strategy_execution_service import StrategyExecutionService
from models.strategy_execution import StrategyExecuteRequest

@pytest.fixture
def service():
    return StrategyExecutionService()

@pytest.fixture
def mock_strategy_engine():
    with patch('services.strategy_execution_service.StrategyEngine') as mock:
        yield mock

def test_execute_single_strategy(service, mock_strategy_engine):
    """测试单股策略执行"""
    # Mock 策略引擎返回
    mock_engine = Mock()
    mock_engine.execute.return_value = {
        'symbol': '600519.SH',
        'signal_type': 'BUY',
        'confidence': 0.85,
        'entry_price': 1850.0,
        'stop_loss': 1750.0,
        'target_price': 2050.0
    }
    mock_strategy_engine.return_value = mock_engine
    
    request = StrategyExecuteRequest(
        symbol="600519.SH",
        strategy_name="Turtle",
        persist=True
    )
    
    result = service.execute_single(request)
    
    assert result['symbol'] == '600519.SH'
    assert result['signal_type'] == 'BUY'
    assert result['confidence'] == 0.85
    assert 'signal_id' in result  # 持久化后应有 signal_id

def test_execute_single_without_persist(service, mock_strategy_engine):
    """测试不持久化的单股执行"""
    mock_engine = Mock()
    mock_engine.execute.return_value = {
        'symbol': '600519.SH',
        'signal_type': 'HOLD',
        'confidence': 0.55
    }
    mock_strategy_engine.return_value = mock_engine
    
    request = StrategyExecuteRequest(
        symbol="600519.SH",
        strategy_name="Turtle",
        persist=False
    )
    
    result = service.execute_single(request)
    
    assert 'signal_id' not in result  # 不持久化不应有 signal_id
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd quantsys-v2
python -m pytest tests/services/test_strategy_execution_service.py::test_execute_single_strategy -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'services.strategy_execution_service'"

- [ ] **Step 3: 实现服务层 - 单股执行**

```python
# quantsys-v2/services/strategy_execution_service.py
import time
import uuid
from datetime import datetime
from typing import Dict, List, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed

from models.strategy_execution import (
    StrategyExecuteRequest,
    StrategyBatchExecuteRequest,
    StrategyPipelineExecuteRequest
)
from services.strategy_engine import StrategyEngine
from repositories.signal_test_log_repository import SignalTestLogRepository
from repositories.order_repository import OrderRepository
from services.risk_manager import RiskManager

class StrategyExecutionService:
    def __init__(self):
        self.signal_repo = SignalTestLogRepository()
        self.order_repo = OrderRepository()
        self.risk_manager = RiskManager()
    
    def execute_single(self, request: StrategyExecuteRequest) -> Dict:
        """执行单股策略"""
        # 初始化策略引擎
        engine = StrategyEngine(request.strategy_name)
        
        # 执行策略
        signal = engine.execute(
            symbol=request.symbol,
            date=request.date
        )
        
        # 持久化
        if request.persist:
            signal_id = self._generate_signal_id(
                request.symbol,
                request.strategy_name,
                request.date or datetime.now().strftime('%Y-%m-%d')
            )
            
            self.signal_repo.create({
                'signal_id': signal_id,
                'symbol': request.symbol,
                'strategy_name': request.strategy_name,
                'signal_type': signal['signal_type'],
                'confidence': signal['confidence'],
                'entry_price': signal.get('entry_price'),
                'stop_loss': signal.get('stop_loss'),
                'target_price': signal.get('target_price'),
                'status': 'pending',
                'created_at': datetime.now()
            })
            
            signal['signal_id'] = signal_id
        
        return signal
    
    def _generate_signal_id(self, symbol: str, strategy: str, date: str) -> str:
        """生成信号ID"""
        short_uuid = str(uuid.uuid4())[:8]
        return f"sig_{date.replace('-', '')}_{symbol.replace('.', '_')}_{strategy.lower()}_{short_uuid}"
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd quantsys-v2
python -m pytest tests/services/test_strategy_execution_service.py::test_execute_single_strategy -v
python -m pytest tests/services/test_strategy_execution_service.py::test_execute_single_without_persist -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: 提交**

```bash
git add quantsys-v2/services/strategy_execution_service.py quantsys-v2/tests/services/test_strategy_execution_service.py
git commit -m "feat(services): add strategy execution service - single mode"
```

### Task 3: 批量执行和流式响应

**Files:**
- Modify: `quantsys-v2/services/strategy_execution_service.py`
- Modify: `quantsys-v2/tests/services/test_strategy_execution_service.py`

- [ ] **Step 1: 写失败测试 - 批量执行**

```python
# quantsys-v2/tests/services/test_strategy_execution_service.py (追加)

def test_execute_batch_strategies(service, mock_strategy_engine):
    """测试批量策略执行"""
    mock_engine = Mock()
    mock_engine.execute.side_effect = [
        {'symbol': '600519.SH', 'signal_type': 'BUY', 'confidence': 0.85},
        {'symbol': '000001.SZ', 'signal_type': 'HOLD', 'confidence': 0.55}
    ]
    mock_strategy_engine.return_value = mock_engine
    
    request = StrategyBatchExecuteRequest(
        symbols=["600519.SH", "000001.SZ"],
        strategy_name="Turtle",
        persist=True
    )
    
    results = list(service.execute_batch(request))
    
    # 应该返回 2 个信号 + 1 个摘要
    assert len(results) == 3
    assert results[0]['type'] == 'signal'
    assert results[1]['type'] == 'signal'
    assert results[2]['type'] == 'summary'
    assert results[2]['data']['total'] == 2

def test_execute_batch_with_errors(service, mock_strategy_engine):
    """测试批量执行时的错误隔离"""
    mock_engine = Mock()
    mock_engine.execute.side_effect = [
        {'symbol': '600519.SH', 'signal_type': 'BUY', 'confidence': 0.85},
        Exception("数据不足"),
        {'symbol': '000002.SZ', 'signal_type': 'SELL', 'confidence': 0.75}
    ]
    mock_strategy_engine.return_value = mock_engine
    
    request = StrategyBatchExecuteRequest(
        symbols=["600519.SH", "000001.SZ", "000002.SZ"],
        strategy_name="Turtle"
    )
    
    results = list(service.execute_batch(request))
    
    # 应该有 2 个成功信号 + 1 个错误 + 1 个摘要
    signals = [r for r in results if r['type'] == 'signal']
    errors = [r for r in results if r['type'] == 'error']
    summary = [r for r in results if r['type'] == 'summary'][0]
    
    assert len(signals) == 2
    assert len(errors) == 1
    assert summary['data']['success'] == 2
    assert summary['data']['failed'] == 1
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd quantsys-v2
python -m pytest tests/services/test_strategy_execution_service.py::test_execute_batch_strategies -v
```

Expected: FAIL with "AttributeError: 'StrategyExecutionService' object has no attribute 'execute_batch'"

- [ ] **Step 3: 实现批量执行逻辑**

```python
# quantsys-v2/services/strategy_execution_service.py (追加方法)

    def execute_batch(self, request: StrategyBatchExecuteRequest) -> Generator[Dict, None, None]:
        """批量执行策略（流式返回）"""
        start_time = time.time()
        
        # 去重
        symbols = list(set(request.symbols))
        
        # 并发执行
        max_workers = min(10, len(symbols))
        success_count = 0
        failed_count = 0
        signal_distribution = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_symbol = {
                executor.submit(
                    self._execute_single_for_batch,
                    symbol,
                    request.strategy_name,
                    request.date,
                    request.persist
                ): symbol
                for symbol in symbols
            }
            
            # 逐个返回结果
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    signal = future.result()
                    
                    # 过滤低置信度
                    if request.min_confidence and signal['confidence'] < request.min_confidence:
                        continue
                    
                    success_count += 1
                    signal_distribution[signal['signal_type']] += 1
                    
                    yield {
                        'type': 'signal',
                        'data': signal
                    }
                    
                except Exception as e:
                    failed_count += 1
                    yield {
                        'type': 'error',
                        'data': {
                            'symbol': symbol,
                            'error': str(e)
                        }
                    }
        
        # 返回摘要
        duration_ms = int((time.time() - start_time) * 1000)
        yield {
            'type': 'summary',
            'data': {
                'total': len(symbols),
                'success': success_count,
                'failed': failed_count,
                'buy': signal_distribution['BUY'],
                'sell': signal_distribution['SELL'],
                'hold': signal_distribution['HOLD'],
                'duration_ms': duration_ms
            }
        }
    
    def _execute_single_for_batch(self, symbol: str, strategy_name: str, 
                                   date: str, persist: bool) -> Dict:
        """批量执行中的单个股票执行（内部方法）"""
        request = StrategyExecuteRequest(
            symbol=symbol,
            strategy_name=strategy_name,
            date=date,
            persist=persist,
            return_details=False  # 批量模式不返回详细指标
        )
        return self.execute_single(request)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd quantsys-v2
python -m pytest tests/services/test_strategy_execution_service.py::test_execute_batch_strategies -v
python -m pytest tests/services/test_strategy_execution_service.py::test_execute_batch_with_errors -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: 提交**

```bash
git add quantsys-v2/services/strategy_execution_service.py quantsys-v2/tests/services/test_strategy_execution_service.py
git commit -m "feat(services): add batch execution with streaming and error isolation"
```

### Task 4: 完整流程执行（Pipeline）

**Files:**
- Modify: `quantsys-v2/services/strategy_execution_service.py`
- Modify: `quantsys-v2/tests/services/test_strategy_execution_service.py`

- [ ] **Step 1: 写失败测试 - Pipeline 执行**

```python
# quantsys-v2/tests/services/test_strategy_execution_service.py (追加)

@pytest.fixture
def mock_risk_manager():
    with patch('services.strategy_execution_service.RiskManager') as mock:
        yield mock

@pytest.fixture
def mock_order_repo():
    with patch('services.strategy_execution_service.OrderRepository') as mock:
        yield mock

def test_execute_pipeline_with_orders(service, mock_strategy_engine, 
                                      mock_risk_manager, mock_order_repo):
    """测试完整流程执行 - 创建订单"""
    # Mock 策略引擎
    mock_engine = Mock()
    mock_engine.execute.side_effect = [
        {'symbol': '600519.SH', 'signal_type': 'BUY', 'confidence': 0.85, 'entry_price': 1850.0},
        {'symbol': '000001.SZ', 'signal_type': 'BUY', 'confidence': 0.75, 'entry_price': 12.5}
    ]
    mock_strategy_engine.return_value = mock_engine
    
    # Mock 风控管理器
    mock_rm = Mock()
    mock_rm.check_signal.side_effect = [
        {'approved': True},
        {'approved': False, 'reason': '仓位超限'}
    ]
    mock_risk_manager.return_value = mock_rm
    
    # Mock 订单仓库
    mock_order_repo.return_value.create.return_value = {'order_id': 'ORD001'}
    
    request = StrategyPipelineExecuteRequest(
        symbols=["600519.SH", "000001.SZ"],
        strategy_name="Turtle",
        create_orders=True,
        risk_check=True
    )
    
    result = service.execute_pipeline(request)
    
    assert result['signals_generated'] == 2
    assert result['signals_approved'] == 1
    assert result['signals_rejected'] == 1
    assert result['orders_created'] == 1
    assert '仓位超限' in result['rejection_reasons']

def test_execute_pipeline_without_orders(service, mock_strategy_engine, mock_risk_manager):
    """测试完整流程执行 - 不创建订单"""
    mock_engine = Mock()
    mock_engine.execute.return_value = {
        'symbol': '600519.SH',
        'signal_type': 'BUY',
        'confidence': 0.85
    }
    mock_strategy_engine.return_value = mock_engine
    
    mock_rm = Mock()
    mock_rm.check_signal.return_value = {'approved': True}
    mock_risk_manager.return_value = mock_rm
    
    request = StrategyPipelineExecuteRequest(
        symbols=["600519.SH"],
        strategy_name="Turtle",
        create_orders=False
    )
    
    result = service.execute_pipeline(request)
    
    assert result['signals_generated'] == 1
    assert result['signals_approved'] == 1
    assert result['orders_created'] == 0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd quantsys-v2
python -m pytest tests/services/test_strategy_execution_service.py::test_execute_pipeline_with_orders -v
```

Expected: FAIL with "AttributeError: 'StrategyExecutionService' object has no attribute 'execute_pipeline'"

- [ ] **Step 3: 实现 Pipeline 执行逻辑**

```python
# quantsys-v2/services/strategy_execution_service.py (追加方法)

    def execute_pipeline(self, request: StrategyPipelineExecuteRequest) -> Dict:
        """执行完整流程：策略→信号→风控→订单"""
        start_time = time.time()
        execution_date = datetime.now().strftime('%Y-%m-%d')
        
        # 统计数据
        signals_generated = 0
        signals_approved = 0
        signals_rejected = 0
        orders_created = 0
        rejection_reasons = {}
        orders = []
        
        # 批量执行策略
        batch_request = StrategyBatchExecuteRequest(
            symbols=request.symbols,
            strategy_name=request.strategy_name,
            persist=True  # Pipeline 模式强制持久化
        )
        
        for item in self.execute_batch(batch_request):
            if item['type'] == 'signal':
                signal = item['data']
                signals_generated += 1
                
                # 风控检查
                if request.risk_check:
                    risk_result = self.risk_manager.check_signal(signal)
                    
                    if risk_result['approved']:
                        signals_approved += 1
                        
                        # 创建订单
                        if request.create_orders and signal['signal_type'] in ['BUY', 'SELL']:
                            order = self._create_order_from_signal(signal)
                            orders.append(order)
                            orders_created += 1
                    else:
                        signals_rejected += 1
                        reason = risk_result.get('reason', 'unknown')
                        rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                else:
                    # 不做风控检查，直接通过
                    signals_approved += 1
                    if request.create_orders and signal['signal_type'] in ['BUY', 'SELL']:
                        order = self._create_order_from_signal(signal)
                        orders.append(order)
                        orders_created += 1
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return {
            'execution_date': execution_date,
            'duration_ms': duration_ms,
            'signals_generated': signals_generated,
            'signals_approved': signals_approved,
            'signals_rejected': signals_rejected,
            'orders_created': orders_created,
            'rejection_reasons': rejection_reasons,
            'orders': orders
        }
    
    def _create_order_from_signal(self, signal: Dict) -> Dict:
        """从信号创建订单"""
        order_data = {
            'symbol': signal['symbol'],
            'side': signal['signal_type'],
            'price': signal.get('entry_price'),
            'signal_id': signal.get('signal_id'),
            'status': 'pending',
            'created_at': datetime.now()
        }
        
        order = self.order_repo.create(order_data)
        return {
            'order_id': order['order_id'],
            'symbol': order['symbol'],
            'side': order['side'],
            'price': order['price']
        }
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd quantsys-v2
python -m pytest tests/services/test_strategy_execution_service.py::test_execute_pipeline_with_orders -v
python -m pytest tests/services/test_strategy_execution_service.py::test_execute_pipeline_without_orders -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: 提交**

```bash
git add quantsys-v2/services/strategy_execution_service.py quantsys-v2/tests/services/test_strategy_execution_service.py
git commit -m "feat(services): add pipeline execution with risk check and order creation"
```

### Task 5: Flask API 路由

**Files:**
- Create: `quantsys-v2/api/routes/strategy_execution.py`
- Create: `quantsys-v2/tests/api/test_strategy_execution_routes.py`
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: 写失败测试 - API 路由**

```python
# quantsys-v2/tests/api/test_strategy_execution_routes.py
import pytest
import json
from api.server import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_execute_single_strategy_api(client):
    """测试单股执行 API"""
    response = client.post('/api/strategies/execute',
        json={
            'symbol': '600519.SH',
            'strategy_name': 'Turtle',
            'persist': True
        },
        content_type='application/json'
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'signal_id' in data['data']
    assert data['data']['symbol'] == '600519.SH'

def test_execute_batch_strategies_api(client):
    """测试批量执行 API（NDJSON 流式）"""
    response = client.post('/api/strategies/batch-execute',
        json={
            'symbols': ['600519.SH', '000001.SZ'],
            'strategy_name': 'Turtle'
        },
        content_type='application/json'
    )
    
    assert response.status_code == 200
    assert response.content_type == 'application/x-ndjson'
    
    # 解析 NDJSON
    lines = response.data.decode('utf-8').strip().split('\n')
    assert len(lines) >= 3  # 至少 2 个信号 + 1 个摘要
    
    summary = json.loads(lines[-1])
    assert summary['type'] == 'summary'
    assert summary['data']['total'] == 2

def test_execute_pipeline_api(client):
    """测试完整流程 API"""
    response = client.post('/api/strategies/pipeline-execute',
        json={
            'symbols': ['600519.SH'],
            'strategy_name': 'Turtle',
            'create_orders': True
        },
        content_type='application/json'
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'signals_generated' in data['data']
    assert 'orders_created' in data['data']
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd quantsys-v2
python -m pytest tests/api/test_strategy_execution_routes.py::test_execute_single_strategy_api -v
```

Expected: FAIL with "404 NOT FOUND"

- [ ] **Step 3: 实现 API 路由**

```python
# quantsys-v2/api/routes/strategy_execution.py
from flask import Blueprint, request, jsonify, Response
import json
from models.strategy_execution import (
    StrategyExecuteRequest,
    StrategyBatchExecuteRequest,
    StrategyPipelineExecuteRequest
)
from services.strategy_execution_service import StrategyExecutionService

bp = Blueprint('strategy_execution', __name__, url_prefix='/api/strategies')
service = StrategyExecutionService()

@bp.route('/execute', methods=['POST'])
def execute_single():
    """单股策略执行"""
    try:
        data = request.get_json()
        req = StrategyExecuteRequest(**data)
        
        result = service.execute_single(req)
        
        return jsonify({
            'success': True,
            'data': result
        }), 200
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/batch-execute', methods=['POST'])
def execute_batch():
    """批量策略执行（NDJSON 流式）"""
    try:
        data = request.get_json()
        req = StrategyBatchExecuteRequest(**data)
        
        def generate():
            for item in service.execute_batch(req):
                yield json.dumps(item, ensure_ascii=False) + '\n'
        
        return Response(
            generate(),
            mimetype='application/x-ndjson',
            status=200
        )
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/pipeline-execute', methods=['POST'])
def execute_pipeline():
    """完整流程执行"""
    try:
        data = request.get_json()
        req = StrategyPipelineExecuteRequest(**data)
        
        result = service.execute_pipeline(req)
        
        return jsonify({
            'success': True,
            'data': result
        }), 200
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
```

- [ ] **Step 4: 注册路由到 Flask app**

```python
# quantsys-v2/api/server.py (修改)
# 在现有的 blueprint 注册部分添加：

from api.routes import strategy_execution

def create_app():
    app = Flask(__name__)
    
    # ... 现有配置 ...
    
    # 注册路由
    app.register_blueprint(strategy_execution.bp)
    
    # ... 其他 blueprints ...
    
    return app
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd quantsys-v2
python -m pytest tests/api/test_strategy_execution_routes.py -v
```

Expected: PASS (3 tests)

- [ ] **Step 6: 提交**

```bash
git add quantsys-v2/api/routes/strategy_execution.py quantsys-v2/tests/api/test_strategy_execution_routes.py quantsys-v2/api/server.py
git commit -m "feat(api): add strategy execution routes (execute/batch/pipeline)"
```

---

## Phase 2: 前端客户端实现

### Task 6: TypeScript 类型定义

**Files:**
- Modify: `src/infrastructure/quant/types.ts`
- Create: `src/infrastructure/quant/types.test.ts`

- [ ] **Step 1: 写失败测试 - 类型验证**

```typescript
// src/infrastructure/quant/types.test.ts
import { describe, test, expect } from '@jest/globals';
import type {
  StrategyExecuteParams,
  StrategyBatchExecuteParams,
  StrategyPipelineExecuteParams,
  StrategySignal
} from './types.js';

describe('Strategy Execution Types', () => {
  test('StrategyExecuteParams should have required fields', () => {
    const params: StrategyExecuteParams = {
      symbol: '600519.SH',
      strategy_name: 'Turtle'
    };
    
    expect(params.symbol).toBe('600519.SH');
    expect(params.strategy_name).toBe('Turtle');
  });
  
  test('StrategyBatchExecuteParams should accept symbols array', () => {
    const params: StrategyBatchExecuteParams = {
      symbols: ['600519.SH', '000001.SZ'],
      strategy_name: 'Turtle',
      min_confidence: 0.6
    };
    
    expect(params.symbols).toHaveLength(2);
    expect(params.min_confidence).toBe(0.6);
  });
  
  test('StrategySignal should have signal_type union', () => {
    const signal: StrategySignal = {
      symbol: '600519.SH',
      signal_type: 'BUY',
      confidence: 0.85,
      entry_price: 1850.0
    };
    
    expect(signal.signal_type).toBe('BUY');
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- types.test.ts
```

Expected: FAIL with "Cannot find module './types.js'"

- [ ] **Step 3: 添加类型定义**

```typescript
// src/infrastructure/quant/types.ts (追加)

// ===== 策略执行相关类型 =====

export interface StrategyExecuteParams {
  symbol: string;
  strategy_name: string;
  date?: string;
  persist?: boolean;
  return_details?: boolean;
}

export interface StrategyBatchExecuteParams {
  symbols: string[];
  strategy_name: string;
  date?: string;
  persist?: boolean;
  min_confidence?: number;
}

export interface StrategyPipelineExecuteParams {
  symbols: string[];
  strategy_name: string;
  create_orders?: boolean;
  risk_check?: boolean;
}

export interface StrategySignal {
  signal_id?: string;
  symbol: string;
  signal_type: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  entry_price: number;
  stop_loss?: number;
  target_price?: number;
  position_size?: number;
  indicators?: Record<string, any>;
}

export interface BatchExecutionResult {
  signals: StrategySignal[];
  summary: {
    total: number;
    success: number;
    failed: number;
    buy: number;
    sell: number;
    hold: number;
    duration_ms: number;
  };
  errors: Array<{
    symbol: string;
    error: string;
  }>;
}

export interface PipelineExecutionResult {
  execution_date: string;
  duration_ms: number;
  signals_generated: number;
  signals_approved: number;
  signals_rejected: number;
  orders_created: number;
  rejection_reasons: Record<string, number>;
  orders: Array<{
    order_id: string;
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity?: number;
    price: number;
  }>;
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- types.test.ts
```

Expected: PASS (3 tests)

- [ ] **Step 5: 提交**

```bash
git add src/infrastructure/quant/types.ts src/infrastructure/quant/types.test.ts
git commit -m "feat(types): add strategy execution type definitions"
```

### Task 7: QuantV2Client 客户端方法

**Files:**
- Modify: `src/infrastructure/quant/quant-v2-client.ts`
- Create: `src/infrastructure/quant/quant-v2-client-strategy.test.ts`

- [ ] **Step 1: 写失败测试 - executeStrategy**

```typescript
// src/infrastructure/quant/quant-v2-client-strategy.test.ts
import { describe, test, expect, jest, beforeEach } from '@jest/globals';
import { executeStrategy, batchExecuteStrategy, pipelineExecuteStrategy } from './quant-v2-client.js';
import type { StrategyExecuteParams } from './types.js';

// Mock fetch
global.fetch = jest.fn();

describe('QuantV2Client - Strategy Execution', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });
  
  test('executeStrategy should call correct endpoint', async () => {
    const mockResponse = {
      success: true,
      data: {
        signal_id: 'sig_test',
        symbol: '600519.SH',
        signal_type: 'BUY',
        confidence: 0.85,
        entry_price: 1850.0
      }
    };
    
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });
    
    const params: StrategyExecuteParams = {
      symbol: '600519.SH',
      strategy_name: 'Turtle',
      persist: true
    };
    
    const result = await executeStrategy(params);
    
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:5001/api/strategies/execute',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
      })
    );
    
    expect(result.signal_id).toBe('sig_test');
    expect(result.signal_type).toBe('BUY');
  });
  
  test('executeStrategy should throw on API error', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      statusText: 'Bad Request'
    });
    
    const params: StrategyExecuteParams = {
      symbol: '600519.SH',
      strategy_name: 'Turtle'
    };
    
    await expect(executeStrategy(params)).rejects.toThrow('Strategy execution failed');
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- quant-v2-client-strategy.test.ts
```

Expected: FAIL with "executeStrategy is not a function"

- [ ] **Step 3: 实现 executeStrategy 方法**

```typescript
// src/infrastructure/quant/quant-v2-client.ts (追加)

import type {
  StrategyExecuteParams,
  StrategyBatchExecuteParams,
  StrategyPipelineExecuteParams,
  StrategySignal,
  BatchExecutionResult,
  PipelineExecutionResult
} from './types.js';

/**
 * 执行单股策略
 */
export async function executeStrategy(
  params: StrategyExecuteParams
): Promise<StrategySignal> {
  const response = await fetch(`${V2_API_BASE}/api/strategies/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal: AbortSignal.timeout(V2_TIMEOUT_MS)
  });
  
  if (!response.ok) {
    throw new QuantV2Error(`Strategy execution failed: ${response.statusText}`);
  }
  
  const result = await response.json();
  
  if (!result.success) {
    throw new QuantV2Error(result.error || 'Unknown error');
  }
  
  return result.data;
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- quant-v2-client-strategy.test.ts
```

Expected: PASS (2 tests)

- [ ] **Step 5: 提交**

```bash
git add src/infrastructure/quant/quant-v2-client.ts src/infrastructure/quant/quant-v2-client-strategy.test.ts
git commit -m "feat(client): add executeStrategy method"
```

### Task 8: 批量执行客户端方法

**Files:**
- Modify: `src/infrastructure/quant/quant-v2-client.ts`
- Modify: `src/infrastructure/quant/quant-v2-client-strategy.test.ts`

- [ ] **Step 1: 写失败测试 - batchExecuteStrategy**

```typescript
// src/infrastructure/quant/quant-v2-client-strategy.test.ts (追加)

test('batchExecuteStrategy should parse NDJSON stream', async () => {
  const ndjsonResponse = 
    '{"type":"signal","data":{"symbol":"600519.SH","signal_type":"BUY","confidence":0.85}}\n' +
    '{"type":"signal","data":{"symbol":"000001.SZ","signal_type":"HOLD","confidence":0.55}}\n' +
    '{"type":"summary","data":{"total":2,"success":2,"failed":0,"buy":1,"sell":0,"hold":1}}\n';
  
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    text: async () => ndjsonResponse
  });
  
  const params: StrategyBatchExecuteParams = {
    symbols: ['600519.SH', '000001.SZ'],
    strategy_name: 'Turtle'
  };
  
  const result = await batchExecuteStrategy(params);
  
  expect(result.signals).toHaveLength(2);
  expect(result.summary.total).toBe(2);
  expect(result.summary.buy).toBe(1);
  expect(result.errors).toHaveLength(0);
});

test('batchExecuteStrategy should handle errors in stream', async () => {
  const ndjsonResponse = 
    '{"type":"signal","data":{"symbol":"600519.SH","signal_type":"BUY","confidence":0.85}}\n' +
    '{"type":"error","data":{"symbol":"000001.SZ","error":"数据不足"}}\n' +
    '{"type":"summary","data":{"total":2,"success":1,"failed":1}}\n';
  
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    text: async () => ndjsonResponse
  });
  
  const params: StrategyBatchExecuteParams = {
    symbols: ['600519.SH', '000001.SZ'],
    strategy_name: 'Turtle'
  };
  
  const result = await batchExecuteStrategy(params);
  
  expect(result.signals).toHaveLength(1);
  expect(result.errors).toHaveLength(1);
  expect(result.errors[0].symbol).toBe('000001.SZ');
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- quant-v2-client-strategy.test.ts
```

Expected: FAIL with "batchExecuteStrategy is not a function"

- [ ] **Step 3: 实现 batchExecuteStrategy 方法**

```typescript
// src/infrastructure/quant/quant-v2-client.ts (追加)

/**
 * 批量执行策略（NDJSON 流式响应）
 */
export async function batchExecuteStrategy(
  params: StrategyBatchExecuteParams
): Promise<BatchExecutionResult> {
  const response = await fetch(`${V2_API_BASE}/api/strategies/batch-execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal: AbortSignal.timeout(V2_TIMEOUT_MS)
  });
  
  if (!response.ok) {
    throw new QuantV2Error(`Batch execution failed: ${response.statusText}`);
  }
  
  // 解析 NDJSON 流式响应
  const text = await response.text();
  const lines = text.trim().split('\n').filter(line => line.trim());
  
  const signals: StrategySignal[] = [];
  const errors: Array<{ symbol: string; error: string }> = [];
  let summary: any = null;
  
  for (const line of lines) {
    try {
      const obj = JSON.parse(line);
      
      if (obj.type === 'signal') {
        signals.push(obj.data);
      } else if (obj.type === 'error') {
        errors.push(obj.data);
      } else if (obj.type === 'summary') {
        summary = obj.data;
      }
    } catch (e) {
      // 忽略无法解析的行
      console.warn('Failed to parse NDJSON line:', line);
    }
  }
  
  if (!summary) {
    throw new QuantV2Error('No summary in batch execution response');
  }
  
  return { signals, summary, errors };
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- quant-v2-client-strategy.test.ts
```

Expected: PASS (4 tests)

- [ ] **Step 5: 提交**

```bash
git add src/infrastructure/quant/quant-v2-client.ts src/infrastructure/quant/quant-v2-client-strategy.test.ts
git commit -m "feat(client): add batchExecuteStrategy with NDJSON parsing"
```

### Task 9: Pipeline 执行客户端方法

**Files:**
- Modify: `src/infrastructure/quant/quant-v2-client.ts`
- Modify: `src/infrastructure/quant/quant-v2-client-strategy.test.ts`

- [ ] **Step 1: 写失败测试 - pipelineExecuteStrategy**

```typescript
// src/infrastructure/quant/quant-v2-client-strategy.test.ts (追加)

test('pipelineExecuteStrategy should return execution result', async () => {
  const mockResponse = {
    success: true,
    data: {
      execution_date: '2026-05-29',
      duration_ms: 5800,
      signals_generated: 48,
      signals_approved: 35,
      signals_rejected: 13,
      orders_created: 35,
      rejection_reasons: {
        '仓位超限': 8,
        '单日交易次数超限': 3
      },
      orders: [
        { order_id: 'ORD001', symbol: '600519.SH', side: 'BUY', price: 1850.0 }
      ]
    }
  };
  
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    json: async () => mockResponse
  });
  
  const params: StrategyPipelineExecuteParams = {
    symbols: ['600519.SH'],
    strategy_name: 'Turtle',
    create_orders: true
  };
  
  const result = await pipelineExecuteStrategy(params);
  
  expect(result.signals_generated).toBe(48);
  expect(result.signals_approved).toBe(35);
  expect(result.orders_created).toBe(35);
  expect(result.rejection_reasons['仓位超限']).toBe(8);
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- quant-v2-client-strategy.test.ts
```

Expected: FAIL with "pipelineExecuteStrategy is not a function"

- [ ] **Step 3: 实现 pipelineExecuteStrategy 方法**

```typescript
// src/infrastructure/quant/quant-v2-client.ts (追加)

/**
 * 执行完整流程（策略→信号→风控→订单）
 */
export async function pipelineExecuteStrategy(
  params: StrategyPipelineExecuteParams
): Promise<PipelineExecutionResult> {
  const response = await fetch(`${V2_API_BASE}/api/strategies/pipeline-execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
    signal: AbortSignal.timeout(V2_TIMEOUT_MS)
  });
  
  if (!response.ok) {
    throw new QuantV2Error(`Pipeline execution failed: ${response.statusText}`);
  }
  
  const result = await response.json();
  
  if (!result.success) {
    throw new QuantV2Error(result.error || 'Unknown error');
  }
  
  return result.data;
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- quant-v2-client-strategy.test.ts
```

Expected: PASS (5 tests)

- [ ] **Step 5: 提交**

```bash
git add src/infrastructure/quant/quant-v2-client.ts src/infrastructure/quant/quant-v2-client-strategy.test.ts
git commit -m "feat(client): add pipelineExecuteStrategy method"
```

---

## Phase 3: quant_cli 工具集成

### Task 10: 添加 strategy.execute 命令定义

**Files:**
- Modify: `src/infrastructure/tools/core/quant-cli-tool.ts`
- Create: `src/infrastructure/tools/core/quant-cli-strategy-execute.test.ts`

- [ ] **Step 1: 写失败测试 - strategy.execute 命令**

```typescript
// src/infrastructure/tools/core/quant-cli-strategy-execute.test.ts
import { describe, test, expect, jest, beforeEach } from '@jest/globals';
import { quantCliTool } from './quant-cli-tool.js';
import * as quantV2Client from '../../quant/quant-v2-client.js';

jest.mock('../../quant/quant-v2-client.js');

describe('quant_cli - strategy.execute command', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });
  
  test('should execute single mode', async () => {
    const mockSignal = {
      signal_id: 'sig_test',
      symbol: '600519.SH',
      signal_type: 'BUY',
      confidence: 0.85,
      entry_price: 1850.0,
      stop_loss: 1750.0
    };
    
    (quantV2Client.executeStrategy as jest.Mock).mockResolvedValueOnce(mockSignal);
    
    const result = await quantCliTool.execute('test-call', {
      command: 'strategy.execute',
      params: {
        action: 'single',
        symbol: '600519.SH',
        strategy: 'Turtle'
      }
    });
    
    expect(result.content[0].text).toContain('策略执行结果');
    expect(result.content[0].text).toContain('BUY');
    expect(result.content[0].text).toContain('85%');
  });
  
  test('should validate action parameter', async () => {
    const result = await quantCliTool.execute('test-call', {
      command: 'strategy.execute',
      params: {
        symbol: '600519.SH',
        strategy: 'Turtle'
        // missing action
      }
    });
    
    expect(result.content[0].text).toContain('错误');
    expect(result.content[0].text).toContain('action');
  });
  
  test('should validate symbol for single mode', async () => {
    const result = await quantCliTool.execute('test-call', {
      command: 'strategy.execute',
      params: {
        action: 'single',
        strategy: 'Turtle'
        // missing symbol
      }
    });
    
    expect(result.content[0].text).toContain('错误');
    expect(result.content[0].text).toContain('symbol');
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- quant-cli-strategy-execute.test.ts
```

Expected: FAIL with "strategy.execute command not found"

- [ ] **Step 3: 添加命令定义到 COMMANDS**

```typescript
// src/infrastructure/tools/core/quant-cli-tool.ts (在 COMMANDS 对象中添加)

const COMMANDS: Record<string, CommandRule> = {
  // ... 现有命令 ...
  
  "strategy.execute": {
    domain: "strategy",
    action: "execute",
    description: 
      "统一策略执行工具，支持三种模式：\n" +
      "- action='single': 单股快速分析，返回详细风控参数\n" +
      "- action='batch': 批量信号生成，流式返回结果\n" +
      "- action='pipeline': 完整自动化流程（策略→信号→风控→订单）\n" +
      "默认持久化到数据库（persist=true），支持策略循环闭合。",
    params: {
      action: { 
        required: true, 
        type: "string", 
        enum: ["single", "batch", "pipeline"] 
      },
      symbol: { type: "string", symbol: true },
      symbols: { type: "array" },
      strategy: { required: true, type: "string" },
      date: { type: "string" },
      persist: { type: "boolean" },
      return_details: { type: "boolean" },
      min_confidence: { type: "number", min: 0, max: 1 },
      create_orders: { type: "boolean" },
      risk_check: { type: "boolean" }
    },
    example: {
      action: "single",
      symbol: "600519.SH",
      strategy: "Turtle"
    }
  },
  
  // ... 其他命令 ...
};
```

- [ ] **Step 4: 添加路由映射**

```typescript
// src/infrastructure/tools/core/quant-cli-tool.ts (在 V2_ROUTES 中添加)

const V2_ROUTES: Record<string, { path: string; method: "GET" | "POST" | "DELETE" }> = {
  // ... 现有路由 ...
  
  "strategy.execute": { path: "/api/strategies/execute", method: "POST" },
  "strategy.batch": { path: "/api/strategies/batch-execute", method: "POST" },
  "strategy.pipeline": { path: "/api/strategies/pipeline-execute", method: "POST" },
  
  // ... 其他路由 ...
};
```

- [ ] **Step 5: 运行测试验证通过**

```bash
npm test -- quant-cli-strategy-execute.test.ts
```

Expected: PASS (3 tests)

- [ ] **Step 6: 提交**

```bash
git add src/infrastructure/tools/core/quant-cli-tool.ts src/infrastructure/tools/core/quant-cli-strategy-execute.test.ts
git commit -m "feat(quant-cli): add strategy.execute command definition"
```

### Task 11: 实现 strategy.execute 执行逻辑

**Files:**
- Modify: `src/infrastructure/tools/core/quant-cli-tool.ts`
- Modify: `src/infrastructure/tools/core/quant-cli-strategy-execute.test.ts`

- [ ] **Step 1: 写失败测试 - 批量模式**

```typescript
// src/infrastructure/tools/core/quant-cli-strategy-execute.test.ts (追加)

test('should execute batch mode', async () => {
  const mockResult = {
    signals: [
      { symbol: '600519.SH', signal_type: 'BUY', confidence: 0.85 },
      { symbol: '000001.SZ', signal_type: 'HOLD', confidence: 0.55 }
    ],
    summary: {
      total: 2,
      success: 2,
      failed: 0,
      buy: 1,
      sell: 0,
      hold: 1,
      duration_ms: 2300
    },
    errors: []
  };
  
  (quantV2Client.batchExecuteStrategy as jest.Mock).mockResolvedValueOnce(mockResult);
  
  const result = await quantCliTool.execute('test-call', {
    command: 'strategy.execute',
    params: {
      action: 'batch',
      symbols: ['600519.SH', '000001.SZ'],
      strategy: 'Turtle'
    }
  });
  
  expect(result.content[0].text).toContain('批量策略执行完成');
  expect(result.content[0].text).toContain('BUY 信号: 1');
  expect(result.content[0].text).toContain('HOLD 信号: 1');
});

test('should execute pipeline mode', async () => {
  const mockResult = {
    execution_date: '2026-05-29',
    duration_ms: 5800,
    signals_generated: 48,
    signals_approved: 35,
    signals_rejected: 13,
    orders_created: 35,
    rejection_reasons: { '仓位超限': 8 },
    orders: []
  };
  
  (quantV2Client.pipelineExecuteStrategy as jest.Mock).mockResolvedValueOnce(mockResult);
  
  const result = await quantCliTool.execute('test-call', {
    command: 'strategy.execute',
    params: {
      action: 'pipeline',
      symbols: ['600519.SH'],
      strategy: 'Turtle',
      create_orders: true
    }
  });
  
  expect(result.content[0].text).toContain('自动化流程执行完成');
  expect(result.content[0].text).toContain('生成信号: 48');
  expect(result.content[0].text).toContain('创建订单: 35');
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- quant-cli-strategy-execute.test.ts
```

Expected: FAIL with "batch/pipeline modes not implemented"

- [ ] **Step 3: 实现执行逻辑**

```typescript
// src/infrastructure/tools/core/quant-cli-tool.ts (在 execute 函数中添加)

import { 
  executeStrategy, 
  batchExecuteStrategy, 
  pipelineExecuteStrategy 
} from '../../quant/quant-v2-client.js';
import { 
  formatSingleSignal, 
  formatBatchSignals, 
  formatPipelineResult 
} from '../../quant/formatters.js';

// 在 execute 函数中处理 strategy.execute
if (command === "strategy.execute") {
  const { action, symbol, symbols, strategy, ...rest } = params;
  
  // 参数验证
  if (!action || !['single', 'batch', 'pipeline'].includes(action)) {
    return {
      content: [{
        type: "text" as const,
        text: "错误：action 参数必须是 'single'、'batch' 或 'pipeline'"
      }],
      details: undefined
    };
  }
  
  if (action === "single") {
    if (!symbol) {
      return {
        content: [{
          type: "text" as const,
          text: "错误：action='single' 需要 symbol 参数"
        }],
        details: undefined
      };
    }
    
    try {
      const result = await executeStrategy({
        symbol,
        strategy_name: strategy,
        ...rest
      });
      
      return {
        content: [{
          type: "text" as const,
          text: formatSingleSignal(result)
        }],
        details: result
      };
    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `执行失败: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: undefined
      };
    }
  }
  
  if (action === "batch") {
    if (!symbols || !Array.isArray(symbols) || symbols.length === 0) {
      return {
        content: [{
          type: "text" as const,
          text: "错误：action='batch' 需要 symbols 参数（数组）"
        }],
        details: undefined
      };
    }
    
    try {
      const result = await batchExecuteStrategy({
        symbols,
        strategy_name: strategy,
        ...rest
      });
      
      return {
        content: [{
          type: "text" as const,
          text: formatBatchSignals(result)
        }],
        details: result
      };
    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `批量执行失败: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: undefined
      };
    }
  }
  
  if (action === "pipeline") {
    if (!symbols || !Array.isArray(symbols) || symbols.length === 0) {
      return {
        content: [{
          type: "text" as const,
          text: "错误：action='pipeline' 需要 symbols 参数（数组）"
        }],
        details: undefined
      };
    }
    
    try {
      const result = await pipelineExecuteStrategy({
        symbols,
        strategy_name: strategy,
        create_orders: rest.create_orders,
        risk_check: rest.risk_check
      });
      
      return {
        content: [{
          type: "text" as const,
          text: formatPipelineResult(result)
        }],
        details: result
      };
    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `流程执行失败: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: undefined
      };
    }
  }
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- quant-cli-strategy-execute.test.ts
```

Expected: PASS (5 tests)

- [ ] **Step 5: 提交**

```bash
git add src/infrastructure/tools/core/quant-cli-tool.ts src/infrastructure/tools/core/quant-cli-strategy-execute.test.ts
git commit -m "feat(quant-cli): implement strategy.execute execution logic"
```

### Task 12: 添加格式化函数

**Files:**
- Modify: `src/infrastructure/quant/formatters.ts`
- Create: `src/infrastructure/quant/formatters-strategy.test.ts`

- [ ] **Step 1: 写失败测试 - 格式化函数**

```typescript
// src/infrastructure/quant/formatters-strategy.test.ts
import { describe, test, expect } from '@jest/globals';
import { formatSingleSignal, formatBatchSignals, formatPipelineResult } from './formatters.js';
import type { StrategySignal, BatchExecutionResult, PipelineExecutionResult } from './types.js';

describe('Strategy Formatters', () => {
  test('formatSingleSignal should format BUY signal', () => {
    const signal: StrategySignal = {
      signal_id: 'sig_test',
      symbol: '600519.SH',
      signal_type: 'BUY',
      confidence: 0.85,
      entry_price: 1850.0,
      stop_loss: 1750.0,
      target_price: 2050.0,
      position_size: 0.08
    };
    
    const result = formatSingleSignal(signal);
    
    expect(result).toContain('策略执行结果');
    expect(result).toContain('600519.SH');
    expect(result).toContain('BUY');
    expect(result).toContain('85%');
    expect(result).toContain('1,850.00');
    expect(result).toContain('sig_test');
  });
  
  test('formatBatchSignals should format batch result', () => {
    const batchResult: BatchExecutionResult = {
      signals: [
        { symbol: '600519.SH', signal_type: 'BUY', confidence: 0.85, entry_price: 1850.0 },
        { symbol: '000001.SZ', signal_type: 'HOLD', confidence: 0.55, entry_price: 12.5 }
      ],
      summary: {
        total: 2,
        success: 2,
        failed: 0,
        buy: 1,
        sell: 0,
        hold: 1,
        duration_ms: 2300
      },
      errors: []
    };
    
    const result = formatBatchSignals(batchResult);
    
    expect(result).toContain('批量策略执行完成');
    expect(result).toContain('总股票数: 2');
    expect(result).toContain('BUY 信号: 1');
    expect(result).toContain('HOLD 信号: 1');
  });
  
  test('formatPipelineResult should format pipeline result', () => {
    const pipelineResult: PipelineExecutionResult = {
      execution_date: '2026-05-29',
      duration_ms: 5800,
      signals_generated: 48,
      signals_approved: 35,
      signals_rejected: 13,
      orders_created: 35,
      rejection_reasons: { '仓位超限': 8, '单日交易次数超限': 3 },
      orders: []
    };
    
    const result = formatPipelineResult(pipelineResult);
    
    expect(result).toContain('自动化流程执行完成');
    expect(result).toContain('生成信号: 48');
    expect(result).toContain('风控通过: 35');
    expect(result).toContain('创建订单: 35');
    expect(result).toContain('仓位超限: 8');
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- formatters-strategy.test.ts
```

Expected: FAIL with "formatSingleSignal is not a function"

- [ ] **Step 3: 实现格式化函数**

```typescript
// src/infrastructure/quant/formatters.ts (追加)

import type { StrategySignal, BatchExecutionResult, PipelineExecutionResult } from './types.js';

/**
 * 格式化单股策略信号
 */
export function formatSingleSignal(signal: StrategySignal): string {
  const signalEmoji = signal.signal_type === 'BUY' ? '🟢' : 
                      signal.signal_type === 'SELL' ? '🔴' : '⚪';
  
  let output = `## 📊 策略执行结果\n\n`;
  output += `**股票**: ${signal.symbol}\n`;
  
  if (signal.signal_id) {
    output += `**信号ID**: ${signal.signal_id}\n`;
  }
  
  output += `\n### 交易信号\n`;
  output += `- **方向**: ${signalEmoji} ${signal.signal_type}\n`;
  output += `- **置信度**: ${(signal.confidence * 100).toFixed(0)}%\n`;
  output += `- **当前价格**: ¥${signal.entry_price.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}\n`;
  
  if (signal.stop_loss || signal.target_price || signal.position_size) {
    output += `\n### 风险管理\n`;
    
    if (signal.stop_loss) {
      const stopLossPct = ((signal.stop_loss - signal.entry_price) / signal.entry_price * 100).toFixed(1);
      output += `- **止损价格**: ¥${signal.stop_loss.toLocaleString('zh-CN', { minimumFractionDigits: 2 })} (${stopLossPct}%)\n`;
    }
    
    if (signal.target_price) {
      const targetPct = ((signal.target_price - signal.entry_price) / signal.entry_price * 100).toFixed(1);
      output += `- **目标价格**: ¥${signal.target_price.toLocaleString('zh-CN', { minimumFractionDigits: 2 })} (+${targetPct}%)\n`;
    }
    
    if (signal.position_size) {
      output += `- **建议仓位**: ${(signal.position_size * 100).toFixed(0)}%\n`;
    }
  }
  
  if (signal.indicators && Object.keys(signal.indicators).length > 0) {
    output += `\n### 技术指标\n`;
    for (const [key, value] of Object.entries(signal.indicators)) {
      output += `- ${key}: ${typeof value === 'number' ? value.toFixed(2) : value}\n`;
    }
  }
  
  return output;
}

/**
 * 格式化批量执行结果
 */
export function formatBatchSignals(result: BatchExecutionResult): string {
  let output = `## 📊 批量策略执行完成\n\n`;
  
  output += `**执行时间**: ${new Date().toLocaleString('zh-CN')}\n`;
  output += `**耗时**: ${(result.summary.duration_ms / 1000).toFixed(1)}秒\n\n`;
  
  output += `### 统计摘要\n`;
  output += `- 总股票数: ${result.summary.total}\n`;
  output += `- 成功: ${result.summary.success}\n`;
  output += `- 失败: ${result.summary.failed}\n`;
  output += `- BUY 信号: ${result.summary.buy} (${(result.summary.buy / result.summary.success * 100).toFixed(0)}%)\n`;
  output += `- SELL 信号: ${result.summary.sell} (${(result.summary.sell / result.summary.success * 100).toFixed(0)}%)\n`;
  output += `- HOLD 信号: ${result.summary.hold} (${(result.summary.hold / result.summary.success * 100).toFixed(0)}%)\n`;
  
  // BUY 信号列表
  const buySignals = result.signals.filter(s => s.signal_type === 'BUY');
  if (buySignals.length > 0) {
    output += `\n### BUY 信号列表\n`;
    output += `| 股票 | 置信度 | 当前价 | 止损价 |\n`;
    output += `|------|--------|--------|--------|\n`;
    for (const signal of buySignals.slice(0, 10)) {
      output += `| ${signal.symbol} | ${(signal.confidence * 100).toFixed(0)}% | ${signal.entry_price.toFixed(2)} | ${signal.stop_loss?.toFixed(2) || '-'} |\n`;
    }
    if (buySignals.length > 10) {
      output += `\n... 还有 ${buySignals.length - 10} 个 BUY 信号\n`;
    }
  }
  
  // 错误记录
  if (result.errors.length > 0) {
    output += `\n### 失败记录\n`;
    for (const error of result.errors) {
      output += `- ${error.symbol}: ${error.error}\n`;
    }
  }
  
  return output;
}

/**
 * 格式化流程执行结果
 */
export function formatPipelineResult(result: PipelineExecutionResult): string {
  let output = `## ✅ 自动化流程执行完成\n\n`;
  
  output += `**执行日期**: ${result.execution_date}\n`;
  output += `**耗时**: ${(result.duration_ms / 1000).toFixed(1)}秒\n\n`;
  
  output += `### 📊 执行统计\n`;
  output += `| 阶段 | 数量 |\n`;
  output += `|------|------|\n`;
  output += `| 生成信号 | ${result.signals_generated} |\n`;
  output += `| 风控通过 | ${result.signals_approved} |\n`;
  output += `| 风控拒绝 | ${result.signals_rejected} |\n`;
  output += `| 创建订单 | ${result.orders_created} |\n`;
  
  if (Object.keys(result.rejection_reasons).length > 0) {
    output += `\n### 🛡️ 风控拒绝原因\n`;
    for (const [reason, count] of Object.entries(result.rejection_reasons)) {
      output += `- ${reason}: ${count} 只\n`;
    }
  }
  
  if (result.orders.length > 0) {
    output += `\n### 📝 已创建订单\n`;
    output += `| 订单ID | 股票 | 方向 | 价格 |\n`;
    output += `|--------|------|------|------|\n`;
    for (const order of result.orders.slice(0, 10)) {
      output += `| ${order.order_id} | ${order.symbol} | ${order.side} | ${order.price.toFixed(2)} |\n`;
    }
    if (result.orders.length > 10) {
      output += `\n... 还有 ${result.orders.length - 10} 个订单\n`;
    }
  }
  
  return output;
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- formatters-strategy.test.ts
```

Expected: PASS (3 tests)

- [ ] **Step 5: 提交**

```bash
git add src/infrastructure/quant/formatters.ts src/infrastructure/quant/formatters-strategy.test.ts
git commit -m "feat(formatters): add strategy execution formatters"
```

---

## Phase 4: 兼容层和迁移

### Task 13: 添加向后兼容层

**Files:**
- Modify: `src/infrastructure/tools/core/quant-cli-tool.ts`
- Create: `docs/migration/strategy-system-unification.md`

- [ ] **Step 1: 添加 signal.generate 别名**

```typescript
// src/infrastructure/tools/core/quant-cli-tool.ts (在 COMMANDS 中添加)

const COMMANDS: Record<string, CommandRule> = {
  // ... 现有命令 ...
  
  "signal.generate": {
    domain: "signal",
    action: "generate",
    description: 
      "⚠️ DEPRECATED: 请使用 strategy.execute 命令。\n" +
      "此命令将在 v3.0 移除。自动映射到 strategy.execute action='batch'。",
    params: {
      symbols: { required: true, type: "array" },
      strategy: { required: true, type: "string" },
      date: { type: "string" },
      persist: { type: "boolean" },
      min_confidence: { type: "number" }
    },
    deprecated: true,
    replacement: "strategy.execute"
  }
};
```

- [ ] **Step 2: 添加命令映射逻辑**

```typescript
// src/infrastructure/tools/core/quant-cli-tool.ts (在 execute 函数开头添加)

// 向后兼容：signal.generate → strategy.execute
if (command === "signal.generate") {
  console.warn(
    "⚠️ DEPRECATED: signal.generate 命令已废弃，请使用 strategy.execute。\n" +
    "此命令将在 v3.0 移除。"
  );
  
  // 映射到 strategy.execute
  return quantCliTool.execute(callId, {
    command: "strategy.execute",
    params: {
      action: "batch",
      ...params
    }
  });
}
```

- [ ] **Step 3: 创建迁移文档**

```markdown
# 策略系统统一迁移指南

## 概述

策略执行系统已统一到 `quant_cli` 工具的 `strategy.execute` 命令。旧的 `strategy_execute` 工具和 `signal.generate` 命令已废弃。

## 迁移映射

### signal.generate → strategy.execute (batch)

**旧用法**:
```typescript
quant_cli({
  command: "signal.generate",
  params: {
    symbols: ["600519.SH", "000001.SZ"],
    strategy: "Turtle",
    min_confidence: 0.6
  }
})
```

**新用法**:
```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "batch",
    symbols: ["600519.SH", "000001.SZ"],
    strategy: "Turtle",
    min_confidence: 0.6
  }
})
```

### strategy_execute 工具 → strategy.execute (single)

**旧用法**:
```typescript
strategy_execute({
  symbol: "600519.SH",
  strategy_name: "Turtle"
})
```

**新用法**:
```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "single",
    symbol: "600519.SH",
    strategy: "Turtle"
  }
})
```

## 新增功能

### Pipeline 模式

完整自动化流程（策略→信号→风控→订单）：

```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "pipeline",
    symbols: ["600519.SH", "000001.SZ"],
    strategy: "Turtle",
    create_orders: true,
    risk_check: true
  }
})
```

## 废弃时间表

- **v2.1** (当前): 添加向后兼容层，旧命令显示警告
- **v2.5** (2026-07): 旧命令标记为 DEPRECATED
- **v3.0** (2026-10): 移除旧命令和工具

## 自动迁移脚本

```bash
# 查找所有使用旧命令的文件
grep -r "signal.generate" src/
grep -r "strategy_execute" src/

# 使用 sed 批量替换（请先备份）
find src/ -type f -name "*.ts" -exec sed -i '' \
  's/command: "signal.generate"/command: "strategy.execute", params: { action: "batch"/g' {} +
```
```

- [ ] **Step 4: 提交**

```bash
git add src/infrastructure/tools/core/quant-cli-tool.ts docs/migration/strategy-system-unification.md
git commit -m "feat(compat): add backward compatibility layer for deprecated commands"
```

### Task 14: 废弃旧工具

**Files:**
- Delete: `src/infrastructure/tools/strategy/execute-tool.ts`
- Modify: `src/infrastructure/tools/index.ts`
- Modify: `CLAUDE.md`

- [ ] **Step 1: 标记 strategyExecuteTool 为废弃**

```typescript
// src/infrastructure/tools/index.ts (修改)

import { strategyExecuteTool } from './strategy/execute-tool.js';

// ⚠️ DEPRECATED: 使用 quant_cli 的 strategy.execute 命令
// 此工具将在 v3.0 移除
export const deprecatedTools = {
  strategy_execute: strategyExecuteTool
};

// 从主工具列表中移除
export const tools = [
  // ... 其他工具 ...
  // strategyExecuteTool, // REMOVED
];
```

- [ ] **Step 2: 更新 CLAUDE.md 文档**

```markdown
# CLAUDE.md (修改策略执行部分)

## 策略执行

### 统一命令：strategy.execute

使用 `quant_cli` 工具的 `strategy.execute` 命令执行策略，支持三种模式：

1. **single**: 单股快速分析
   ```typescript
   quant_cli({
     command: "strategy.execute",
     params: {
       action: "single",
       symbol: "600519.SH",
       strategy: "Turtle"
     }
   })
   ```

2. **batch**: 批量信号生成
   ```typescript
   quant_cli({
     command: "strategy.execute",
     params: {
       action: "batch",
       symbols: ["600519.SH", "000001.SZ"],
       strategy: "Turtle",
       min_confidence: 0.6
     }
   })
   ```

3. **pipeline**: 完整自动化流程
   ```typescript
   quant_cli({
     command: "strategy.execute",
     params: {
       action: "pipeline",
       symbols: ["600519.SH", "000001.SZ"],
       strategy: "Turtle",
       create_orders: true,
       risk_check: true
     }
   })
   ```

### 废弃命令

以下命令已废弃，将在 v3.0 移除：
- ❌ `signal.generate` → 使用 `strategy.execute` (action='batch')
- ❌ `strategy_execute` 工具 → 使用 `quant_cli` 的 `strategy.execute`
```

- [ ] **Step 3: 删除旧工具文件**

```bash
# 备份旧文件
mkdir -p .deprecated/tools/strategy
git mv src/infrastructure/tools/strategy/execute-tool.ts .deprecated/tools/strategy/

# 或直接删除
# git rm src/infrastructure/tools/strategy/execute-tool.ts
```

- [ ] **Step 4: 提交**

```bash
git add src/infrastructure/tools/index.ts CLAUDE.md
git commit -m "chore: deprecate old strategy execution tools"
```

---

## Phase 5: 测试和文档

### Task 15: 端到端测试

**Files:**
- Create: `tests/e2e/strategy-execution-flow.test.ts`

- [ ] **Step 1: 写端到端测试**

```typescript
// tests/e2e/strategy-execution-flow.test.ts
import { describe, test, expect, beforeAll, afterAll } from '@jest/globals';
import { quantCliTool } from '../../src/infrastructure/tools/core/quant-cli-tool.js';
import { startQuantV2Server, stopQuantV2Server } from '../helpers/quant-server.js';

describe('Strategy Execution E2E Flow', () => {
  beforeAll(async () => {
    await startQuantV2Server();
  });
  
  afterAll(async () => {
    await stopQuantV2Server();
  });
  
  test('should execute full pipeline: single → batch → pipeline', async () => {
    // Step 1: 单股分析
    const singleResult = await quantCliTool.execute('e2e-single', {
      command: 'strategy.execute',
      params: {
        action: 'single',
        symbol: '600519.SH',
        strategy: 'Turtle',
        persist: true
      }
    });
    
    expect(singleResult.content[0].text).toContain('策略执行结果');
    expect(singleResult.details).toHaveProperty('signal_id');
    
    // Step 2: 批量生成
    const batchResult = await quantCliTool.execute('e2e-batch', {
      command: 'strategy.execute',
      params: {
        action: 'batch',
        symbols: ['600519.SH', '000001.SZ', '000002.SZ'],
        strategy: 'Turtle',
        persist: true,
        min_confidence: 0.6
      }
    });
    
    expect(batchResult.content[0].text).toContain('批量策略执行完成');
    expect(batchResult.details.signals.length).toBeGreaterThan(0);
    
    // Step 3: 完整流程（不创建订单）
    const pipelineResult = await quantCliTool.execute('e2e-pipeline', {
      command: 'strategy.execute',
      params: {
        action: 'pipeline',
        symbols: ['600519.SH', '000001.SZ'],
        strategy: 'Turtle',
        create_orders: false,
        risk_check: true
      }
    });
    
    expect(pipelineResult.content[0].text).toContain('自动化流程执行完成');
    expect(pipelineResult.details.signals_generated).toBeGreaterThan(0);
    expect(pipelineResult.details.orders_created).toBe(0);
  }, 30000); // 30s timeout
  
  test('should handle backward compatibility', async () => {
    // 测试 signal.generate 别名
    const result = await quantCliTool.execute('e2e-compat', {
      command: 'signal.generate',
      params: {
        symbols: ['600519.SH'],
        strategy: 'Turtle'
      }
    });
    
    expect(result.content[0].text).toContain('批量策略执行完成');
  });
});
```

- [ ] **Step 2: 运行端到端测试**

```bash
npm run test:e2e -- strategy-execution-flow.test.ts
```

Expected: PASS (2 tests)

- [ ] **Step 3: 提交**

```bash
git add tests/e2e/strategy-execution-flow.test.ts
git commit -m "test(e2e): add strategy execution end-to-end tests"
```

### Task 16: 性能测试

**Files:**
- Create: `tests/performance/strategy-execution-perf.test.ts`

- [ ] **Step 1: 写性能测试**

```typescript
// tests/performance/strategy-execution-perf.test.ts
import { describe, test, expect } from '@jest/globals';
import { batchExecuteStrategy } from '../../src/infrastructure/quant/quant-v2-client.js';

describe('Strategy Execution Performance', () => {
  test('batch execution should handle 100 symbols in < 30s', async () => {
    const symbols = Array.from({ length: 100 }, (_, i) => 
      `${String(i).padStart(6, '0')}.${i % 2 === 0 ? 'SH' : 'SZ'}`
    );
    
    const startTime = Date.now();
    
    const result = await batchExecuteStrategy({
      symbols,
      strategy_name: 'Turtle',
      persist: false // 性能测试不持久化
    });
    
    const duration = Date.now() - startTime;
    
    expect(duration).toBeLessThan(30000); // < 30s
    expect(result.summary.total).toBe(100);
    expect(result.summary.success + result.summary.failed).toBe(100);
    
    console.log(`✅ 批量执行 100 只股票耗时: ${duration}ms`);
    console.log(`   平均每只: ${(duration / 100).toFixed(0)}ms`);
  }, 35000);
  
  test('pipeline execution should handle 50 symbols with orders in < 60s', async () => {
    const symbols = Array.from({ length: 50 }, (_, i) => 
      `${String(i).padStart(6, '0')}.SH`
    );
    
    const startTime = Date.now();
    
    const result = await pipelineExecuteStrategy({
      symbols,
      strategy_name: 'Turtle',
      create_orders: true,
      risk_check: true
    });
    
    const duration = Date.now() - startTime;
    
    expect(duration).toBeLessThan(60000); // < 60s
    expect(result.signals_generated).toBeGreaterThan(0);
    
    console.log(`✅ Pipeline 执行 50 只股票耗时: ${duration}ms`);
    console.log(`   生成信号: ${result.signals_generated}`);
    console.log(`   创建订单: ${result.orders_created}`);
  }, 65000);
});
```

- [ ] **Step 2: 运行性能测试**

```bash
npm run test:perf -- strategy-execution-perf.test.ts
```

Expected: PASS (2 tests)

- [ ] **Step 3: 记录性能基准**

```markdown
# Performance Benchmarks

## Strategy Execution

### Batch Mode
- 100 symbols: < 30s (avg ~250ms/symbol)
- Concurrent execution: 10 workers
- Memory usage: < 500MB

### Pipeline Mode
- 50 symbols with orders: < 60s
- Includes: strategy → signal → risk check → order creation
- Database writes: ~150 inserts

### Bottlenecks
- Network I/O: 40%
- Strategy computation: 35%
- Database writes: 20%
- Other: 5%
```

- [ ] **Step 4: 提交**

```bash
git add tests/performance/strategy-execution-perf.test.ts docs/performance/benchmarks.md
git commit -m "test(perf): add strategy execution performance tests"
```

### Task 17: 文档更新

**Files:**
- Modify: `CLAUDE.md`
- Create: `docs/guides/strategy-execution-guide.md`
- Modify: `.pi-invest/bootstrap/TOOLS.md`

- [ ] **Step 1: 更新 TOOLS.md**

```markdown
# .pi-invest/bootstrap/TOOLS.md (修改)

## quant_cli 工具

### strategy.execute - 统一策略执行

**用途**: 执行量化策略，支持单股分析、批量生成、完整流程三种模式。

**参数**:
- `action` (required): 执行模式
  - `single`: 单股快速分析
  - `batch`: 批量信号生成
  - `pipeline`: 完整自动化流程
- `symbol`: 股票代码（single 模式必需）
- `symbols`: 股票代码数组（batch/pipeline 模式必需）
- `strategy`: 策略名称（必需）
- `persist`: 是否持久化（默认 true）
- `min_confidence`: 最低置信度过滤（batch 模式）
- `create_orders`: 是否创建订单（pipeline 模式）
- `risk_check`: 是否风控检查（pipeline 模式，默认 true）

**示例**:
```typescript
// 单股分析
quant_cli({
  command: "strategy.execute",
  params: {
    action: "single",
    symbol: "600519.SH",
    strategy: "Turtle"
  }
})

// 批量生成
quant_cli({
  command: "strategy.execute",
  params: {
    action: "batch",
    symbols: ["600519.SH", "000001.SZ"],
    strategy: "Turtle",
    min_confidence: 0.6
  }
})

// 完整流程
quant_cli({
  command: "strategy.execute",
  params: {
    action: "pipeline",
    symbols: ["600519.SH", "000001.SZ"],
    strategy: "Turtle",
    create_orders: true
  }
})
```

**返回**: 
- single: 单个信号详情（含风控参数）
- batch: 信号列表 + 统计摘要
- pipeline: 执行统计（信号数、订单数、拒绝原因）
```

- [ ] **Step 2: 创建使用指南**

```markdown
# 策略执行使用指南

## 概述

策略执行系统提供三种模式，覆盖从单股分析到完整自动化的所有场景。

## 使用场景

### 场景 1: 快速分析单只股票

**需求**: 分析某只股票是否有交易机会，获取详细的风控参数。

**方案**: 使用 `action='single'`

```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "single",
    symbol: "600519.SH",
    strategy: "Turtle",
    persist: true,
    return_details: true
  }
})
```

**输出**:
- 交易信号（BUY/SELL/HOLD）
- 置信度
- 入场价格、止损价、目标价
- 建议仓位
- 技术指标详情

### 场景 2: 批量筛选交易机会

**需求**: 从股票池中筛选出高置信度的交易信号。

**方案**: 使用 `action='batch'`

```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "batch",
    symbols: ["600519.SH", "000001.SZ", "000002.SZ"],
    strategy: "Turtle",
    min_confidence: 0.7,
    persist: true
  }
})
```

**输出**:
- 信号列表（按置信度排序）
- 统计摘要（BUY/SELL/HOLD 分布）
- 失败记录

### 场景 3: 完全自动化交易

**需求**: 每日自动执行策略、风控检查、创建订单。

**方案**: 使用 `action='pipeline'`

```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "pipeline",
    symbols: stockPool, // 从数据库加载
    strategy: "Turtle",
    create_orders: true,
    risk_check: true
  }
})
```

**输出**:
- 执行统计（生成/通过/拒绝信号数）
- 创建的订单列表
- 风控拒绝原因分布

## 最佳实践

### 1. 默认持久化

所有模式默认 `persist=true`，确保信号追踪链路完整：
```
signal_test_log → orders → strategy_performance
```

### 2. 批量模式使用置信度过滤

```typescript
// 只关注高置信度信号
params: {
  action: "batch",
  min_confidence: 0.7
}
```

### 3. Pipeline 模式先测试后上线

```typescript
// 测试阶段：不创建订单
params: {
  action: "pipeline",
  create_orders: false,
  risk_check: true
}

// 上线阶段：创建订单
params: {
  action: "pipeline",
  create_orders: true,
  risk_check: true
}
```

### 4. 错误处理

所有模式都有错误隔离：
- single: 抛出异常
- batch: 错误记录在 `errors` 数组，不影响其他股票
- pipeline: 错误记录在统计中，继续执行

## 性能优化

### 批量执行

- 并发度: 10 workers
- 建议批次大小: 50-100 只股票
- 超过 100 只建议分批执行

### Pipeline 执行

- 适合日终批处理
- 建议在非交易时段执行
- 监控执行时间，超过 5 分钟需优化
```

- [ ] **Step 3: 提交**

```bash
git add CLAUDE.md .pi-invest/bootstrap/TOOLS.md docs/guides/strategy-execution-guide.md
git commit -m "docs: update strategy execution documentation"
```

---

## 自查清单

### Spec Coverage

- [ ] 所有设计文档中的需求都有对应的实施任务
- [ ] 三种执行模式（single/batch/pipeline）都已实现
- [ ] 默认持久化逻辑已实现
- [ ] NDJSON 流式响应已实现
- [ ] 错误隔离机制已实现
- [ ] 向后兼容层已实现

### Placeholder Scan

```bash
# 检查是否有未完成的占位符
grep -r "TODO\|FIXME\|TBD\|XXX" src/infrastructure/tools/core/quant-cli-tool.ts
grep -r "TODO\|FIXME\|TBD\|XXX" src/infrastructure/quant/quant-v2-client.ts
grep -r "TODO\|FIXME\|TBD\|XXX" quantsys-v2/services/strategy_execution_service.py
```

Expected: No matches

### Type Consistency

- [ ] TypeScript 类型定义与 Python Pydantic 模型一致
- [ ] API 请求/响应格式匹配
- [ ] 枚举值一致（BUY/SELL/HOLD, single/batch/pipeline）
- [ ] 字段命名一致（snake_case in Python, camelCase in TS）

### Test Coverage

```bash
# 后端测试覆盖率
cd quantsys-v2
python -m pytest --cov=services --cov=api --cov-report=term-missing

# 前端测试覆盖率
npm run test:coverage -- quant-cli-tool quant-v2-client formatters
```

Expected: > 80% coverage

### Performance Validation

- [ ] 批量执行 100 只股票 < 30s
- [ ] Pipeline 执行 50 只股票 < 60s
- [ ] 单股执行 < 500ms
- [ ] 内存使用 < 500MB

### Documentation Completeness

- [ ] CLAUDE.md 已更新
- [ ] TOOLS.md 已更新
- [ ] 迁移指南已创建
- [ ] 使用指南已创建
- [ ] API 文档已更新

---

## 执行方式

完成计划编写后，选择执行方式：

1. **Subagent-Driven (推荐)**: 使用 `superpowers:subagent-driven-development`
   - 自动分配任务给专门的 agent
   - 并行执行独立任务
   - 适合大型重构

2. **Inline Execution**: 使用 `superpowers:executing-plans`
   - 主 agent 逐个执行任务
   - 适合需要紧密协调的任务

