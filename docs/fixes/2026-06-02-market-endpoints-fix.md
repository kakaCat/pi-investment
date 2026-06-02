# Market Endpoints Fix - 2026-06-02

## 问题描述

两个 `quant_cli` 命令失败，返回错误：
```
HTTP 503: {"error":"Module not available: No module named 'quantsys'","success":false}
```

受影响的命令：
- `market.margin` - 全市场融资融券余额趋势
- `market.sector_flow` - 行业资金流向排行

## 根本原因

项目已从 quantsys v1 迁移到 quantsys-v2，但以下组件仍在尝试导入旧的 `quantsys.cli` 模块：

1. `api/routes/market.py` - 路由层仍使用 v1 导入
2. `start_all.py` - 启动脚本添加了不存在的 v1 模块路径
3. `api/shared.py` - 缺少 `strategy_repository` 实例定义

## 修复内容

### 1. 创建 v2 原生服务 (`services/market_data_service.py`)

**新建文件**，实现三个核心功能：

#### 1.1 `get_market_margin()` - 融资融券数据
- **数据源**: akshare
  - `ak.stock_margin_sse()` - 上交所（返回历史30天数据）
  - `ak.stock_margin_szse(date=...)` - 深交所（返回当日汇总）
- **返回结构**:
  ```json
  {
    "success": true,
    "data": {
      "sh": [...],  // 上交所数据
      "sz": [...],  // 深交所数据
      "update_time": "2026-06-02T10:00:00"
    }
  }
  ```

#### 1.2 `get_sector_fund_flow()` - 行业资金流向
- **数据源**: 后端 `SectorRotationService`（不依赖 akshare）
- **实现逻辑**:
  1. 获取所有行业列表
  2. 计算行业动量、资金流、相对强度
  3. 使用 `SectorRotation` 引擎计算综合评分
  4. 按评分排序返回
- **返回结构**:
  ```json
  {
    "success": true,
    "data": {
      "period": "即时",
      "industries": [
        {
          "name": "交通运输、仓储和邮政业",
          "code": "",
          "composite_score": 0.85,
          "momentum": 0.82,
          "flow": 0.88,
          "relative_strength": 0.86,
          "rank": 1
        }
      ],
      "total": 50,
      "update_time": "2026-06-02T10:00:00"
    }
  }
  ```

#### 1.3 `get_hot_stocks()` - 热搜股票
- **数据源**: akshare `stock_hot_rank_em()`
- 支持 A股、港股、美股市场

### 2. 修改路由层 (`api/routes/market.py`)

将三个路由从 v1 导入改为 v2 service：

**修改前**:
```python
@market_bp.route('/api/market/margin', methods=['GET'])
@handle_api_error
def get_market_margin_v2():
    try:
        sys.path.insert(0, str(_V2_ROOT.parent / 'quant'))
        from quantsys.cli.market_query import get_market_margin
        result = get_market_margin()
        return api_response(result)
    except ImportError as e:
        return jsonify({'success': False, 'error': f'Module not available: {e}'}), 503
```

**修改后**:
```python
@market_bp.route('/api/market/margin', methods=['GET'])
@handle_api_error
def get_market_margin_v2():
    """全市场融资融券 - v2 原生实现"""
    from services.market_data_service import market_data_service
    result = market_data_service.get_market_margin()
    if not result.get('success', False):
        return jsonify(result), 503
    return api_response(result.get('data', {}))
```

同样修改：
- `get_market_margin_v2()`
- `get_hot_stocks_v2()`
- `get_sector_flow_v2()`

### 3. 修复 `api/shared.py`

添加缺失的 `strategy_repository` 实例：

```python
strategy_repository = StrategyRepository()  # 新增
pool_validation_service = PoolValidationService(
    pool_repo=pool_repo,
    strategy_repo=strategy_repository,  # 使用实例
)
```

**问题**: `combo_backtest_service` 初始化时使用了未定义的 `strategy_repository` 变量，导致启动失败。

### 4. 修复 `start_all.py`

移除对不存在的 v1 模块路径的依赖：

**修改前**:
```python
def run_rest_api():
    load_dotenv()
    
    # Add quant/ to PYTHONPATH for v1 quantsys module imports
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    quant_path = str(project_root / 'quant')
    if quant_path not in sys.path:
        sys.path.insert(0, quant_path)
    
    from api.server import app
    ...
```

**修改后**:
```python
def run_rest_api():
    load_dotenv()
    
    # v2 不再需要 v1 quantsys 模块路径
    # 所有功能已迁移到 v2 原生实现
    
    from api.server import create_app
    app = create_app()
    ...
```

## 测试结果

### 1. market.margin ✅
```bash
curl -s http://127.0.0.1:5001/api/market/margin
```
**结果**:
- Success: `true`
- 上交所数据: 30 条历史记录
- 深交所数据: 当日汇总
- 更新时间: ISO 8601 格式

### 2. market.sector-flow ✅
```bash
curl -s http://127.0.0.1:5001/api/market/sector-flow
```
**结果**:
- Success: `true`
- 行业数量: 50
- 数据来源: 后端 `SectorRotationService`（基于数据库K线数据计算）
- 包含: 行业名称、综合评分、动量、资金流、相对强度、排名

## 架构改进

### Before (v1)
```
quant_cli → HTTP API → Python subprocess → quantsys.cli.market_query (v1)
                                              ↓
                                           akshare
```

### After (v2)
```
quant_cli → HTTP API → services/market_data_service.py (v2)
                         ↓                              ↓
                    akshare (融资融券)    SectorRotationService (资金流向)
                                                      ↓
                                          数据库 (stocks + klines)
```

**优势**:
1. ✅ 无需维护旧的 v1 CLI 包装层
2. ✅ 资金流向数据基于后端真实持仓和K线数据，更准确
3. ✅ 统一使用 v2 架构，减少技术债
4. ✅ 更好的错误处理和日志记录

## 相关文件

- ✅ `quantsys-v2/services/market_data_service.py` (新建)
- ✅ `quantsys-v2/api/routes/market.py` (修改)
- ✅ `quantsys-v2/api/shared.py` (修复)
- ✅ `quantsys-v2/start_all.py` (修复)

## 迁移说明

### 对 TypeScript Agent 的影响

`quant_cli` 工具的以下命令已迁移到 v2 原生实现：
- `market.margin` ✅
- `market.sector_flow` ✅
- `market.hot_stocks` ✅

**无需修改 TypeScript 代码**，HTTP API 接口保持不变。

### 其他待迁移的 market 命令

以下命令仍使用 v1 导入（需要后续迁移）：
- `market.macro` - 宏观数据
- `market.news` - 市场新闻
- `market.concepts` - 概念板块列表
- `market.concept_stocks` - 概念板块成分股
- `market.north_flow` - 北向资金流向
- `market.index_history` - 指数历史K线

## 注意事项

1. **融资融券数据**: 
   - 上交所返回历史数据，深交所仅返回当日汇总
   - akshare API 可能存在数据延迟或格式变化

2. **行业资金流向**:
   - 完全基于后端数据库计算，无外部API依赖
   - 评分算法使用 `SectorRotation` 引擎（动量 + 资金流 + 相对强度）
   - 计算可能耗时较长（需查询数据库K线数据）

3. **服务启动**:
   - 必须使用 `python start_all.py` 或直接启动 `api/server.py`
   - 确保 quantsys-v2 服务运行在 `127.0.0.1:5001`

## 验证步骤

```bash
# 1. 启动服务
cd quantsys-v2
python start_all.py

# 2. 测试 market.margin
curl -s http://127.0.0.1:5001/api/market/margin | python3 -m json.tool

# 3. 测试 market.sector-flow
curl -s http://127.0.0.1:5001/api/market/sector-flow | python3 -m json.tool

# 4. 从 TypeScript Agent 测试
npm run dev
# 在交互界面执行: quant_cli market.margin
# 在交互界面执行: quant_cli market.sector_flow
```

## 完成时间

2026-06-02 10:00 (Beijing Time)
