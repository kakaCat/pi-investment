# Python Bridge 超时修复

**日期**: 2026-05-16  
**问题**: Python 调用超时 120 秒，导致用户体验差，部分工具调用失败

---

## 🔍 问题分析

### 错误现象
```
Python调用失败: Request timeout after 120000ms
```

### 影响范围
- `get_macro_data` - 宏观经济数据（PMI/CPI/GDP）
- `get_market_news` - 市场新闻（财新/东财/百度）
- `test_market_sentiment` - 市场情绪分析
- `get_lhb` - 龙虎榜数据
- `get_stock_fund_flow` - 个股资金流向

### 根本原因
1. **Python bridge 超时过长**: 硬编码 120 秒
2. **分级超时未生效**: `python-caller-resilient.ts` 的分级超时被 bridge 覆盖
3. **AkShare 调用无超时控制**: Python 端直接调用 `akshare` 库，无函数级超时
4. **网络请求可能挂起**: 数据源（新浪/东财）响应慢或返回错误页面

---

## ✅ 修复方案

### 1. 降低 Python Bridge 超时时间

**文件**: `src/infrastructure/tools/python-bridge.ts`

```diff
- const REQUEST_TIMEOUT_MS = 120000; // 2 minutes
+ const REQUEST_TIMEOUT_MS = 90000; // 90 seconds (max timeout, controlled by caller)
```

**理由**: 90 秒作为最大超时上限，实际超时由调用层控制

---

### 2. 优化分级超时配置

**文件**: `src/infrastructure/tools/shared/python-caller-resilient.ts`

```diff
- const TIMEOUT_FAST = 10000;      // 10秒 - 实时数据
- const TIMEOUT_MEDIUM = 30000;    // 30秒 - 技术指标
- const TIMEOUT_SLOW = 60000;      // 60秒 - 宏观数据
+ const TIMEOUT_FAST = 15000;      // 15秒 - 实时数据（避免网络波动）
+ const TIMEOUT_MEDIUM = 35000;    // 35秒 - 技术指标
+ const TIMEOUT_SLOW = 55000;      // 55秒 - 宏观数据（配合Python端50秒超时）
```

**分级策略**:
- **快速接口 (15秒)**: 实时行情、市场概览、股票新闻
- **中速接口 (35秒)**: 北向资金、资金流向、技术指标、龙虎榜、公告
- **慢速接口 (55秒)**: 宏观数据、财务报表、市场新闻、情绪分析

---

### 3. 添加 Python 函数级超时控制

**文件**: `python/akshare_bridge.py`

#### 3.1 添加超时装饰器

```python
import signal
from functools import wraps

def timeout_decorator(seconds=30):
    """为函数添加超时控制（仅 Unix 系统）"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")

            # 设置信号处理器
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)

            try:
                result = func(*args, **kwargs)
            finally:
                # 恢复原信号处理器
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            return result
        return wrapper
    return decorator
```

#### 3.2 为慢速函数添加超时

```python
@timeout_decorator(seconds=50)
def get_macro_data(indicators: list = None) -> dict:
    # ... 实现

@timeout_decorator(seconds=50)
def get_market_news(num: int = 20) -> dict:
    # ... 实现

@timeout_decorator(seconds=40)
def get_lhb(symbol: str = None, date: str = None) -> dict:
    # ... 实现

@timeout_decorator(seconds=30)
def get_stock_fund_flow(symbol: str) -> dict:
    # ... 实现

@timeout_decorator(seconds=30)
def get_announcements(symbol: str) -> dict:
    # ... 实现

@timeout_decorator(seconds=30)
def get_sector_fund_flow() -> dict:
    # ... 实现
```

---

## 📊 超时层级设计

```
┌─────────────────────────────────────────────────────────┐
│ TypeScript 调用层                                        │
│ python-caller-resilient.ts                              │
│                                                          │
│ ┌─────────────┬─────────────┬─────────────┐            │
│ │ TIMEOUT_FAST│TIMEOUT_MEDIUM│ TIMEOUT_SLOW│            │
│ │   15 秒     │   35 秒      │   55 秒     │            │
│ └─────────────┴─────────────┴─────────────┘            │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Python Bridge 层                                         │
│ python-bridge.ts                                         │
│                                                          │
│         REQUEST_TIMEOUT_MS = 90 秒 (最大上限)           │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Python 函数层                                            │
│ akshare_bridge.py                                        │
│                                                          │
│ ┌──────────────┬──────────────┬──────────────┐         │
│ │ @timeout(30s)│ @timeout(40s)│ @timeout(50s)│         │
│ │ 资金流向     │ 龙虎榜       │ 宏观数据     │         │
│ └──────────────┴──────────────┴──────────────┘         │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 网络请求层                                               │
│ requests.get(timeout=10)                                 │
│                                                          │
│         单次 HTTP 请求 10 秒超时 + 3 次重试             │
└─────────────────────────────────────────────────────────┘
```

---

## 🛡️ 降级策略

### 已有机制（保持不变）

1. **TypeScript 原生优先**: 优先使用 `akshare-ts` 的 TS 实现
2. **降级缓存**: Python 调用失败时，使用 7 天内的旧数据
3. **备选方案提示**: 返回错误时，提供替代工具建议

### 示例

```json
{
  "error": "数据获取失败: Timeout after 55000ms",
  "_from_fallback_cache": true,
  "_cache_age_minutes": 120,
  "_warning": "数据源暂时不可用，使用 120 分钟前的缓存数据",
  "_alternatives": [
    "分别调用 get_north_flow（北向资金）和 get_market_margin（融资融券）",
    "使用 get_lhb 查看龙虎榜数据判断市场热度",
    "使用 get_market_overview 查看大盘走势"
  ]
}
```

---

## 🧪 测试验证

### 运行测试

```bash
node test-timeout-fix.js
```

### 预期结果

```
🧪 测试 get_macro_data (预期超时: 55000ms)
✅ 超时控制生效 (45123ms < 60000ms)

🧪 测试 get_market_news (预期超时: 55000ms)
✅ 成功获取数据
⏱️  耗时: 12345ms

📊 测试总结:
════════════════════════════════════════════════════════════
⏱️  超时 get_macro_data                45123ms
✅ 成功 get_market_news                12345ms
✅ 成功 get_stock_fund_flow            8901ms
⏱️  超时 get_lhb                       35678ms
════════════════════════════════════════════════════════════
✅ 所有测试通过
```

---

## 📈 性能对比

| 场景 | 修复前 | 修复后 | 改善 |
|------|--------|--------|------|
| 宏观数据超时 | 120秒 | 55秒 | ⬇️ 54% |
| 市场新闻超时 | 120秒 | 55秒 | ⬇️ 54% |
| 资金流向超时 | 120秒 | 35秒 | ⬇️ 71% |
| 龙虎榜超时 | 120秒 | 40秒 | ⬇️ 67% |
| 用户等待时间 | 最长2分钟 | 最长55秒 | ⬇️ 54% |

---

## ⚠️ 注意事项

### 1. Unix 系统限制

`signal.SIGALRM` 仅在 Unix/Linux/macOS 上可用，Windows 不支持。

**解决方案**: 
- 生产环境使用 Unix 系统（已满足）
- Windows 开发环境依赖 TypeScript 层超时

### 2. 超时时间调优

如果发现某些接口经常超时但实际可以成功：
- 调整 `TIMEOUT_CONFIG` 中的对应值
- 调整 Python 端 `@timeout_decorator(seconds=X)` 的值

### 3. 降级缓存有效期

降级缓存默认 7 天有效期，可根据数据时效性调整：
```typescript
fallbackCache.set(cacheKey, { 
  ...entry, 
  expiry: Date.now() + 7 * 24 * 60 * 60 * 1000  // 7天
});
```

---

## 🔄 后续优化建议

1. **监控超时率**: 添加日志统计各接口超时频率
2. **动态超时**: 根据历史响应时间动态调整超时值
3. **数据源健康检查**: 定期检测数据源可用性，提前切换备用源
4. **并发控制**: 限制同时发起的 Python 调用数量，避免资源耗尽

---

## 📝 修改文件清单

- ✅ `src/infrastructure/tools/python-bridge.ts` - 降低最大超时到 90 秒
- ✅ `src/infrastructure/tools/shared/python-caller-resilient.ts` - 优化分级超时
- ✅ `python/akshare_bridge.py` - 添加函数级超时装饰器
- ✅ `test-timeout-fix.js` - 超时修复测试脚本
- ✅ `docs/timeout-fix-2026-05-16.md` - 本文档

---

**修复完成时间**: 2026-05-16  
**修复人**: Claude (Opus 4.6)
