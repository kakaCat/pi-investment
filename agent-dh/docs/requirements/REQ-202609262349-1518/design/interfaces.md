# 接口设计


定义所有模块的公开接口（函数签名、参数、返回值、错误码），使模块间协作清晰，验收标准：每个模块的接口文档完整，调用示例可运行。


## RTMGenerator 接口（serves: FR-3）

详见 [rtm-generation.md](./rtm-generation.md#rtmgenerator-实现)

```typescript
class RTMGenerator {
  async generate(requirementId: string, stage: Stage): Promise<void>
  async updateTaskRTM(requirementId: string, taskId: string): Promise<void>
}
```

## DocumentParser 接口（serves: FR-4）

详见 [traceability-engine.md](./traceability-engine.md#documentparser-实现)

```typescript
interface Annotation {
  type: 'FR' | 'section' | 'task' | 'test'
  id?: string
  title: string
  ref: string
  serves?: string[]
  implements?: string
  covers?: string[]
  line: number
}

class DocumentParser {
  async parse(filePath: string): Promise<Annotation[]>
}
```

## TraceabilityBuilder 接口（serves: FR-5）

详见 [traceability-engine.md](./traceability-engine.md#traceabilitybuilder-实现)

```typescript
class TraceabilityBuilder {
  build(stage: Stage, annotations: Annotation[], ledger: Ledger | null): TraceabilityMap
}
```

## CoverageCalculator 接口（serves: FR-6）

详见 [coverage-gate.md](./coverage-gate.md#coveragecalculator-实现)

```typescript
class CoverageCalculator {
  calculate(traceability: TraceabilityMap, stage: Stage, frs?: string[], designs?: string[], tasks?: string[]): Coverage
}
```

## CoverageGate 接口（serves: FR-7）

详见 [coverage-gate.md](./coverage-gate.md#coveragegate-实现)

```typescript
class CoverageGate {
  check(kind: 'design' | 'plan' | 'verification', coverage: Coverage): void
  // 抛出 CoverageInsufficientError
}
```

## RTMReader 接口（serves: FR-8）

详见 [architecture.md](./architecture.md#模块划分)

```typescript
class RTMReader {
  async read(requirementId: string, stage: Stage): Promise<RTMFile | null>
}
```

## RTMWriter 接口（serves: FR-3）

详见 [architecture.md](./architecture.md#模块划分)

```typescript
class RTMWriter {
  async write(requirementId: string, stage: Stage, rtm: RTMFile): Promise<void>
}
```


```bash
# 接口调用测试
node -e "
const generator = new RTMGenerator(/* ... */);
await generator.generate('REQ-xxx', 'lifecycle');

const reader = new RTMReader();
const rtm = await reader.read('REQ-xxx', 'lifecycle');
assert(rtm !== null);
assert(rtm.metadata.stage === 'lifecycle');
"
```