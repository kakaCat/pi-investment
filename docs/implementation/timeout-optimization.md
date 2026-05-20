# 数据源超时优化方案

## 问题诊断

### 原始问题
Session `20260516T12425_81a8261f` 出现大量工具调用超时：
- **总工具调用**: 183次
- **超时次数**: 23次（12.6%）
- **超时工具**: 
  - `get_quality_score`: 13次超时
  - `get_valuation`: 10次超时
- **超时时长**: 每次90秒
- **发生时段**: 周末非交易时段（2026-05-16 周六）

### 根本原因
周末非交易时段，数据源（新浪财经/东方财富）响应极慢或不稳定，导致：
1. 财务数据接口全部超时
2. Agent 反复重试，浪费大量时间
3. 最终放弃深度分析，改用已知数据

---

## 解决方案

### 1. 交易时间检测工具

**文件**: `src/infrastructure/akshare-ts/utils/trading-time.ts`

**功能**:
- 检测当前是否为交易时段（周一至周五 9:30-15:00）
- 识别周末、盘前、午休、盘后等非交易时段
- 生成用户友好的错误信息和替代方案

**API**:
```typescript
interface TradingTimeInfo {
  isTradingDay: boolean;      // 是否交易日（非周末）
  isTradingHours: boolean;    // 是否交易时段
  isWeekend: boolean;         // 是否周末
  currentTime: string;        // 当前时间（中国时区）
  reason: string;             // 不可用原因
  alternatives: string[];     // 替代方案建议
}

getTradingTimeInfo(): TradingTimeInfo
generateTimeoutAlternatives(symbol: string, toolName: string): string
```

**示例输出**:
```json
{
  "error": "数据源超时（周末非交易时段，数据源响应缓慢或不可用）",
  "symbol": "600519",
  "tool": "get_quality_score",
  "time_info": {
    "current_time": "2026/05/16 21:34",
    "is_trading_hours": false,
    "is_weekend": true
  },
  "alternatives": [
    "使用已知基本面数据（ROE/毛利率/负债率）进行初步筛选",
    "基于行业和市值进行定性分析",
    "建议交易日 9:30-15:00 重新运行深度分析"
  ],
  "suggestion": "建议在交易时段（周一至周五 9:30-15:00）重新运行以获取完整数据"
}
```

---

### 2. 快速失败机制

**文件**: `src/infrastructure/akshare-ts/data/financial.ts`

**修改的函数**:
- `get_stock_valuation()`
- `get_quality_score()`

**优化策略**:

#### 非交易时段（周末/盘前/盘后）
- **超时时间**: 90秒 → **30秒**
- **失败处理**: 返回明确的错误信息 + 替代方案
- **LLM 提示**: 
  - 当前时间和交易状态
  - 为什么数据不可用
  - 可以使用哪些替代方法
  - 何时重试

#### 交易时段
- **超时时间**: 保持90秒（正常网络延迟）
- **失败处理**: 返回标准错误信息

**代码示例**:
```typescript
export async function get_quality_score(symbol: string): Promise<string> {
  const clean = cleanSymbol(symbol);
  const timeInfo = getTradingTimeInfo();

  if (!timeInfo.isTradingHours) {
    // 非交易时段：30秒快速失败
    const timeoutPromise = new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error('TIMEOUT')), 30000);
    });

    try {
      const result = await Promise.race([
        Promise.all([/* 数据调用 */]),
        timeoutPromise
      ]);
      return await processQualityScore(clean, ...result);
    } catch (e) {
      if (String(e).includes('TIMEOUT')) {
        return generateTimeoutAlternatives(clean, 'get_quality_score');
      }
      return JSON.stringify({ error: String(e), symbol: clean });
    }
  }

  // 交易时段：正常处理（90秒超时）
  try {
    const result = await Promise.all([/* 数据调用 */]);
    return await processQualityScore(clean, ...result);
  } catch (e) {
    return JSON.stringify({ error: String(e), symbol: clean });
  }
}
```

---

## 效果对比

### 修复前
```
Turn 43: 调用 get_quality_score × 8
  → 等待 90秒 × 8 = 720秒（12分钟）
  → 全部超时
  → Agent 困惑，不知道如何处理

Turn 45: 重试 get_valuation × 8
  → 等待 90秒 × 8 = 720秒（12分钟）
  → 全部超时
  → 继续重试...

总浪费时间: ~24分钟
```

### 修复后
```
Turn 43: 调用 get_quality_score × 8
  → 检测到周末非交易时段
  → 等待 30秒 × 8 = 240秒（4分钟）
  → 返回明确错误 + 替代方案
  → LLM 理解原因，切换到替代策略

总时间: ~4分钟
节省: 20分钟（83%）

LLM 收到的信息:
- "周末非交易时段，数据源响应缓慢"
- "建议使用已知基本面数据进行初步筛选"
- "建议交易日 9:30-15:00 重新运行"
→ LLM 立即切换到基于已知数据的分析
```

---

## 测试验证

**测试脚本**: `src/scripts/test-trading-time.ts`

```bash
npx tsx src/scripts/test-trading-time.ts
```

**测试结果**:
```
✅ 正确识别周末非交易时段
✅ 生成用户友好的错误信息
✅ 提供3条替代方案建议
✅ 明确告知何时重试（交易日 9:30-15:00）
```

---

## 未来优化方向

### 1. 缓存策略
- 非交易时段优先使用缓存数据
- 缓存有效期：交易日数据缓存至当日收盘，非交易日数据缓存至下个交易日开盘

### 2. 数据源降级
- 主数据源超时 → 自动切换到备用数据源
- 备用数据源：
  - 本地数据库缓存
  - 历史数据 + 估算
  - 行业平均值

### 3. 智能重试
- 交易时段：立即重试
- 非交易时段：延迟到下个交易日开盘后自动重试
- 重试次数限制：最多3次

### 4. 节假日检测
- 当前实现仅检测周末
- 未来可集成 A股交易日历 API
- 识别法定节假日、调休日

---

## 相关文件

- `src/infrastructure/akshare-ts/utils/trading-time.ts` - 交易时间检测工具
- `src/infrastructure/akshare-ts/data/financial.ts` - 财务数据层（已优化）
- `src/scripts/test-trading-time.ts` - 测试脚本
- `.pi-invest/sessions/20260516T12425_81a8261f/events.jsonl` - 原始问题日志

---

## 总结

通过引入交易时间检测和快速失败机制：

1. **减少等待时间**: 非交易时段超时从90秒降至30秒（节省67%）
2. **提升用户体验**: 明确告知原因和替代方案，而非静默失败
3. **优化 LLM 决策**: 提供结构化的错误信息，帮助 LLM 快速切换策略
4. **节省资源**: 避免无意义的重试和等待

**关键指标**:
- 超时时间优化: 90s → 30s（非交易时段）
- 错误信息质量: 从 "Request timeout" → 结构化错误 + 3条替代方案
- 预期节省时间: 每次超时节省60秒，批量操作节省10-20分钟
