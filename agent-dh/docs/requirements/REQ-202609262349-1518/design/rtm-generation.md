# RTM 生成逻辑


在 reqboard 工具的 7 个触发点自动生成/更新 RTM 文件，使每个节点的状态和追溯关系实时同步到 RTM，验收标准：完成需求全流程后，7 个 RTM 文件全部生成且内容正确（包含对应节点的 inputs / outputs / traceability / coverage）。


## 7 个触发点集成（serves: FR-3）

| 触发点 | 工具 | 时机 | 生成的 RTM | 集成位置 |
|--------|------|------|------------|----------|
| 1 | reqboard_create | 立项后 | rtm-lifecycle.yml | CreateTool.execute() 末尾 |
| 2 | reqboard_submit(kind=requirement) | G2 门禁通过后 | rtm-brainstorming.yml | SubmitTool.execute() requirement 分支 |
| 3 | reqboard_ask_confirm(kind=requirement) | 用户确认后 | 更新 rtm-brainstorming.yml | AskConfirmTool.execute() confirmed 分支 |
| 4 | reqboard_submit(kind=design) | 设计门禁通过后 | rtm-design.yml | SubmitTool.execute() design 分支 |
| 5 | reqboard_ask_confirm(kind=design) | 用户确认后 | 更新 rtm-design.yml | AskConfirmTool.execute() confirmed 分支 |
| 6 | reqboard_decompose | 任务落库后 | rtm-decomposing.yml + rtm-implementing.yml + rtm-implementing/*.yml | DecomposeTool.execute() 末尾 |
| 7 | reqboard_task_move | 任务状态变更后 | 更新 rtm-implementing/*.yml + rtm-implementing.yml | TaskExecuteTool / TaskReportTool |

## RTMGenerator 实现（serves: FR-3）

```typescript
// packages/web/dsh-pmboard/src/rtm/RTMGenerator.ts

export class RTMGenerator {
  constructor(
    private parser: DocumentParser,
    private traceBuilder: TraceabilityBuilder,
    private coverageCalc: CoverageCalculator,
    private writer: RTMWriter
  ) {}

  async generate(requirementId: string, stage: Stage): Promise<void> {
    const ledger = await this.loadLedger();
    const requirement = ledger.requirements.find(r => r.id === requirementId);
    if (!requirement) throw new Error(`Requirement ${requirementId} not found`);

    switch (stage) {
      case 'lifecycle':
        await this.generateLifecycle(requirement);
        break;
      case 'brainstorming':
        await this.generateBrainstorming(requirement);
        break;
      case 'design':
        await this.generateDesign(requirement);
        break;
      case 'decomposing':
        await this.generateDecomposing(requirement, ledger);
        break;
      case 'implementing':
        await this.generateImplementing(requirement, ledger);
        break;
      case 'accepting':
        await this.generateAccepting(requirement, ledger);
        break;
    }
  }

  private async generateLifecycle(req: Requirement): Promise<void> {
    const rtm: RTMFile = {
      metadata: {
        version: 1,
        requirement_id: req.id,
        stage: 'lifecycle',
        generated_at: new Date().toISOString(),
        generator: 'reqboard-rtm-v1'
      },
      lifecycle: {
        current_stage: req.status,
        stages: this.buildStageStatus(req.statusHistory)
      }
    };
    await this.writer.write(req.id, 'lifecycle', rtm);
  }

  private async generateBrainstorming(req: Requirement): Promise<void> {
    const reqDoc = `docs/requirements/${req.id}/requirement.md`;
    const annotations = await this.parser.parse(reqDoc);
    const frs = annotations.filter(a => a.type === 'FR');

    const rtm: RTMFile = {
      metadata: { /* ... */ },
      inputs: {},
      outputs: {
        requirements: frs.map(fr => ({
          id: fr.id,
          title: fr.title,
          source: 'requirement.md',
          line: fr.line
        }))
      },
      traceability: {
        fr_to_design: {}  // 初始化空映射
      },
      coverage: {}
    };
    await this.writer.write(req.id, 'brainstorming', rtm);
  }

  private async generateDesign(req: Requirement): Promise<void> {
    const designDir = `docs/requirements/${req.id}/design`;
    const designFiles = await this.listMarkdownFiles(designDir);
    
    let allAnnotations = [];
    for (const file of designFiles) {
      const annotations = await this.parser.parse(file);
      allAnnotations.push(...annotations);
    }

    const traceability = this.traceBuilder.build('design', allAnnotations, null);
    const coverage = this.coverageCalc.calculate(traceability);

    const rtm: RTMFile = {
      metadata: { /* ... */ },
      inputs: {
        requirements: await this.getRequirementsFRs(req.id)
      },
      outputs: {
        design_sections: allAnnotations.map(a => ({
          ref: a.ref,
          title: a.title,
          serves: a.serves,
          line: a.line
        }))
      },
      traceability,
      coverage
    };
    await this.writer.write(req.id, 'design', rtm);
  }

  async updateTaskRTM(requirementId: string, taskId: string): Promise<void> {
    const ledger = await this.loadLedger();
    const task = ledger.tasks?.find(t => t.id === taskId);
    if (!task) throw new Error(`Task ${taskId} not found`);

    // 更新单个任务文件
    const taskRTM = await this.buildTaskRTM(task);
    await this.writer.write(requirementId, `implementing/${taskId}`, taskRTM);

    // 更新汇总文件
    await this.updateImplementingSummary(requirementId, ledger);
  }
}
```

## 集成示例（serves: FR-3）

```typescript
// packages/web/dsh-pmboard/src/tools/CreateTool/CreateTool.ts

async execute(args: CreateArgs): Promise<CreateResult> {
  // ... 现有立项逻辑 ...
  
  const requirement = await this.createRequirement(args);
  
  // 【新增】触发点 1：生成 rtm-lifecycle.yml
  const rtmGenerator = new RTMGenerator(/* ... */);
  await rtmGenerator.generate(requirement.id, 'lifecycle');
  
  return { requirement_id: requirement.id, status: 'draft' };
}
```

```typescript
// packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts

async execute(args: SubmitArgs): Promise<SubmitResult> {
  if (args.kind === 'requirement') {
    // G2 门禁检查
    await this.g2Gate.check(args.path);
    
    // 【新增】触发点 2：生成 rtm-brainstorming.yml
    await this.rtmGenerator.generate(args.requirement_id, 'brainstorming');
  }
  
  if (args.kind === 'design') {
    // 【新增】先生成 RTM 用于覆盖度计算
    await this.rtmGenerator.generate(args.requirement_id, 'design');
    
    // 【新增】触发点 4：设计覆盖度门禁
    const rtm = await this.rtmReader.read(args.requirement_id, 'design');
    await this.coverageGate.check('design', rtm.coverage);
  }
  
  return { success: true };
}
```