# 追溯关系索引引擎


实现文档标注解析器和追溯链构建器，从 Markdown 文档中提取 `<!-- serves: FR-N -->` / `<!-- implements: design/xxx -->` / `<!-- covers: t-xxx -->` 标注，构建三级追溯映射（fr_to_design / design_to_tasks / task_to_tests），验收标准：解析测试文档后正确提取所有标注，生成的追溯映射完整且准确。


## DocumentParser 实现（serves: FR-4）

```typescript
// packages/web/dsh-pmboard/src/rtm/DocumentParser.ts

export interface Annotation {
  type: 'FR' | 'section' | 'task' | 'test'
  id?: string                 // FR-1 / t-xxx / TC-1
  title: string
  ref: string                 // design/arch.md#整体架构
  serves?: string[]           // ["FR-1", "FR-2"]
  implements?: string         // "design/arch#1.1"
  covers?: string[]           // ["t-xxx"]
  line: number
}

export class DocumentParser {
  async parse(filePath: string): Promise<Annotation[]> {
    const content = await fs.readFile(filePath, 'utf-8');
    const lines = content.split('\n');
    const annotations: Annotation[] = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      
      // 解析 FR 定义行：**FR-1: xxx**
      const frMatch = line.match(/\*\*FR-(\d+):\s*(.+?)\*\*/);
      if (frMatch) {
        annotations.push({
          type: 'FR',
          id: `FR-${frMatch[1]}`,
          title: frMatch[2],
          ref: `${path.basename(filePath)}`,
          line: i + 1
        });
      }

      // 解析章节标题：## 整体架构
      const headingMatch = line.match(/^##\s+(.+)$/);
      if (headingMatch) {
        // 查找下一行的标注
        const nextLine = lines[i + 1] || '';
        const serves = this.extractServes(nextLine);
        const implements = this.extractImplements(nextLine);

        annotations.push({
          type: 'section',
          title: headingMatch[1],
          ref: `${path.basename(filePath)}#${headingMatch[1]}`,
          serves,
          implements,
          line: i + 1
        });
      }
    }

    return annotations;
  }

  private extractServes(line: string): string[] | undefined {
    // 匹配 <!-- serves: FR-1, FR-2 -->
    const match = line.match(/<!--\s*serves:\s*([^-]+?)\s*-->/);
    if (!match) return undefined;
    return match[1].split(',').map(s => s.trim());
  }

  private extractImplements(line: string): string | undefined {
    // 匹配 <!-- implements: design/arch#1.1 -->
    const match = line.match(/<!--\s*implements:\s*(.+?)\s*-->/);
    return match ? match[1].trim() : undefined;
  }

  private extractCovers(line: string): string[] | undefined {
    // 匹配 <!-- covers: t-xxx, t-yyy -->
    const match = line.match(/<!--\s*covers:\s*(.+?)\s*-->/);
    if (!match) return undefined;
    return match[1].split(',').map(s => s.trim());
  }
}
```

## TraceabilityBuilder 实现（serves: FR-5）

```typescript
// packages/web/dsh-pmboard/src/rtm/TraceabilityBuilder.ts

export interface TraceabilityMap {
  fr_to_design?: Record<string, string[]>      // FR-1 → [design/arch#1.1, ...]
  design_to_tasks?: Record<string, string[]>   // design/arch#1.1 → [t-xxx, ...]
  task_to_tests?: Record<string, string[]>     // t-xxx → [TC-1, ...]
  fr_to_tasks?: Record<string, string[]>       // 衍生映射
}

export class TraceabilityBuilder {
  build(stage: Stage, annotations: Annotation[], ledger: Ledger | null): TraceabilityMap {
    switch (stage) {
      case 'brainstorming':
        return { fr_to_design: {} };  // 初始化空映射
      
      case 'design':
        return this.buildDesignTrace(annotations);
      
      case 'decomposing':
        return this.buildDecomposingTrace(annotations, ledger);
      
      case 'accepting':
        return this.buildAcceptingTrace(annotations);
      
      default:
        return {};
    }
  }

  private buildDesignTrace(annotations: Annotation[]): TraceabilityMap {
    const fr_to_design: Record<string, string[]> = {};

    for (const ann of annotations) {
      if (ann.type === 'section' && ann.serves) {
        for (const fr of ann.serves) {
          if (!fr_to_design[fr]) fr_to_design[fr] = [];
          fr_to_design[fr].push(ann.ref);
        }
      }
    }

    return { fr_to_design };
  }

  private buildDecomposingTrace(annotations: Annotation[], ledger: Ledger): TraceabilityMap {
    const design_to_tasks: Record<string, string[]> = {};
    const fr_to_tasks: Record<string, string[]> = {};

    // 从台账任务提取追溯关系
    for (const task of ledger.tasks || []) {
      if (task.implements) {
        if (!design_to_tasks[task.implements]) design_to_tasks[task.implements] = [];
        design_to_tasks[task.implements].push(task.id);
      }
      
      if (task.designServes) {
        for (const fr of task.designServes) {
          if (!fr_to_tasks[fr]) fr_to_tasks[fr] = [];
          fr_to_tasks[fr].push(task.id);
        }
      }
    }

    return { design_to_tasks, fr_to_tasks };
  }

  private buildAcceptingTrace(annotations: Annotation[]): TraceabilityMap {
    const task_to_tests: Record<string, string[]> = {};

    for (const ann of annotations) {
      if (ann.type === 'test' && ann.covers) {
        for (const taskId of ann.covers) {
          if (!task_to_tests[taskId]) task_to_tests[taskId] = [];
          task_to_tests[taskId].push(ann.id!);
        }
      }
    }

    return { task_to_tests };
  }
}
```


```bash
# 单元测试：DocumentParser
node -e "
const parser = new DocumentParser();
const annotations = await parser.parse('test-design.md');
assert(annotations.length > 0);
assert(annotations[0].serves.includes('FR-1'));
"

# 单元测试：TraceabilityBuilder
node -e "
const builder = new TraceabilityBuilder();
const trace = builder.build('design', annotations, null);
assert(trace.fr_to_design['FR-1'].length > 0);
"

# 集成测试：完整追溯链
node -e "
// 生成 rtm-design.yml
reqboard_submit({ kind: 'design' });
const rtm = readRTM('REQ-xxx', 'design');
assert(rtm.traceability.fr_to_design['FR-1']);
"
```