---
id: wl-2026-09-p1-5-deployment-guide
title: P1-5 部署指南
type: worklog
status: archived
updated: 2026-09-14
owners: [agent-dh]
tags: [worklog, 2026-09]
---

# P1-5 部署指南

## 一、部署前检查

### 1. 确认所有文件已修改

```bash
cd ~/pi-investment

# 检查后端修改
git diff quantsys-v2/domain/factors/models/barra.py
git diff quantsys-v2/adapters/inbound/fastapi_app/routes/factor_models_async.py

# 检查前端修改
git diff agent-dh/packages/risk/src/tools/BarraDecompositionTool/
```

### 2. 运行测试验证

```bash
cd quantsys-v2
source venv/bin/activate
python tests/test_barra_small_sample.py
```

预期输出：
```
============================================================
✓ 所有测试通过！
============================================================
```

---

## 二、后端部署

### 步骤 1: 重启 quantsys-v2 服务

```bash
cd ~/pi-investment/quantsys-v2

# 检查当前服务状态
lsof -ti:5001

# 停止服务（如果在运行）
pkill -f "python.*start_all.py"

# 启动服务
source venv/bin/activate
python start_all.py
```

### 步骤 2: 验证 API 可用性

```bash
# 测试小样本场景（2 只股票）
curl -X POST http://localhost:5001/api/factor-models/barra/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["600519", "000858"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }' | jq .

# 预期返回包含：
# - "degraded": true
# - "method": "single_factor_size"
# - "warning": "小样本模式..."

# 测试完整模式（10 只股票）
curl -X POST http://localhost:5001/api/factor-models/barra/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["600519", "000858", "601318", "000001", "600036", 
                "601398", "600028", "601288", "600900", "000333"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }' | jq .

# 预期返回包含：
# - "degraded": false
# - "n_factors": 5
```

---

## 三、前端部署

### 步骤 1: 构建（可选，tsx 模式下可跳过）

```bash
cd ~/pi-investment/agent-dh

# 仅当需要预编译时执行
pnpm build
```

### 步骤 2: 确保 Profile 链接正确

```bash
# 检查链接状态
python3 agent-dh/scripts/relink-profile.py --check

# 如果有漂移，重新链接
python3 agent-dh/scripts/relink-profile.py
```

### 步骤 3: 重启 DSH Profile

```bash
# 重启 investment profile（端口 13080，由 launchd 托管）
launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh

# 等待启动（约 5-10 秒）
sleep 10

# 验证服务运行
lsof -ti:13080
curl http://localhost:13080/health || echo "等待服务启动..."
```

---

## 四、验收测试

### 在 DSH Web UI 中测试

访问: http://localhost:13080

#### 测试 1: 小样本模式（2 只股票）

在聊天界面输入：

```
请用 risk_barra_decomposition 分析 600519 和 000858 两只股票的风险分解
```

预期结果：
- ✅ 成功返回结果
- ✅ 包含 `degraded: true`
- ✅ 显示警告信息："小样本模式：仅使用市值单因子，精度降低但可用"
- ✅ `n_factors: 1`
- ✅ `method: "single_factor_size"`

#### 测试 2: 完整模式（10 只股票）

在聊天界面输入：

```
请用 risk_barra_decomposition 分析以下 10 只股票的风险分解：
600519, 000858, 601318, 000001, 600036, 601398, 600028, 601288, 600900, 000333
```

预期结果：
- ✅ 成功返回结果
- ✅ `degraded: false` 或不存在此字段
- ✅ `n_factors: 5`
- ✅ 包含完整的因子协方差矩阵和组合暴露度

#### 测试 3: 边界场景（1 只股票）

在聊天界面输入：

```
请用 risk_barra_decomposition 分析 600519 单只股票的风险
```

预期结果：
- ✅ 返回错误（样本不足）
- ✅ 错误信息建议使用 `risk_metrics` 代替

---

## 五、回滚计划

### 如果部署出现问题

#### 后端回滚

```bash
cd ~/pi-investment/quantsys-v2

# 回退代码
git checkout HEAD -- domain/factors/models/barra.py
git checkout HEAD -- adapters/inbound/fastapi_app/routes/factor_models_async.py

# 重启服务
pkill -f "python.*start_all.py"
source venv/bin/activate
python start_all.py
```

#### 前端回滚

```bash
cd ~/pi-investment/agent-dh

# 回退代码
git checkout HEAD -- packages/risk/src/tools/BarraDecompositionTool/

# 重新链接
python3 scripts/relink-profile.py

# 重启 DSH
launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh
```

---

## 六、常见问题排查

### 问题 1: API 返回 500 错误

**症状**: `curl` 请求返回 500 Internal Server Error

**排查**:
```bash
# 查看后端日志
tail -f ~/pi-investment/quantsys-v2/logs/app.log

# 查看 Python 错误
cd ~/pi-investment/quantsys-v2
source venv/bin/activate
python -c "from domain.factors.models.barra import BarraRiskModelCalculator; print('Import OK')"
```

**可能原因**:
- Python 语法错误（缩进、拼写）
- 导入缺失（numpy/pandas/scipy）

### 问题 2: DSH 工具不可用

**症状**: 调用 `risk_barra_decomposition` 时工具未找到

**排查**:
```bash
# 检查 profile 链接
ls -la ~/.dsh/profiles/investment/node_modules/@pi-investment/risk

# 应该是符号链接，指向仓库源码
# lrwxr-xr-x ... @pi-investment/risk -> ../../../pi-investment/agent-dh/packages/risk
```

**解决**:
```bash
cd ~/pi-investment
python3 agent-dh/scripts/relink-profile.py
launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh
```

### 问题 3: 返回结果缺少 `degraded` 字段

**症状**: 小样本场景下返回结果没有 `degraded` 标记

**排查**:
```bash
# 检查后端是否已更新
cd ~/pi-investment/quantsys-v2
grep -n "degraded" domain/factors/models/barra.py

# 应该能找到多处匹配
```

**解决**: 确认代码已提交并重启服务

---

## 七、部署检查清单

### 部署前

- [ ] 所有测试通过（`python tests/test_barra_small_sample.py`）
- [ ] Git 工作区干净（`git status`）
- [ ] 备份当前运行版本

### 部署中

- [ ] quantsys-v2 服务停止
- [ ] quantsys-v2 代码更新
- [ ] quantsys-v2 服务启动成功
- [ ] DSH profile 链接更新
- [ ] DSH service 重启成功

### 部署后

- [ ] API 端点验证（curl 测试通过）
- [ ] DSH Web UI 小样本测试通过
- [ ] DSH Web UI 完整模式测试通过
- [ ] 边界场景测试通过

### 验收完成

- [ ] 所有测试用例通过
- [ ] 无报错日志
- [ ] 用户确认可用

---

## 八、后续工作

### 文档更新

- [ ] 更新 `quantsys-v2/docs/api/factor_models.md`（API 文档）
- [ ] 更新 `agent-dh/docs/tools/risk.md`（工具使用指南）
- [ ] 更新 `docs/architecture/risk-models.md`（架构文档）

### 性能优化（可选）

- [ ] 缓存市值因子暴露（避免重复计算）
- [ ] 并行化时间序列回归（加速计算）

### 增强功能（未来）

- [ ] P1-5.1: 收缩协方差法（5-8 只股票）
- [ ] P1-5.2: 动态因子选择

---

**部署负责人**: _____________  
**部署日期**: _____________  
**验收人**: _____________  
**验收日期**: _____________  
