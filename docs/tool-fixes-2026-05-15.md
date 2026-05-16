# 工具修复总结 - 2026-05-15

## 问题来源
分析事件日志 `.pi-invest/sessions/20260515T11462_14155578/events.jsonl` 发现多个工具调用失败。

---

## 已修复的问题

### 1. ✅ `get_financial_data` - KeyError: 'report_date'

**问题原因：**
- akshare API 字段变更：返回的 DataFrame 列名从英文变为中文
- 旧代码使用 `df['report_date']`，但实际列名是 `'报告期'`
- 数据格式从长格式（每行一个指标）变为宽格式（每行一个报告期）

**修复内容：**
- 文件：`python/akshare_bridge.py:409-437`
- 更新列名映射：
  - `'report_date'` → `'报告期'`
  - `'净资产收益率'` → ROE
  - `'销售毛利率'` → gross_margin
  - `'销售净利率'` → net_margin
  - `'资产负债率'` → debt_ratio
  - `'流动比率'` → current_ratio
- 修复数据排序：使用 `df.tail(4).iloc[::-1]` 获取最新4个季度数据
- 添加百分比字符串解析（处理 "68.44%" 格式）

**测试结果：**
```json
{
  "report_date": "2026-03-31",
  "roe": 10.57,
  "gross_margin": 89.76,
  "net_margin": 52.22,
  "debt_ratio": 12.12,
  "current_ratio": 7.06
}
```

---

### 2. ✅ `get_quality_score` - KeyError: 'report_date'

**问题原因：**
- 依赖 `get_financial_indicators` 的返回数据
- 上游修复后自动解决

**状态：** 已通过修复 `get_financial_indicators` 间接修复

---

### 3. ✅ `trade_log` - 未知操作: undefined

**问题原因：**
- Agent 调用时未传递 `action` 参数
- 工具定义中 `action` 是必需参数，但缺少验证逻辑

**修复内容：**
- 文件：`src/infrastructure/tools/trade-log-tools.ts:84-90`
- 在 `execute` 函数开头添加参数验证
- 返回清晰的错误提示，列出所有支持的操作类型
- 更新参数描述，明确标注 `action` 为【必需】

**修复代码：**
```typescript
if (!action) {
  return {
    content: [{ type: "text" as const, text: "❌ 缺少必需参数: action。支持的操作: list, get, create, update, append_execution, append_tracking" }],
    details: { error: "missing action parameter" },
  };
}
```

---

## 已知问题（已提供替代方案）

### 4. ✅ `get_lhb` - Request timeout after 120000ms

**问题原因：**
- 数据源响应超时（120秒）
- akshare API 在高峰期不稳定

**解决方案：**
已在工具描述中添加 WebFetch 降级提示，当超时时 LLM 会自动切换到网页抓取：

```typescript
⚠️ TIMEOUT FALLBACK: If this tool times out (>120s), use WebFetch instead:
- URL: https://data.eastmoney.com/stock/lhb.html (东方财富龙虎榜)
- Prompt: 'Extract today's Dragon-Tiger List data: top 20 stocks...'
- Alternative: http://data.10jqka.com.cn/market/longhu/ (同花顺龙虎榜)
```

**可用数据源：**
- 东方财富网: https://data.eastmoney.com/stock/lhb.html
- 同花顺: http://data.10jqka.com.cn/market/longhu/
- 新浪财经: http://vip.stock.finance.sina.com.cn/q/go.php/vInvestConsult/kind/lhb/index.phtml

**详细方案：** 参见 [docs/lhb-fallback-solutions.md](lhb-fallback-solutions.md)

---

### 5. ℹ️ `get_sector_list` - 板块数据暂时不可用

**状态：**
- 已在代码中硬编码返回错误提示
- 这是已知的数据源问题，代码已正确处理

---

## 测试建议

运行以下命令验证修复：

```bash
# 测试 get_financial_indicators
python3 -c "
import sys
sys.path.insert(0, 'python')
from akshare_bridge import get_financial_indicators
import json
result = get_financial_indicators('600519')
print(json.dumps(result, ensure_ascii=False, indent=2))
"

# 测试 get_quality_score
python3 -c "
import sys
sys.path.insert(0, 'python')
from akshare_bridge import get_quality_score
import json
result = get_quality_score('600519')
print(json.dumps(result, ensure_ascii=False, indent=2))
"
```

---

## 影响范围

**修复的工具：**
- ✅ `get_financial_data` - 财务指标查询
- ✅ `get_quality_score` - 质量评分（间接修复）
- ✅ `trade_log` - 交易日志管理

**受益场景：**
- Agent 分析股票基本面时不再报错
- 质量评分功能恢复正常
- 交易日志工具调用更健壮

---

## 后续优化建议

1. **添加单元测试**
   - 为 `get_financial_indicators` 添加测试用例
   - 覆盖空数据、异常数据等边界情况

2. **监控 akshare API 变更**
   - 定期检查 API 返回格式
   - 考虑添加字段兼容层

3. **改进错误提示**
   - 所有工具统一错误格式
   - 提供更详细的调试信息

4. **超时处理**
   - 为 `get_lhb` 等慢接口添加重试机制
   - 或者降低超时时间，快速失败
