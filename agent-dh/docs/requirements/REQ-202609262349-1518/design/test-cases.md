# 测试策略


定义完整的测试策略，覆盖单元测试、集成测试、端到端测试，验收标准：所有功能点都有对应的测试用例，测试通过率 100%。


## 单元测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9）

每个模块的独立测试，详见各设计文档的"验收口径"：
- DocumentParser：[traceability-engine.md 验收口径](./traceability-engine.md#验收口径)
- TraceabilityBuilder：[traceability-engine.md 验收口径](./traceability-engine.md#验收口径)
- CoverageCalculator：[coverage-gate.md 验收口径](./coverage-gate.md#验收口径)
- CoverageGate：[coverage-gate.md 验收口径](./coverage-gate.md#验收口径)

## 集成测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9）

模块间协作测试：
- RTM 生成流程：[rtm-generation.md 验收口径](./rtm-generation.md#验收口径)
- 覆盖度门禁集成：[coverage-gate.md 验收口径](./coverage-gate.md#验收口径)

## 端到端测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9）

完整需求流程测试：
- 创建需求 → 7 个 RTM 文件全部生成：[architecture.md 验收口径](./architecture.md#验收口径)
- RTM 文件结构验证：[rtm-file-structure.md 验收口径](./rtm-file-structure.md#验收口径)
- 数据迁移验证：[ledger-schema.md 验收口径](./ledger-schema.md#验收口径)

## 性能测试（serves: FR-8）

RTM 读取性能验证（目标 < 10ms）：
```bash
time node -e "
  const { RTMReader } = require('./packages/web/dsh-pmboard/src/rtm/RTMReader');
  const reader = new RTMReader();
  const rtm = await reader.read('REQ-xxx', 'design');
  console.log(rtm.coverage.design.rate);
"
# 预期：real < 0.01s
```

## 回归测试（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9）

向后兼容性测试：
```bash
# 使用 v8 台账测试 v9 代码
cp .dsh-data/dsh-reqboard.json.bak-v8 .dsh-data/dsh-reqboard.json
./scripts/restart-with-build.sh
# 预期：服务正常启动，功能正常
```


```bash
# 运行所有测试
pnpm test

# 预期：所有测试通过
```