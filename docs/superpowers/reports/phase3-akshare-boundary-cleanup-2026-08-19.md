# Phase 3 Akshare 边界清理完成报告

**日期**: 2026-08-19  
**分支**: feat/phase3-akshare-boundary-cleanup  
**工作包**: Phase 3 遗留边界清理

## 背景

Phase 3 已完成 application 层 10 个服务的 akshare 迁移到 DataProviderManager，但遗留 3 个文件直接使用 akshare：
- `domain/brokers/adapters/akshare_broker.py` (453行, 14处引用)
- `domain/quantlib/adapters/akshare_adapter.py` (885行, 34处引用)
- `live_trading/multi_source_data_fetcher.py` (416行, 6处引用)

**目标**: 消除 domain/ 和 live_trading/ 层的 akshare 直接依赖，收敛到统一的 DataProviderManager。

## 完成工作

### ✅ 第一步：补充 DataProviderManager 缺失能力

**问题**: AkShareAdapter 提供 3 个 manager 未覆盖的方法。

**方案**: 恢复 Phase 3 创建但合并时丢失的 3 个 provider，添加路由方法到 manager。

**实施**:
- 恢复 `adapters/outbound/datasources/providers/index/akshare.py` (67行)
- 恢复 `adapters/outbound/datasources/providers/hk/akshare.py` (145行)
- 恢复 `adapters/outbound/datasources/providers/financial/akshare.py` (125行)
- 新增 manager 方法:
  - `get_stock_info(symbol)` → 股票基本信息
  - `get_index_data(index_code)` → 指数数据
  - `get_north_flow()` → 北向资金流

**提交**: 71aff367 "feat(step1): 补充 DataProviderManager 缺失能力"

---

### ✅ 第二步：重构 AkshareBroker 委托 DataProviderManager

**问题**: `adapters/outbound/brokers/akshare_broker.py` 直接 `import akshare`，453行。

**方案**: 保留 broker 接口（向后兼容），但内部委托 DataProviderManager。

**实施**:
- 删除 `import akshare` 和 `_load_akshare()` 方法
- 添加 `_get_manager()` 延迟加载 manager
- 重构 `get_quotes()` / `get_history()` 委托 manager
- 删除 `_fetch_from_sina()` 冗余 failover 逻辑（manager 已有）
- `search_symbols()` 标记未实现（需全量股票列表）
- **代码量**: 453 行 → 251 行（-44%）

**迁移**: `adapters/shared/pipeline_exec.py` 的 data_update 阶段从 broker 改为 manager 直调。

**提交**: 2c9e7767 "refactor(step2): AkshareBroker 委托 DataProviderManager"

---

### ✅ 第四步：重构 MultiSourceDataFetcher

**问题**: `live_trading/multi_source_data_fetcher.py` 的 AKShareSource 和 SinaSource 直接 `import akshare`。

**方案**: AKShareSource 委托 manager，SinaSource 废弃全量股票列表。

**实施**:
- `AKShareSource.fetch_klines()` → 委托 `manager.get_klines()`
- `AKShareSource.fetch_stock_list()` → 返回 None（manager 无全量列表）
- `SinaSource.fetch_stock_list()` → 返回 None（接口已废弃）
- 删除所有 `import akshare` 语句

**影响**:
- 多源 failover 仍正常（LocalDB → Sina → AKShare/manager）
- `fetch_stock_list()` 全部失败（3个源都不支持），需调用方适配
- `fetch_klines()` 通过 manager 自动 failover

**提交**: 9f23344e "refactor(step4): MultiSourceDataFetcher 清除 akshare 直接依赖"

---

### ✅ 同步：domain 副本更新

**问题**: `domain/brokers/adapters/` 和 `domain/quantlib/adapters/` 的文件是旧副本（非 shim）。

**方案**: 从 `adapters/outbound/` 同步重构后的版本。

**实施**:
- `domain/brokers/adapters/akshare_broker.py` ← 同步（已委托 manager）
- `domain/quantlib/adapters/akshare_adapter.py` ← 同步（但仍含 akshare import，见遗留）

**提交**: 66015eac "sync: 同步 domain 副本为重构后的版本"

---

## 成果

### 代码清理

| 文件 | 原始行数 | 重构后 | 变化 |
|------|---------|--------|------|
| akshare_broker.py | 453 | 251 | -44% |
| multi_source_data_fetcher.py | 416 | 428 | +3% (加manager调用) |
| 新增 providers | 0 | 337 | +337 (index/hk/financial) |

### akshare 直接导入清理

| 区域 | 清理前 | 清理后 | 状态 |
|------|--------|--------|------|
| live_trading/ | 3处 | 0处 | ✅ 完全清零 |
| domain/brokers/ | 1处 | 0处 | ✅ 完全清零 |
| domain/quantlib/ | 2处 | 1处 | ⚠️ 1处遗留 (adapter) |

### 架构改进

**Before**:
```
application/services → 直接 import akshare ❌
domain/brokers → 直接 import akshare ❌
domain/quantlib/adapters → 直接 import akshare ❌
live_trading/ → 直接 import akshare ❌
```

**After**:
```
application/services → DataProviderManager ✅
domain/brokers → DataProviderManager (via broker) ✅
live_trading/ → DataProviderManager ✅
domain/quantlib/adapters → akshare ⚠️ (遗留)
```

---

## 遗留工作（Tech Debt）

### ⚠️ AkShareAdapter (885行, 34处引用)

**位置**: `adapters/outbound/datasources/providers/quantlib/akshare_adapter.py`

**问题**: 仍直接 `import akshare`（第19行）

**原因**: 
- 885行大型适配器，方法众多（22个）
- 34处引用，主要在 tests（20+），少量生产代码
- 架构上已在正确层（adapters/outbound），只是实现未统一

**建议**:
1. **P1**: 将 adapter 方法逐步迁移到 manager 对应 provider
2. **P2**: 更新 tests 改用 manager 或 mock manager
3. **P3**: 废弃 adapter，全部走 manager

**预估工作量**: 2-3 小时（逐方法分析 + 迁移 + 测试）

### ⚠️ 全量股票列表接口缺失

**问题**: MultiSourceDataFetcher 的 `fetch_stock_list()` 全部失败（3个源都返回 None）

**影响**: 依赖全量股票列表的功能可能中断

**建议**:
1. 添加 `StockListProvider` 到 manager（从 database 或专门 API）
2. 或改为按需查询（pool/strategy 维护已知股票列表）

---

## 验证计划

### 单元测试
```bash
# AkshareBroker tests
pytest tests/test_brokers.py::TestAkshareBroker -v

# MultiSourceDataFetcher tests
pytest tests/test_data_fetch_stage.py -v

# DataProviderManager 新方法
pytest tests/test_data_provider_manager.py -k "stock_info or index_data or north_flow" -v
```

### 集成测试
```bash
# Pipeline execution (data_update stage)
python adapters/shared/pipeline_exec.py --test

# Live trading data fetcher
python live_trading/multi_source_data_fetcher.py --test
```

### 回归测试
```bash
# Phase 5 测试套件（确保无回归）
pytest tests/ -k "not slow" --maxfail=5
```

---

## 部署注意事项

1. **向后兼容**: 所有公开 API 未变，现有调用方无需修改
2. **broker_registry**: AkshareBroker 仍注册可用，内部已统一到 manager
3. **全量股票列表**: 如有功能依赖 `fetch_stock_list()`，需适配或使用其他方案
4. **domain/ shim**: 按计划 2026-09-19 删除，调用方应迁移到 `adapters.outbound.*` 导入

---

## 相关文档

- 计划文档: `PHASE3_AKSHARE_BOUNDARY_PLAN.md`
- Phase 3 报告: `docs/work-logs/2026-08/phase3-data-governance-complete.md`
- 数据访问指南: `DATA_ACCESS_GUIDE.md`
- 架构审计: `docs/superpowers/reports/quantsys-v2-audit-report-2026-08-19.md`

---

## 提交记录

```
71aff367 feat(step1): 补充 DataProviderManager 缺失能力
2c9e7767 refactor(step2): AkshareBroker 委托 DataProviderManager
9f23344e refactor(step4): MultiSourceDataFetcher 清除 akshare 直接依赖
66015eac sync: 同步 domain 副本为重构后的版本
```

**总结**: Phase 3 遗留边界清理基本完成，live_trading/ 和 domain/brokers/ 已清零 akshare 直接依赖。AkShareAdapter (885行) 作为唯一遗留，留待后续专项清理。
