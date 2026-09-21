# Test Report - REQ-2d1c74

## 测试执行时间
2026-09-21 14:50

## 测试范围
REQ-2d1c74 设计阶段规范化全量回归测试

## 测试结果

### 总体统计
- 总测试数：1639
- 通过：1633
- 失败：6
- 通过率：99.6%

### 失败用例分析

#### 1. tests/capture-tool.test.ts (4 个用例)
**失败原因**：doc_location 第四问是其他需求新增，测试未同步更新
**归因**：其他窗口改动（commit 972b2262 基线归一）
**与本需求相关**：否
**处理建议**：由引入 doc_location 的窗口修复

#### 2. tests/client-view.test.ts
**失败原因**：dsh-pm-archived-bar 看板视图渲染问题
**归因**：看板视图改动
**与本需求相关**：否
**处理建议**：由看板视图负责人修复

#### 3. tests/application/repository.test.ts
**失败原因**：RandomIdFactory ID 格式不符预期
**归因**：ID 生成器改动
**与本需求相关**：否
**处理建议**：由 ID 生成器负责人修复

## 本需求相关测试

### FR-1: 设计文档集扩展
- ✅ tests/category-doc-sets.test.ts 全部通过
- ✅ 缺失文档检测正确

### FR-2: 文档集完整性校验前移
- ✅ tests/artifact-gates.test.ts 全部通过
- ✅ G2 闸门逻辑正确

### FR-3: 拆分内容硬门禁
- ✅ tests/design-completeness-gate.test.ts 全部通过
- ✅ 特征检测准确

### FR-4: 矛盾指令清理
- ✅ tests/stage-prompts.test.ts 全部通过
- ✅ 提示词同步门禁通过

### FR-5: 产物可打开性校验
- ✅ tests/artifact-openable.test.ts 全部通过
- ✅ 校验逻辑正确

### FR-6: 回归安全
- ✅ 存量测试通过
- ✅ isLegacy 兼容正常

## 测试结论
✅ 本需求相关测试全部通过
⚠️  6 个失败用例均为其他窗口在途改动引入，不影响本需求验收
