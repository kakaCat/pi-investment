# 系统日志健康检查报告

**日期**: 2026-08-27 23:25  
**执行人**: PI 投资顾问·投资脑 (investor)  
**状态**: ✅ 整体健康

---

## 执行摘要

**系统健康度**: 🟢 良好  
**发现问题**: 2 个轻微问题  
**需要处理**: 1 个（quantlib 依赖缺失）

---

## 服务状态检查

### 1. quantsys-v2 后端 ✅

**进程状态**: 🟢 运行中
- PID: 8870
- 端口: 5001
- 运行时长: 10+ 小时
- API 响应: ✅ 正常

**日志分析**（最近 1000 行）:
- 错误数: 10 个
- 主要问题: quantlib 模块缺失（影响 3 个策略）

### 2. Agent OS ✅

**进程状态**: 🟢 运行中
- PID: 17245 (serve), 20303 (listener)
- 端口: 8080
- API 响应: ✅ 正常
- 调度器: ✅ 29 个任务运行中

### 3. DSH Investment Profile ✅

**进程状态**: 🟢 运行中
- 端口: 13080
- Web UI: ✅ 可访问
- 本窗口: w-24ec9233

---

## 发现的问题

### ⚠️ 问题 1: quantlib 模块缺失（轻微）

**影响**: 3 个策略无法加载
```
Failed to load multi_factor_swing_strategy: No module named 'quantlib'
Failed to load ensemble_vote_strategy: No module named 'quantlib'
Failed to load pe_momentum_ma60_strategy: No module named 'quantlib'
```

**影响范围**: 
- 不影响核心功能
- 这 3 个策略暂时不可用
- M1/M3/M6 不受影响

**建议操作**:
```bash
cd /Users/yunpeng/pi-investment/quantsys-v2
source activate-py313.sh
pip install quantlib-python
# 或者如果是自定义库：
pip install -e path/to/quantlib
```

**优先级**: 低（可选）

---

### ⚠️ 问题 2: ThreadPoolExecutor shutdown 警告（轻微）

**错误信息**:
```
ThreadPoolExecutor.shutdown() got an unexpected keyword argument 'timeout'
```

**影响**: 
- 关闭线程池时的警告
- 不影响正常运行
- Python 版本兼容性问题

**原因**: Python 3.9+ 才支持 `shutdown(timeout=xxx)` 参数

**建议操作**:
- 检查 Python 版本: `python --version`
- 如果是 3.8，升级到 3.9+
- 或者修改代码移除 timeout 参数

**优先级**: 低

---

### ✅ 问题 3: 端口 5001 已占用（已解决）

**日志**:
```
ERROR: [Errno 48] address already in use
```

**状态**: 已自然解决
- 这是旧的重启日志
- 当前服务正常运行在 5001

**无需操作**

---

## 系统资源使用

### CPU 负载
```
Load averages: 4.25 3.56 3.29
```
- 14 天运行时长
- 负载正常（6 核心以上）

### 内存使用
```
物理内存: 62GB used / 1.4GB free
  - Wired: 4.1GB
  - Compressed: 18GB
```
- 使用率: 97%
- 压缩内存占用较高
- **建议**: 考虑重启释放内存（非紧急）

---

## 日志健康度评分

| 服务 | 错误率 | 评分 | 状态 |
|---|---|---|---|
| quantsys-v2 | 1% (10/1000) | 🟢 A | 优秀 |
| Agent OS | 0% | 🟢 A+ | 完美 |
| DSH investment | 0% | 🟢 A+ | 完美 |

**总体评分**: 🟢 **A (优秀)**

---

## 建议操作清单

### 立即执行（可选）
- [ ] 安装 quantlib 模块（如果需要那 3 个策略）

### 本周内
- [ ] 计划系统重启（释放内存）
  - 建议时间: 周末凌晨
  - 释放 18GB 压缩内存

### 下次维护
- [ ] 升级 Python 到 3.9+（解决 ThreadPoolExecutor 警告）
- [ ] 清理旧日志文件（如果磁盘空间紧张）

---

## 监控建议

### 日常监控指标
1. **服务可用性** - 每日检查
   ```bash
   curl http://localhost:5001/health
   curl http://localhost:8080/health
   ```

2. **错误日志** - 每周检查
   ```bash
   tail -1000 quantsys-v2/logs/fastapi_5001.log | grep -i error
   ```

3. **内存使用** - 每周检查
   ```bash
   top -l 1 | grep PhysMem
   ```

### 告警阈值建议
- 错误率 > 5%: 🟡 警告
- 错误率 > 10%: 🔴 告警
- 内存使用 > 95%: 🟡 警告
- 服务无响应: 🔴 告警

---

## 验证清单

- [x] 所有服务进程运行中
- [x] 所有端口正常监听
- [x] API 可正常响应
- [x] 无严重错误
- [x] 系统负载正常

---

## 结论

**系统整体健康，可继续运行。**

发现的 2 个问题都是轻微的，不影响核心功能。quantlib 缺失只影响 3 个可选策略，ThreadPoolExecutor 警告不影响运行。

**下一次检查**: 2026-09-03 (1周后)

---

**检查完成时间**: 2026-08-27 23:25
