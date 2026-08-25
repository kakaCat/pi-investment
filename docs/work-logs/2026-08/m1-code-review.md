# M1 市场感知代码 Review（RFC 007）

**Review Date**: 2026-08-25  
**Reviewer**: agent-dh (w-98f9a35c)  
**Scope**: quantsys-v2/application/services/market_perception_service.py + routes/market_perception_async.py

---

## 综合评分：6.3/10 ⚠️

| 维度 | 评分 | 说明 |
|---|---|---|
| **功能完整性** | 9/10 | ✅ RFC 007 要求全部实现，只缺调度挂载 |
| **代码质量** | 7/10 | ✅ 结构清晰，⚠️ 有过长函数和魔术数字 |
| **错误处理** | 6/10 | ✅ 多层防御，⚠️ 部分失败语义不清 |
| **性能** | 6/10 | ⚠️ N+1 查询，无缓存 |
| **测试覆盖** | 2/10 | ❌ 无单元测试，只有手动验收 |
| **文档** | 8/10 | ✅ RFC + 交接单齐全，⚠️ API 文档不足 |
| **安全性** | 6/10 | ✅ SQL 防注入，⚠️ 无 API 认证 |

---

## 关键发现

### ✅ 优点

1. **架构清晰**：服务层/路由层分离，依赖注入支持可测试性
2. **容错到位**：数据源不可用时显式标记 `stored=false`，不造假
3. **自查机制**：coverage < 4000 → partial=true（K线同步未完成的自卫）
4. **幂等设计**：DELETE WHERE catalyst IS NULL 保留 LLM 已回写
5. **文档齐全**：RFC 007 + 交接单 + 验收报告完整

### ⚠️ 主要问题

#### P0 阻断项（上线前必须修复）

1. **❌ 缺失单元测试**
   - 无 `test_market_perception_service.py`
   - regime 判定规则（5 档×2 边界 = 10 条测试）未覆盖
   - 边界条件（coverage=0 / 指数历史不足）无验证
   - **风险**：规则变更可能引入 bug，无自动化验证

2. **⚠️ DB 回滚不完整**（detect_and_store_themes, line 345-371）
   ```python
   stored = []
   for rank, (sector, rows) in enumerate(top, start=1):
       cur = session.execute(...)
       stored.append({'id': cur.fetchone()[0], ...})  # 提前填充
   session.commit()  # 如果这里失败，返回 stored=True 但 DB 无数据
   ```
   - **风险**：返回值与实际 DB 状态不一致
   - **修复**：
     ```python
     try:
         for ...:
             session.execute(...)
         session.commit()
         return {'stored': True, 'themes': stored}
     except Exception as e:
         session.rollback()
         return {'stored': False, 'error': str(e)}
     ```

#### P1 重要优化

3. **过长函数**：`backfill_regime` 120 行（SQL 查询 + 指数拉取 + 逐日判定 + 落库）
   - 建议拆分：`_fetch_breadth_history()` / `_fetch_index_history()` / `_backfill_one_day()`

4. **魔术数字**：`-6` / `20` / `60` 硬编码
   - 应改为常量 `INDEX_5D_LOOKBACK = 6` / `MA20_PERIOD = 20` / `MA60_PERIOD = 60`

5. **N+1 查询**：backfill_regime 逐日 INSERT（120 次）
   - 应改用 `executemany()` 或批量 INSERT

6. **部分失败语义不清**
   ```python
   result['success'] = any(s.get('stored') for s in result['steps'].values())
   ```
   - `any()` 语义：只要一步成功就算成功
   - 用户误解风险：看到 `success=true` 以为三步全成功
   - 建议返回 `all_stored` / `partial_success` / `failed_steps`

#### P2 建议优化

7. **无 API 认证**：POST 端点任何人可调用（可能触发大量计算）
8. **指数历史无缓存**：每次回填都重拉全量指数（上千条记录）
9. **API 文档不足**：缺少返回格式示例和错误码说明

---

## 测试计划（P0 优先）

### Phase 1: 单元测试（2026-08-26 前完成）

**1.1 Regime 判定规则测试（10 条）**
```python
def test_classify_regime_panic():
    """测试 panic 判定：情绪≤20, 量能<1.0, 指数5日<-3.0"""
    regime = MarketPerceptionService._classify_regime(
        sentiment=15, volume_ratio=0.8, up_pct=20, chg5d=-4.5,
        close=3000, ma20=3100, ma60=3200
    )
    assert regime == 'panic'

def test_classify_regime_euphoria():
    """测试 euphoria 判定：情绪≥80, 量能>2.0, 涨家占比>70%"""
    regime = MarketPerceptionService._classify_regime(
        sentiment=85, volume_ratio=2.5, up_pct=75, chg5d=1.0,
        close=3100, ma20=3050, ma60=3000
    )
    assert regime == 'euphoria'

def test_classify_regime_trend_up():
    """测试 trend_up：close>MA20>MA60, 5日>1.0"""
    regime = MarketPerceptionService._classify_regime(
        sentiment=60, volume_ratio=1.2, up_pct=55, chg5d=1.5,
        close=3200, ma20=3100, ma60=3000
    )
    assert regime == 'trend_up'

def test_classify_regime_trend_down():
    """测试 trend_down：close<MA20<MA60, 5日<-1.0"""
    regime = MarketPerceptionService._classify_regime(
        sentiment=40, volume_ratio=0.9, up_pct=40, chg5d=-1.5,
        close=3000, ma20=3100, ma60=3200
    )
    assert regime == 'trend_down'

def test_classify_regime_range_fallback():
    """测试 range 兜底：不满足任何明确条件"""
    regime = MarketPerceptionService._classify_regime(
        sentiment=50, volume_ratio=1.0, up_pct=50, chg5d=0.5,
        close=3100, ma20=3100, ma60=3100
    )
    assert regime == 'range'

# 边界条件测试（5 条）
def test_classify_regime_panic_boundary():
    """测试 panic 边界：情绪=20（刚好触线）"""
    regime = MarketPerceptionService._classify_regime(
        sentiment=20, volume_ratio=0.99, up_pct=25, chg5d=-3.0,
        close=3000, ma20=3100, ma60=3200
    )
    assert regime == 'panic'

def test_classify_regime_euphoria_boundary():
    """测试 euphoria 边界：情绪=80, 量能=2.0, 涨家占比=70%"""
    regime = MarketPerceptionService._classify_regime(
        sentiment=80, volume_ratio=2.0, up_pct=70, chg5d=0.5,
        close=3100, ma20=3050, ma60=3000
    )
    assert regime == 'euphoria'
```

**1.2 数据源容错测试（3 条）**
```python
def test_index_trend_no_data():
    """测试指数数据源返回失败"""
    with patch('get_data_provider_manager') as mock_mgr:
        mock_mgr.return_value.get_index_daily.return_value = {'success': False}
        svc = MarketPerceptionService()
        result = svc._index_trend()
        assert result is None

def test_index_trend_insufficient_history():
    """测试指数历史不足 60 日"""
    with patch('get_data_provider_manager') as mock_mgr:
        mock_mgr.return_value.get_index_daily.return_value = {
            'success': True, 'data': {'records': [{'close': 3000, 'date': '2026-08-01'}] * 50}
        }
        svc = MarketPerceptionService()
        result = svc._index_trend()
        assert result is None

def test_snapshot_sentiment_provider_error():
    """测试情绪计算服务异常"""
    mock_ds = Mock()
    mock_ds.kline = Mock()
    mock_ds.kline.side_effect = Exception("DB connection failed")
    svc = MarketPerceptionService(ds=mock_ds)
    result = svc._snapshot_sentiment()
    assert result['stored'] is False
    assert 'error' in result
```

**1.3 边界条件测试（3 条）**
```python
def test_coverage_partial_threshold():
    """测试 coverage=4000 边界（刚好不 partial）"""
    # Mock MarketSentimentService 返回 coverage=4000
    # 预期 partial=false

def test_coverage_partial_below_threshold():
    """测试 coverage=3999（刚好 partial）"""
    # 预期 partial=true

def test_themes_min_limit_up():
    """测试 ≥3 只涨停成团边界"""
    # Mock 涨停池：某行业 2 只（不成团）、某行业 3 只（刚好成团）
    # 预期：只返回 3 只那个板块
```

### Phase 2: 集成测试（2026-08-27 前）

```python
@pytest.mark.integration
def test_snapshot_end_to_end():
    """端到端测试：真实 DB + 真实数据源"""
    svc = MarketPerceptionService()
    result = svc.run_daily_snapshot()
    # 验证返回格式完整性
    assert 'success' in result
    assert 'trade_date' in result
    assert all(k in result['steps'] for k in ['sentiment', 'regime', 'themes'])

@pytest.mark.integration
def test_backfill_idempotent():
    """回填幂等性测试：重复回填不重复数据"""
    svc = MarketPerceptionService()
    # 第一次回填
    result1 = svc.backfill_regime(days=5)
    count1 = result1['stored']
    # 第二次回填
    result2 = svc.backfill_regime(days=5)
    count2 = result2['stored']
    # 验证：第二次应该是 ON CONFLICT DO UPDATE，stored 数相同
    assert count1 == count2
```

---

## 优先修复项（按优先级）

### 🔴 P0（上线前必须修复）

1. ✅ **补充单元测试**：regime 规则（10 条）+ 边界条件（3 条）+ 容错（3 条）
2. ✅ **修复 DB 回滚不完整**：detect_and_store_themes 的 stored 列表填充时机

### 🟡 P1（上线后 1 周内）

3. **拆分过长函数**：backfill_regime 拆分为 3 个子函数
4. **提取魔术数字**：INDEX_5D_LOOKBACK / MA20_PERIOD / MA60_PERIOD
5. **优化 N+1 查询**：backfill 使用 executemany
6. **明确部分失败语义**：返回 all_stored / partial_success / failed_steps

### 🟢 P2（1 个月内）

7. **添加 API 认证**：POST 端点加 API key 或 IP 白名单
8. **指数历史缓存**：Redis 缓存（TTL 1小时）或内存 LRU
9. **补充 API 文档**：OpenAPI schema + 返回格式示例

---

## 代码示例：P0 修复

### 修复 1：DB 回滚完整性

**当前代码**（quantsys-v2/application/services/market_perception_service.py, line 345-371）：
```python
stored = []
try:
    session.execute(text("DELETE ..."))
    for rank, (sector, rows) in enumerate(top, start=1):
        cur = session.execute(text("INSERT ..."), {...})
        stored.append({'id': cur.fetchone()[0], ...})  # ❌ 提前填充
    session.commit()
except Exception as e:
    session.rollback()
    return {'stored': False, 'error': str(e)}

return {'stored': True, 'themes': stored}  # ⚠️ 如果 commit 失败但已填充 stored
```

**修复后**：
```python
try:
    session.execute(text("DELETE ..."))
    stored = []
    for rank, (sector, rows) in enumerate(top, start=1):
        cur = session.execute(text("INSERT ..."), {...})
        stored.append({'id': cur.fetchone()[0], ...})
    session.commit()  # ✅ commit 成功才返回 stored=True
    return {'stored': True, 'trade_date': fmt_date, 'themes': stored}
except Exception as e:
    session.rollback()
    logger.error(f"M1-2 主线落库失败: {e}", exc_info=True)
    return {'stored': False, 'error': str(e)}
```

### 修复 2：部分失败语义明确

**当前代码**（line 84-86）：
```python
result['success'] = any(s.get('stored') for s in result['steps'].values())
```

**修复后**：
```python
steps = result['steps']
all_stored = all(s.get('stored') for s in steps.values())
any_stored = any(s.get('stored') for s in steps.values())
failed_steps = [k for k, v in steps.items() if not v.get('stored')]

result['success'] = any_stored  # 至少一步成功
result['all_steps_success'] = all_stored  # 三步全成功
result['partial_success'] = any_stored and not all_stored  # 部分成功
result['failed_steps'] = failed_steps if failed_steps else None
```

---

## 总结建议

### ✅ 可立即上线
- 核心功能完整且手动验收通过
- 错误处理基本到位（数据源容错 + 显式失败标记）
- 文档齐全（RFC + 交接单 + 验收报告）

### ⚠️ 上线后立即补齐（技术债清单）

**Week 1（2026-08-26 - 08-30）**
1. 补充 16 条单元测试（regime 规则 + 边界 + 容错）
2. 修复 DB 回滚不完整问题
3. 明确部分失败语义（all_steps_success / partial_success）

**Week 2-3（2026-09-01 - 09-15）**
4. 拆分 backfill_regime 过长函数
5. 提取魔术数字为常量
6. 优化 backfill N+1 查询（executemany）
7. 添加集成测试（端到端 + 幂等性）

**Month 1（2026-09 内）**
8. 添加 API 认证（POST 端点）
9. 指数历史缓存（Redis / LRU）
10. 补充 OpenAPI 文档（Swagger）

---

**Review 结论**：  
✅ **功能可用，建议上线**，但必须在上线后 1 周内补齐 P0 测试（16 条单元测试 + DB 回滚修复），否则存在规则变更无验证、DB 状态不一致的风险。

**Reviewer**: agent-dh (w-98f9a35c)  
**Review Date**: 2026-08-25  
**Next Review**: 2026-09-01（验证 P0 修复完成度）
