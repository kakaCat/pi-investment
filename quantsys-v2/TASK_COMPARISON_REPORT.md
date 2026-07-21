# daily-data-update vs 每日数据更新 对比报告

**日期**: 2026-07-17 20:13  
**分析人**: Claude (Kiro)

---

## 📊 任务对比

### 配置对比

| 项目 | daily-data-update (旧) | 每日数据更新 (新) |
|------|----------------------|----------------|
| **任务名** | daily-data-update | 每日数据更新 |
| **语言** | 英文 | 中文 |
| **command** | data_update | data_update |
| **module** | N/A | N/A |
| **function** | N/A | N/A |
| **params** | {} | {} |
| **启用状态** | ❌ False | ✅ True |
| **最后执行** | 2026-07-03 15:11 | 2026-07-16 23:30 |

---

## 🔍 业务逻辑对比

### 实际执行的代码

两个任务都执行同一个命令 `data_update`，对应：

```python
# infrastructure/scheduler/scheduler.py

def _handle_data_update(self, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新市场数据（K线数据获取）
    
    功能：
    1. 获取股票列表（如果未指定symbols）
    2. 过滤掉停牌股票
    3. 并行更新每只股票的K线数据（8个worker）
    4. 返回更新结果统计
    
    参数：
    - market: 可选，市场过滤（如 "A", "HK"）
    - symbols: 可选，要更新的股票列表
    
    返回：
    - symbols_checked: 检查的股票数量
    - symbols_updated: 成功更新的数量
    - errors: 错误数量
    """
```

### 核心逻辑

```python
# 1. 获取股票列表
if not symbols:
    stocks = self.ds.stock.get_all(market=market)
    symbols = [s["symbol"] for s in stocks if not s.get("is_suspended", False)]

# 2. 并行更新
with ThreadPoolExecutor(max_workers=8) as executor:
    for symbol in symbols:
        latest = self.ds.kline.get_latest_daily_kline(symbol)
        # 更新K线数据

# 3. 统计结果
return {
    "symbols_checked": len(symbols),
    "symbols_updated": updated,
    "errors": errors,
}
```

---

## ✅ 结论

### 业务逻辑完全一致 ✅

| 对比项 | 结果 |
|--------|------|
| **执行的命令** | ✅ 相同 (data_update) |
| **调用的函数** | ✅ 相同 (_handle_data_update) |
| **业务逻辑** | ✅ 完全一致 |
| **参数** | ✅ 相同 (都是空参数{}) |
| **功能** | ✅ 都是更新K线数据 |

### 唯一区别

**只有任务名不同**：
- 旧任务：`daily-data-update` (英文)
- 新任务：`每日数据更新` (中文)

---

## 🎯 建议

### ✅ 可以安全废弃 daily-data-update

**理由**：

1. **功能完全重复**
   - 两个任务执行同一个命令
   - 业务逻辑100%一致
   - 参数完全相同

2. **新任务正常运行**
   - `每日数据更新` 启用中
   - 最后执行：昨天23:30
   - 状态：成功

3. **旧任务已废弃**
   - `daily-data-update` 已禁用
   - 最后执行：2周前
   - 不再使用

### 🔧 清理步骤

可以安全删除 `daily-data-update`：

```bash
# 方式1: 通过API删除
curl -X DELETE http://127.0.0.1:5001/api/scheduler/tasks/daily-data-update

# 方式2: 直接从数据库删除
DELETE FROM scheduler_tasks WHERE task_name = 'daily-data-update';
```

---

## 📋 系统迁移记录

### 任务命名迁移

**旧系统（英文命名）**:
- daily-data-update
- weekly-report  
- weekly-risk-check
- weekly_financial_update

**新系统（中文命名）**:
- 每日数据更新 ✅ (替代 daily-data-update)
- 每日因子计算 ✅
- 每日信号执行 ✅
- v13-simulation-trading ✅

### 迁移状态

| 旧任务 | 新任务 | 状态 |
|--------|--------|------|
| daily-data-update | 每日数据更新 | ✅ 已完成 |
| weekly-report | ？ | ❓ 未完成 |
| weekly-risk-check | ？ | ❓ 未完成 |
| weekly_financial_update | ？ | ❓ 未完成 |

---

## 总结

**daily-data-update vs 每日数据更新**:

✅ **业务逻辑完全一致**
- 执行相同的命令
- 调用相同的函数
- 功能100%重复

✅ **可以安全废弃旧任务**
- 新任务正常运行
- 旧任务已禁用2周
- 无任何依赖

**建议行动**: 删除 `daily-data-update` 任务配置，保留 `每日数据更新`
