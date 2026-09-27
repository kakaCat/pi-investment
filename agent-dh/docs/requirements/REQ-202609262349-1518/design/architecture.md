# 架构设计


实现 RTM YAML 文件管理子系统、台账数据模型扩展和 RTM 生成引擎，使 Dive 模式能以 ~2ms 读取节点状态和追溯关系（vs 实时解析文档 ~500ms），验收标准：创建测试需求并完成全流程，7 个 RTM 文件全部生成且读取耗时 < 10ms。


## 整体架构（serves: FR-1, FR-3）

```
┌─────────────────────────────────────────────────────────────┐
│  Reqboard 工具层（现有）                                      │
│  reqboard_create / reqboard_submit / reqboard_ask_confirm   │
│  reqboard_decompose / reqboard_task_move                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ↓ 在 7 个触发点调用
┌─────────────────────────────────────────────────────────────┐
│  RTM 生成引擎（新增）                                         │
│  ├─ RTMGenerator: 主入口                                     │
│  ├─ DocumentParser: 解析文档标注                             │
│  ├─ TraceabilityBuilder: 构建追溯链                          │
│  ├─ CoverageCalculator: 计算覆盖度                           │
│  └─ RTMWriter: 写入 YAML 文件                                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ↓ 读/写
┌─────────────────────────────────────────────────────────────┐
│  数据层                                                       │
│  ├─ 台账（dsh-reqboard.json, schemaVersion: 9）             │
│  │   └─ 新增字段：artifacts[] / designServes[] / implements │
│  └─ RTM 文件（docs/requirements/<REQ>/rtm-*.yml）           │
│      ├─ rtm-lifecycle.yml                                    │
│      ├─ rtm-brainstorming.yml                                │
│      ├─ rtm-design.yml                                       │
│      ├─ rtm-decomposing.yml                                  │
│      ├─ rtm-implementing.yml                                 │
│      ├─ rtm-implementing/*.yml (任务详情)                    │
│      └─ rtm-accepting.yml                                    │
└─────────────────────────────────────────────────────────────┘
```

## 模块划分（serves: FR-3, FR-4, FR-5, FR-6, FR-7）

**1. RTMGenerator（主控制器）**
- 职责：协调各子模块，生成完整的 RTM 文件
- 接口：`generate(requirementId: string, stage: Stage): Promise<void>`
- 位置：`packages/web/dsh-pmboard/src/rtm/RTMGenerator.ts`

**2. DocumentParser（文档解析器）**
- 职责：解析 Markdown 文档中的行内注释标注（`<!-- serves: FR-N -->`）
- 接口：`parse(filePath: string): Promise<Annotation[]>`
- 位置：`packages/web/dsh-pmboard/src/rtm/DocumentParser.ts`

**3. TraceabilityBuilder（追溯链构建器）**
- 职责：根据标注构建三级追溯映射（fr_to_design / design_to_tasks / task_to_tests）
- 接口：`build(stage: Stage, annotations: Annotation[], ledger: Ledger): TraceabilityMap`
- 位置：`packages/web/dsh-pmboard/src/rtm/TraceabilityBuilder.ts`

**4. CoverageCalculator（覆盖度计算器）**
- 职责：计算设计/实施/测试覆盖度，生成 uncovered 清单
- 接口：`calculate(traceability: TraceabilityMap): Coverage`
- 位置：`packages/web/dsh-pmboard/src/rtm/CoverageCalculator.ts`

**5. RTMWriter（YAML 写入器）**
- 职责：将 RTM 对象序列化为 YAML 并写入文件
- 接口：`write(requirementId: string, stage: Stage, rtm: RTMFile): Promise<void>`
- 位置：`packages/web/dsh-pmboard/src/rtm/RTMWriter.ts`

**6. RTMReader（YAML 读取器）**
- 职责：读取并解析 RTM YAML 文件（FR-8）
- 接口：`read(requirementId: string, stage: Stage): Promise<RTMFile | null>`
- 位置：`packages/web/dsh-pmboard/src/rtm/RTMReader.ts`

**7. CoverageGate（覆盖度门禁）**
- 职责：在 reqboard_submit 时检查覆盖度，不足时拒绝提交
- 接口：`check(kind: 'design' | 'plan' | 'verification', coverage: Coverage): void`
- 位置：`packages/web/dsh-pmboard/src/rtm/CoverageGate.ts`

## 数据流（serves: FR-3）

**触发点 1：立项（reqboard_create）**
```
reqboard_create
  → RTMGenerator.generate(reqId, 'lifecycle')
    → RTMWriter.write(reqId, 'lifecycle', {
        lifecycle: { current_stage: 'draft', stages: {...} }
      })
  → 生成 rtm-lifecycle.yml
```

**触发点 2-3：提交需求文档 + 确认（reqboard_submit kind=requirement）**
```
reqboard_submit(kind=requirement)
  → [G2 门禁检查]
  → RTMGenerator.generate(reqId, 'brainstorming')
    → DocumentParser.parse('requirement.md')
      → 提取 FR 列表
    → TraceabilityBuilder.build('brainstorming', ...)
      → 初始化 fr_to_design: {}
    → RTMWriter.write(reqId, 'brainstorming', {...})
  → 生成 rtm-brainstorming.yml

reqboard_ask_confirm(kind=requirement)
  → [用户确认]
  → 更新 rtm-brainstorming.yml: artifacts[0].confirmed = true
  → 更新 rtm-lifecycle.yml: brainstorming.status = 'completed'
```

**触发点 4-5：提交设计文档 + 确认（reqboard_submit kind=design）**
```
reqboard_submit(kind=design)
  → DocumentParser.parse('design/*.md')
    → 提取 serves 标注
  → TraceabilityBuilder.build('design', ...)
    → 构建 fr_to_design 映射
  → CoverageCalculator.calculate(...)
    → 计算 coverage.design.rate
  → CoverageGate.check('design', coverage)
    → IF rate < 100%: throw COVERAGE_INSUFFICIENT
  → RTMGenerator.generate(reqId, 'design')
  → 生成 rtm-design.yml

reqboard_ask_confirm(kind=design)
  → [用户确认]
  → 更新 rtm-design.yml: confirmed = true
```

**触发点 6：批准拆分计划（reqboard_ask_confirm target=plan）**
```
reqboard_submit(kind=plan)
  → [计划提交到台账]

reqboard_decompose
  → [任务落库，带 designServes[] / implements 字段]
  → TraceabilityBuilder.build('decomposing', ...)
    → 构建 design_to_tasks 映射
  → CoverageCalculator.calculate(...)
    → 计算 coverage.implementation.rate
  → CoverageGate.check('plan', coverage)
    → IF rate < 100%: throw COVERAGE_INSUFFICIENT
  → RTMGenerator.generate(reqId, 'decomposing')
  → 生成 rtm-decomposing.yml
  → RTMGenerator.generate(reqId, 'implementing')
  → 生成 rtm-implementing.yml (汇总)
  → 为每个任务生成 rtm-implementing/t-xxx.yml (骨架)
```

**触发点 7：任务状态变更（reqboard_task_move）**
```
reqboard_task_move(taskId, toStatus)
  → [更新台账任务状态]
  → RTMGenerator.updateTaskRTM(reqId, taskId)
    → 更新 rtm-implementing/t-xxx.yml: status / workflow
    → 更新 rtm-implementing.yml: tasks_done / tasks_in_progress
```

## 改动文件清单（serves: FR-1, FR-2, FR-3）

**新增文件**：
- `packages/web/dsh-pmboard/src/rtm/RTMGenerator.ts`
- `packages/web/dsh-pmboard/src/rtm/DocumentParser.ts`
- `packages/web/dsh-pmboard/src/rtm/TraceabilityBuilder.ts`
- `packages/web/dsh-pmboard/src/rtm/CoverageCalculator.ts`
- `packages/web/dsh-pmboard/src/rtm/RTMWriter.ts`
- `packages/web/dsh-pmboard/src/rtm/RTMReader.ts`
- `packages/web/dsh-pmboard/src/rtm/CoverageGate.ts`
- `packages/web/dsh-pmboard/src/rtm/types.ts` (类型定义)
- `scripts/migrate-reqboard-schema-v9.ts` (数据迁移)

**修改文件**：
- `packages/web/dsh-pmboard/src/tools/CreateTool/CreateTool.ts` (触发点 1)
- `packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts` (触发点 2/4，集成门禁)
- `packages/web/dsh-pmboard/src/tools/AskConfirmTool/AskConfirmTool.ts` (触发点 3/5)
- `packages/web/dsh-pmboard/src/tools/DecomposeTool/DecomposeTool.ts` (触发点 6)
- `packages/web/dsh-pmboard/src/tools/TaskExecuteTool/TaskExecuteTool.ts` (触发点 7)
- `packages/web/dsh-pmboard/src/adapters/JsonLedgerRepository.ts` (schemaVersion 9 支持)