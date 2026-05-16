# 超时修复总结

## ✅ 已完成的修复

### 1. Python Bridge 层 (90秒最大超时)
**文件**: `src/infrastructure/tools/python-bridge.ts`
- 从 120秒 降低到 90秒
- 作为最大超时上限，实际由调用层控制

### 2. TypeScript 调用层 (分级超时)
**文件**: `src/infrastructure/tools/shared/python-caller-resilient.ts`
- **快速接口**: 15秒 (实时行情、市场概览)
- **中速接口**: 35秒 (资金流向、技术指标、龙虎榜)
- **慢速接口**: 55秒 (宏观数据、市场新闻)

### 3. Python 函数层 (函数级超时)
**文件**: `python/akshare_bridge.py`

添加了超时装饰器并应用到慢速函数：
- `@timeout_decorator(seconds=50)` → `get_macro_data`
- `@timeout_decorator(seconds=50)` → `get_market_news`
- `@timeout_decorator(seconds=40)` → `get_lhb`
- `@timeout_decorator(seconds=30)` → `get_stock_fund_flow`
- `@timeout_decorator(seconds=30)` → `get_announcements`
- `@timeout_decorator(seconds=30)` → `get_sector_fund_flow`

## 📊 改善效果

| 接口 | 修复前 | 修复后 | 改善 |
|------|--------|--------|------|
| 宏观数据 | 120秒 | 55秒 | ⬇️ 54% |
| 市场新闻 | 120秒 | 55秒 | ⬇️ 54% |
| 资金流向 | 120秒 | 35秒 | ⬇️ 71% |
| 龙虎榜 | 120秒 | 40秒 | ⬇️ 67% |

## 🛡️ 降级机制

1. **TypeScript 原生优先**: 优先使用 `akshare-ts`
2. **降级缓存**: 失败时使用 7 天内的旧数据
3. **备选方案提示**: 返回错误时提供替代工具建议

## 🧪 测试方法

### Python 端测试
```bash
python3 test-python-timeout.py
```

### 完整集成测试
```bash
node test-timeout-fix.js
```

## 📝 修改的文件

1. ✅ `src/infrastructure/tools/python-bridge.ts`
2. ✅ `src/infrastructure/tools/shared/python-caller-resilient.ts`
3. ✅ `python/akshare_bridge.py`
4. ✅ `test-python-timeout.py` (新增)
5. ✅ `test-timeout-fix.js` (新增)
6. ✅ `docs/timeout-fix-2026-05-16.md` (新增)

## 🎯 核心改进

### 超时层级设计
```
TypeScript 调用层 (15s/35s/55s)
         ↓
Python Bridge 层 (90s 最大上限)
         ↓
Python 函数层 (30s/40s/50s)
         ↓
网络请求层 (10s + 3次重试)
```

### 关键特性
- ✅ 多层超时保护
- ✅ 分级超时策略
- ✅ 降级缓存机制
- ✅ 备选方案提示
- ✅ 自动重试机制

## ⚠️ 注意事项

1. **Unix 系统限制**: `signal.SIGALRM` 仅在 Unix/Linux/macOS 可用
2. **超时调优**: 可根据实际情况调整各层超时值
3. **缓存有效期**: 降级缓存默认 7 天，可根据需要调整

## 🔄 后续建议

1. 监控各接口超时率
2. 根据历史数据动态调整超时值
3. 添加数据源健康检查
4. 实现并发控制避免资源耗尽

---

**修复完成**: 2026-05-16  
**问题来源**: `.pi-invest/sessions/20260516T02130_eb127000/events.jsonl`  
**核心问题**: Python 调用超时 120 秒，用户等待时间过长
