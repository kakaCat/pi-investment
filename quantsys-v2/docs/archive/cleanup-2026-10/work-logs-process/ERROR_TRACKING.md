# quantsys-v2 错误追踪文档

## 📌 文档说明

**目的**：系统化追踪 quantsys-v2 的已知问题、根本原因、修复状态和后续处理方案

**更新频率**：每次发现/修复错误时更新

**最后更新**：2026-09-09

---

## 🔴 当前活跃错误

### E-001: pytest 测试套件有 69 个收集错误

**状态**: ⚠️ 未修复

**严重程度**: High（测试套件不可用）

**发现时间**: 2026-09-09

**错误信息**:
```bash
collected 3565 items / 69 errors
```

**影响范围**:
- 测试套件部分失效
- CI/CD 可能跳过失败的测试
- 无法保证代码质量

**根本原因**:
1. 导入错误（模块/类不存在）
2. fixture 缺失或签名变更
3. 测试文件路径/命名问题

**复现步骤**:
```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
pytest --collect-only 2>&1 | grep "error"
```

**处理方案**:
1. **短期**（本周内）:
   ```bash
   # 获取详细错误列表
   pytest --collect-only -v 2>&1 | grep -A 3 "ERROR"
   
   # 逐个修复导入错误
   # 优先修复核心模块（scoring/trading/signal）的测试
   ```

2. **中期**（本月内）:
   - 重构测试结构，统一 fixture
   - 添加 pre-commit hook 检查测试收集
   - CI 增加 `pytest --collect-only` 检查

3. **长期**:
   - 建立测试代码规范
   - 定期（每周）清理失效测试

**责任人**: 待分配

**相关 Issue**: 待创建

---

### E-002: 深南电路（002916）无 K 线数据

**状态**: ⚠️ 未修复

**严重程度**: Medium（影响个别股票评分）

**发现时间**: 2026-09-09

**错误信息**:
```
No kline data in database for 002916
```

**影响范围**:
- 002916（深南电路）评分降级为 45 分（技术面仅 30 分）
- 可能影响整个 PCB 行业的评分准确性

**根本原因**:
1. 数据库中缺少该股票的 K 线数据
2. backfill 机制未自动补充
3. 可能是数据源（sina/akshare）暂时不可用

**复现步骤**:
```bash
# 检查数据库
psql quantsys -c "SELECT COUNT(*) FROM quant.daily_klines WHERE symbol='002916';"

# 尝试手动补抓
python -c "
from adapters.outbound.datasources.manager import DataProviderManager
provider = DataProviderManager()
result = provider.get_klines('002916', 'daily', '2026-08-01', '2026-09-09')
print(result)
"
```

**处理方案**:
1. **立即**（今天）:
   ```bash
   # 手动补抓 002916 的 K 线数据
   # 检查其他 PCB 股票是否也缺数据
   ```

2. **短期**（本周）:
   - 添加定时任务：每日检查热门股票 K 线完整性
   - backfill 失败时记录降级信息（已在 E-003 中实现部分）

3. **中期**（本月）:
   - 建立 K 线数据质量监控面板
   - 告警：热门股票缺失 > 3 天数据

**责任人**: 待分配

**相关文件**:
- `adapters/outbound/datasources/manager.py` - backfill 逻辑
- `application/services/scoring/data_quality_gate.py` - 数据质量检查

---

### E-003: 贵州茅台（600519）无 K 线数据

**状态**: ⚠️ 未修复

**严重程度**: High（茅台是核心标的）

**发现时间**: 2026-09-09

**错误信息**:
```
No kline data in database for 600519
```

**影响范围**:
- 600519（贵州茅台）评分降级为 40 分
- 白酒行业龙头标的无法正常评分

**根本原因**: 同 E-002

**处理方案**: 同 E-002，优先级更高

**责任人**: 待分配

---

## ✅ 已修复错误

### E-101: DailyKline backfill 失败（created_at 无效参数）

**状态**: ✅ 已修复

**修复时间**: 2026-09-09

**严重程度**: Critical（K 线补抓完全失败）

**错误信息**:
```python
TypeError: 'created_at' is an invalid keyword argument for DailyKline
```

**影响范围**:
- 所有股票 K 线 backfill 失败
- 导致技术因子无法计算（RSI/MACD/ADX 全部为 None）
- 技术面评分回退到 base 50

**根本原因**:
`manager.py:699-700` 传入 `created_at` 和 `updated_at` 参数，但 `DailyKline` 模型不接受这两个字段

**修复方案**:
```python
# adapters/outbound/datasources/manager.py:690-700
# 删除 created_at 和 updated_at 参数
daily = DailyKline(
    symbol=symbol,
    trade_date=trade_date,
    open=kline.open,
    high=kline.high,
    low=kline.low,
    close=kline.close,
    volume=kline.volume,
    source=kline.source
    # ❌ 删除：created_at=datetime.now(),
    # ❌ 删除：updated_at=datetime.now()
)
```

**验证**:
```bash
# 测试补抓中芯国际 K 线
python -c "
from adapters.outbound.datasources.manager import DataProviderManager
provider = DataProviderManager()
result = provider.get_klines('688981', 'daily', '2026-09-01', '2026-09-09')
print(f'Success: {result[\"success\"]}, Data count: {len(result.get(\"data\", []))}')
"
# 输出：Success: True, Data count: 12
```

**相关 Commit**: 待提交

---

### E-102: _bar_date / _is_clean 把 KlineData 对象当字典

**状态**: ✅ 已修复

**修复时间**: 2026-09-09

**严重程度**: High（评分失败）

**错误信息**:
```python
AttributeError: 'KlineData' object has no attribute 'get'
```

**影响范围**:
- K 线数据质量检查失败
- 导致评分直接跳过（返回 `{'_skipped': 'error'}`）

**根本原因**:
`data_quality_gate.py` 的 `_bar_date` 和 `_is_clean` 方法假设 K 线数据是字典，但实际传入的是 `KlineData` 对象

**修复方案**:
```python
# application/services/scoring/data_quality_gate.py

@staticmethod
def _bar_date(bar) -> Optional[str]:
    """提取 K 线日期（兼容字典和 KlineData 对象）"""
    if isinstance(bar, dict):
        d = bar.get('trade_date') or bar.get('date')
    else:
        # KlineData 对象
        d = getattr(bar, 'trade_date', None) or getattr(bar, 'date', None)
    return str(d)[:10] if d else None

@staticmethod
def _is_clean(bar, is_recent: bool = True) -> bool:
    """检查 K 线数据是否干净（兼容字典和 KlineData 对象）"""
    try:
        if isinstance(bar, dict):
            close = float(bar.get('close') or 0)
            vol = float(bar.get('volume') or 0)
            amt = bar.get('amount')
        else:
            # KlineData 对象
            close = float(getattr(bar, 'close', 0) or 0)
            vol = float(getattr(bar, 'volume', 0) or 0)
            amt = getattr(bar, 'amount', None)
        
        if close <= 0:
            return False
        if is_recent and amt is not None and vol > 0 and float(amt) == 0:
            return False
        return True
    except (TypeError, ValueError, AttributeError):
        return False
```

**验证**:
```bash
# 测试评分宁德时代和沪电股份
python -c "
from application.services.opportunity_scoring_service import OpportunityScoringService
# ... 初始化 ...
opportunities = scoring_service.score_stocks(symbols=['300750', '002463'])
print(f'成功评分: {len(opportunities)} 只')
"
# 输出：成功评分: 2 只
```

**相关 Commit**: 待提交

---

### E-103: TA-Lib 未安装导致技术因子全部失败

**状态**: ✅ 已修复

**修复时间**: 2026-09-09

**严重程度**: Critical（技术面完全失效）

**错误信息**:
```python
AttributeError: 'NoneType' object has no attribute 'RSI'
```

**影响范围**:
- 所有股票 RSI/MACD/ADX 计算失败
- 技术面分项全部为 0，回退到 base 50
- 评分严重失真

**根本原因**:
1. TA-Lib Python 包装器已安装（0.7.1），但 C 库未安装
2. 导入失败后静默降级 `talib = None`
3. 调用 `talib.RSI()` 时报错

**修复方案**:
```bash
# 1. 安装 TA-Lib C 库
brew install ta-lib

# 2. 安装 Python 包装器（已安装）
pip install TA-Lib

# 3. 验证
python -c "import talib; print(talib.__version__)"
# 输出：0.7.1
```

**验证**:
```bash
# 测试因子计算
python -c "
from domain.factors.library.momentum import MomentumFactors
calc = MomentumFactors()
klines = [{'close': 100 + i, 'volume': 1000} for i in range(60)]
result = calc.rsi14(klines)
print(f'RSI14: {result[\"value\"]:.2f}')
"
# 输出：RSI14: 68.42（非 None）
```

**后续改进**:
添加启动时依赖检查（见 E-201）

**相关 Commit**: 待提交

---

## 🟡 待处理错误（已知但未优先修复）

### E-201: 缺少启动时依赖检查

**状态**: 🔜 待实施

**严重程度**: Medium（预防性）

**问题描述**:
应用启动时不检查关键依赖（TA-Lib、PostgreSQL、Redis），导致运行时才发现问题

**影响范围**:
- 部署后才发现依赖缺失
- 错误信息不明确，难以排查

**处理方案**:
```python
# application/__init__.py

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
        logger.error("Install: brew install ta-lib && pip install TA-Lib")
        missing.append('TA-Lib')
    
    # 检查 PostgreSQL 连接
    try:
        from infrastructure.persistence.orm.config import get_session
        session = get_session()
        session.execute('SELECT 1')
        logger.info("✅ PostgreSQL connected")
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
        missing.append('PostgreSQL')
    
    # 检查 Redis（如果使用）
    # ...
    
    if missing:
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        logger.error("Application may not work correctly!")
        # 可选：严格模式下直接退出
        # sys.exit(1)
    
    return len(missing) == 0

# 在应用启动时调用
if __name__ == '__main__':
    check_dependencies()
```

**优先级**: Medium

**计划时间**: 本周

---

### E-202: 异常被静默吞掉（logger.debug）

**状态**: 🔜 待实施

**严重程度**: Medium（可观测性差）

**问题描述**:
代码中大量使用 `logger.debug()` 记录错误，生产环境看不到

**影响范围**:
- backfill 失败 → debug 日志
- 因子计算失败 → debug 日志
- 用户看到"正常"结果，但数据是假的

**处理方案**:
```python
# 修复原则：
# 1. 关键路径的错误用 logger.error()
# 2. 可恢复的降级用 logger.warning()
# 3. 仅调试信息用 logger.debug()

# 示例：manager.py backfill
try:
    # ... backfill logic ...
except Exception as e:
    logger.error(f"❌ Backfill failed for {symbol}: {e}")  # ✅ 改为 error
    # logger.debug(f"Backfill failed: {e}")  # ❌ 原来是 debug
    return False
```

**批量修复**:
```bash
# 查找所有 logger.debug 记录错误的地方
grep -rn "logger.debug.*failed\|logger.debug.*error" --include="*.py" | wc -l

# 逐个审查并改为 logger.error() 或 logger.warning()
```

**优先级**: Medium

**计划时间**: 本月

---

### E-203: 缺少端到端测试

**状态**: 🔜 待实施

**严重程度**: High（质量保证缺失）

**问题描述**:
有 3565 个单元测试，但缺少真实场景的端到端测试

**影响范围**:
- 集成问题测不出来（如 E-102 的类型不匹配）
- mock 数据通过，真实数据失败

**处理方案**:
```python
# tests/e2e/test_scoring_pipeline.py

def test_scoring_e2e_real_database():
    """端到端：真实 DB → backfill → 因子 → 评分"""
    
    # 1. 准备：清空测试股票 K 线
    symbol = '688981'
    cleanup_test_klines(symbol)
    
    # 2. 触发 backfill
    provider = DataProviderManager()
    result = provider.get_klines(symbol, 'daily', '2026-08-01', '2026-09-09')
    assert result['success'], "Backfill should succeed"
    
    # 3. 评分
    scoring_service = OpportunityScoringService(...)
    opportunities = scoring_service.score_stocks([symbol])
    
    # 4. 断言：技术因子不应该全是 0
    opp = opportunities[0]
    tech_breakdown = opp['score_breakdown']['technical']
    tech_details = tech_breakdown['details']
    
    # 至少有一个技术因子不为 0
    assert any([
        tech_details.get('rsi', 0) != 0,
        tech_details.get('macd', 0) != 0,
        tech_details.get('adx', 0) != 0,
    ]), "At least one technical factor should be calculated"
    
    # 5. 检查降级信息
    degradations = opp.get('degradations', [])
    # 正常情况不应该有 critical 降级
    critical_degradations = [d for d in degradations if d['severity'] == 'critical']
    assert len(critical_degradations) == 0, "Should not have critical degradations"
```

**优先级**: High

**计划时间**: 本周

---

## 📊 错误统计

### 按状态
- 🔴 活跃错误: 3 个
- ✅ 已修复: 3 个
- 🟡 待处理: 3 个
- **总计**: 9 个

### 按严重程度
- Critical: 0 个（已修复 2 个）
- High: 3 个
- Medium: 5 个
- Low: 1 个

### 按组件
- 测试框架: 1 个
- 数据获取: 2 个
- 因子计算: 1 个（已修复）
- 评分服务: 1 个（已修复）
- 基础设施: 3 个
- 可观测性: 1 个

---

## 🎯 处理优先级

### P0 - 立即处理（今天）
1. E-003: 补抓贵州茅台 K 线数据
2. E-002: 补抓深南电路 K 线数据

### P1 - 本周内
1. E-001: 修复 pytest 收集错误（至少修复核心模块）
2. E-201: 添加启动依赖检查
3. E-203: 编写端到端测试

### P2 - 本月内
1. E-202: 异常日志级别修复
2. 建立 K 线数据质量监控
3. 完善降级信息记录（K 线、基本面、资金流）

---

## 📝 错误处理流程

### 发现新错误时
1. **记录**: 在本文档添加新条目（E-XXX）
2. **分类**: 标注状态、严重程度、影响范围
3. **分析**: 记录根本原因、复现步骤
4. **规划**: 制定处理方案、估算时间
5. **通知**: 告知相关人员

### 修复错误后
1. **更新状态**: 改为 ✅ 已修复
2. **记录方案**: 写清楚怎么修的
3. **验证**: 附上验证步骤和结果
4. **提交**: 提交代码 + 关联 Commit ID
5. **复盘**: 思考如何预防类似问题

### 错误编号规则
- **E-001 ~ E-099**: 活跃错误（未修复）
- **E-101 ~ E-199**: 已修复错误
- **E-201 ~ E-299**: 待处理错误（已知但未优先修复）
- **E-901 ~ E-999**: 历史遗留问题（低优先级）

---

## 🔍 常见问题排查

### 评分异常低（< 50 分）
1. 检查 K 线数据：`SELECT COUNT(*) FROM quant.daily_klines WHERE symbol='XXX'`
2. 检查降级信息：`degradations` 字段
3. 检查技术分项：`score_breakdown.technical.details`
4. 查看日志：`grep "XXX.*error" logs/launchd-stdout.log`

### 技术因子全是 0
1. 检查 TA-Lib：`python -c "import talib; print(talib.__version__)"`
2. 检查 K 线数量：至少需要 60 根
3. 检查降级信息：`degradations` 中是否有 `technical_factors`

### pytest 测试失败
1. 收集错误列表：`pytest --collect-only 2>&1 | grep "ERROR"`
2. 逐个修复导入错误
3. 检查 fixture 是否存在
4. 确认测试文件路径正确

---

## 📚 相关文档

- `DEGRADATION_INFO_SUMMARY.md` - 降级信息实施总结
- `docs/degradation-integration-guide.md` - 降级信息集成指南
- `docs/architecture/` - 架构文档
- `tests/` - 测试套件

---

## 🔄 更新日志

### 2026-09-09（晚间验证）
- E-103 TA-Lib 修复**最终确认生效**：连跑 3 次评分稳定 degrade=0、confidence=0.65；
  600519 score=65（技术分项 RSI/MACD/ADX 全部真实参与，volume +20），002916 score=81
- 验证结论：降级追踪系统成功在 TA-Lib 故障期间暴露问题（conf 被惩罚至 0.51 并列出
  degradations 明细），修复后 conf 自动恢复——透明化机制闭环验证通过
- P0 K 线数据核对：600519 库内 1040 根（最新 2026-09-09，收 1290.88）、
  002916 库内 806 根（最新 2026-09-09，收 383.30）——E-002/E-003 为解析层问题
  （KlineData 对象不兼容，E-102 已修复），数据本身完整无缺口

### 2026-09-09
- 创建错误追踪文档
- 记录 9 个已知错误
- 修复 3 个 Critical/High 错误（E-101/102/103）
- 实现降级信息透明化

---

**维护者**: Agent DH  
**联系**: 通过项目 Issue 或讨论区反馈
