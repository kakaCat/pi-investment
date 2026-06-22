# Jest 测试修复计划 - 剩余问题分析

**当前状态**: 40 通过, 53 失败 (43.0% 通过率)

## 失败测试分类

### 1. 断言值不匹配 (Minor - 容易修复) - 约15个

#### a) 路径差异
```typescript
// restart-agent-tool.test.ts:84
Expected: "/Users/mac/Documents/ai/pi-investment/node_modules/.bin/tsx"
Received: "/Users/mac/Documents/ai/pi-investment/agent-ts/node_modules/.bin/tsx"
```
**原因**: 项目结构变化，agent-ts 现在是子目录  
**修复**: 更新测试中的期望路径

#### b) 汇率值差异
```typescript
// fx-rate-service.test.ts:50
Expected: 0.885
Received: 0.8635
```
**原因**: 实时汇率变化  
**修复**: Mock 汇率数据或放宽断言精度

#### c) 字符串匹配
```typescript
// evolution-reporter.test.ts:82
Expected substring: "## 📊 本月表现"
Received string:    "## 📊 本期表现"
```
**原因**: 输出格式变化  
**修复**: 更新期望字符串

### 2. API 接口变化 (Medium) - 约10个

```typescript
// strategy-optimize-tool.test.ts:60
Expected: "/api/portfolio/strategy-optimize"
Received: "/api/strategies/optimize"
```
**原因**: quantsys-v2 API 端点变化  
**修复**: 更新测试 mock 以匹配新 API

### 3. 超时测试 (需要 Mock) - 约5个

```typescript
// evolution-executor.test.ts
Exceeded timeout of 30000 ms
```
**原因**: 测试执行真实文件操作或网络请求  
**修复**: 添加 mock 或增加超时到 60s

### 4. 逻辑错误 (需要调查) - 约10个

```typescript
// performance-analyzer.test.ts:313
Expected: 3 signals
Received: 0 signals
```
**原因**: 测试数据未正确设置  
**修复**: 检查测试数据准备逻辑

### 5. Mock 配置问题 - 约13个

各种 mock 未正确配置导致的失败

## 修复优先级

### 🔴 优先级 1: 快速修复 (预计 30 分钟)
1. 更新路径断言
2. 修复字符串匹配
3. 放宽数值精度
4. 更新 API 端点

**预期效果**: +10-15 个测试通过

### 🟡 优先级 2: Mock 添加 (预计 1 小时)
1. Mock 网络请求
2. Mock 文件系统操作
3. Mock 外部服务

**预期效果**: +5-10 个测试通过

### 🟢 优先级 3: 逻辑修复 (预计 2 小时)
1. 修复测试数据准备
2. 修复测试逻辑错误
3. 更新过期的测试

**预期效果**: +10-15 个测试通过

## 立即行动

开始优先级 1 的快速修复？
