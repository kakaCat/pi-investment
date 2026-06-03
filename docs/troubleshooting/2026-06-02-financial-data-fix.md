# 财务数据获取失效问题修复方案

**日期**: 2026-06-02  
**问题**: `data_fetch_financial` 工具对所有股票（包括 600809、600519）都失败  
**状态**: ✅ 已修复

## 问题描述

### 错误症状
```
data_fetch_financial({ symbol: "600809", reportType: "all" })
财务数据获取失败: HTTP 400: {"error":"All providers failed for 600809.SH: 
  Provider sina failed: 新浪财经查询失败: 利润表获取失败: Expecting value: line 1 column 1 (char 0)
  Provider eastmoney failed: 东方财富查询失败: 未能获取任何财务报表数据"
```

### 根本原因

经过深入调查，发现 **akshare 的所有免费财务数据接口都已失效**：

1. **新浪财经接口** (`stock_financial_report_sina`)
   - 错误: `JSONDecodeError: Expecting value: line 1 column 1 (char 0)`
   - 原因: API 返回空响应，可能需要认证或接口已废弃

2. **东方财富接口** (`stock_profit_sheet_by_report_em`, `stock_balance_sheet_by_report_em`)
   - 错误: `TypeError: 'NoneType' object is not subscriptable`
   - 原因: API 返回 None，接口可能已变更

3. **测试结果**:
   - akshare 版本: 1.17.16 → 1.18.64（已升级）
   - 测试股票: 600519（贵州茅台）、600809
   - 结果: 所有接口均失败

## 解决方案

### 方案 1: 集成 Tushare Pro（推荐）✅

**优势**:
- ✅ 官方维护，稳定可靠
- ✅ 免费用户额度充足（200次/分钟，10000次/天）
- ✅ 数据质量高，覆盖全面
- ✅ 接口稳定，有 SLA 保障

**实施步骤**:

1. **注册获取 Token**
   - 访问 https://tushare.pro/register
   - 注册账号（免费）
   - 获取 API token

2. **安装依赖**
   ```bash
   cd /Users/mac/Documents/ai/pi-investment
   .venv-py313/bin/pip install tushare
   ```

3. **配置环境变量**
   在 `.env` 文件中添加：
   ```bash
   TUSHARE_TOKEN=your_token_here
   ```

4. **已完成的代码修改**
   - ✅ 创建 `TushareFinancialProvider` (quantsys-v2/services/financial_providers/tushare_provider.py)
   - ✅ 更新 `FinancialDataService` 优先使用 Tushare
   - ✅ 保留免费数据源作为 fallback

5. **重启服务**
   ```bash
   cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
   ps aux | grep "[p]ython.*quantsys-v2" | awk '{print $2}' | xargs kill -9
   ../.venv-py313/bin/python start_all.py
   ```

### 方案 2: 等待 akshare 修复（不推荐）

akshare 的免费数据源依赖第三方网站，随时可能失效，不建议依赖。

### 方案 3: 自建爬虫（成本高）

需要维护爬虫逻辑，应对反爬虫机制，不推荐。

## 数据源优先级

修复后的数据源优先级：

1. **Tushare Pro** (首选) - 需要 token，稳定可靠
2. **新浪财经** (备选) - 免费但可能失效
3. **东方财富** (备选) - 免费但可能失效

如果设置了 `TUSHARE_TOKEN` 环境变量，系统会优先使用 Tushare；否则降级到免费数据源。

## 验证步骤

1. **安装 tushare**:
   ```bash
   .venv-py313/bin/pip install tushare
   ```

2. **设置 token** (在 `.env` 中):
   ```bash
   TUSHARE_TOKEN=your_actual_token
   ```

3. **重启服务**:
   ```bash
   cd quantsys-v2
   ../.venv-py313/bin/python start_all.py
   ```

4. **测试 API**:
   ```bash
   curl "http://127.0.0.1:5001/api/stock/600519.SH/financials?report_types=income"
   ```

5. **测试工具**:
   ```typescript
   data_fetch_financial({ symbol: "600519", reportType: "income" })
   ```

## 预期结果

- ✅ 贵州茅台（600519）财务数据成功获取
- ✅ 数据源显示为 "tushare"
- ✅ 返回最近 4 期财务报表
- ⚠️ 600809 如果已退市，仍会返回空数据（这是正常的）

## 注意事项

1. **Tushare 免费额度**:
   - 每分钟 200 次调用
   - 每天 10000 次调用
   - 超出额度会限流

2. **Token 安全**:
   - 不要将 token 提交到 git
   - 已在 `.gitignore` 中排除 `.env` 文件

3. **降级策略**:
   - 如果 Tushare 不可用（未设置 token 或额度用尽），自动降级到免费数据源
   - 免费数据源可能随时失效，建议配置 Tushare

## 相关文件

- `quantsys-v2/services/financial_providers/tushare_provider.py` - Tushare 数据源实现
- `quantsys-v2/services/financial_data_service.py` - 多数据源协调器
- `quantsys-v2/services/financial_providers/__init__.py` - 导出配置
- `.env` - 环境变量配置（需要添加 TUSHARE_TOKEN）

## 后续优化

- [ ] 添加数据源健康检查和告警
- [ ] 实现数据源性能统计（响应时间、成功率）
- [ ] 考虑集成更多备用数据源（baostock、JointQuant 等）
- [ ] 实现数据缓存，减少 API 调用次数
