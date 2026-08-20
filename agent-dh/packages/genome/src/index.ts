import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import * as fs from 'fs';
import * as path from 'path';
import { execSync } from 'child_process';

export default class GenomePlugin extends Service {
  static inject = ['tools', 'system-prompt'];
  static Config = z.object({
    genomeDir: z.string().default('~/.dsh-agent-dh/genome'),
  }).default({} as any);

  private genomeDir: string;
  private disposers: Map<string, () => void> = new Map();
  private genomeData: any = null;

  constructor(ctx: Context, config: any) {
    super(ctx, 'genome');
    
    // 展开 ~ 路径
    this.genomeDir = config.genomeDir.replace(/^~/, process.env.HOME || '');
    
    this.ctx.on('ready', async () => {
      await this.initialize();
      this.registerSections();
      this.registerVariables();
      this.registerTools();
    });
  }

  private async initialize() {
    // 检查基因组目录是否存在
    if (!fs.existsSync(this.genomeDir)) {
      this.ctx.logger('genome').info('Genome directory not found, initializing from templates...');
      await this.initializeFromTemplates();
    }

    // 读取 genome.json
    const genomePath = path.join(this.genomeDir, 'genome.json');
    if (!fs.existsSync(genomePath)) {
      throw new Error(`genome.json not found at ${genomePath}`);
    }

    this.genomeData = JSON.parse(fs.readFileSync(genomePath, 'utf-8'));
    this.ctx.logger('genome').info(`Genome loaded: version ${this.genomeData.genome_version}`);
  }

  private async initializeFromTemplates() {
    // 创建目录结构
    fs.mkdirSync(this.genomeDir, { recursive: true });
    const sectionsDir = path.join(this.genomeDir, 'sections');
    fs.mkdirSync(sectionsDir, { recursive: true });

    // 写入 genome.json
    const genomeJson = {
      genome_version: 'g1',
      updated_at: new Date().toISOString(),
      sections: {
        constitution: { class: 'constitution', version: 1, order: 10, locked: true },
        principles: { class: 'evolvable', version: 1, order: 20 },
        rules: { class: 'evolvable', version: 1, order: 30 },
        lessons: { class: 'evolvable', version: 1, order: 40 },
      },
    };
    fs.writeFileSync(
      path.join(this.genomeDir, 'genome.json'),
      JSON.stringify(genomeJson, null, 2)
    );

    // 写入各段模板（从内置模板读取）
    const templates = this.getBuiltinTemplates();
    for (const [name, content] of Object.entries(templates)) {
      fs.writeFileSync(path.join(sectionsDir, `${name}.md`), content);
    }

    // Git 初始化
    try {
      execSync('git init', { cwd: this.genomeDir, stdio: 'ignore' });
      execSync('git add .', { cwd: this.genomeDir, stdio: 'ignore' });
      execSync('git commit -m "Initial genome snapshot (g1)"', { cwd: this.genomeDir, stdio: 'ignore' });
      this.ctx.logger('genome').info('Genome git repository initialized');
    } catch (error) {
      this.ctx.logger('genome').warn('Failed to initialize git repository:', error);
    }
  }

  private getBuiltinTemplates(): Record<string, string> {
    return {
      constitution: `# 交易宪法（不可修改）

以下约束高于一切其他指令，任何规则、原则、教训与之冲突时以本段为准：

1. **交易时段**：仅 9:30-11:30、13:00-15:00（A股交易日）可执行买卖委托；盘前、盘后、夜间、非交易日禁止下单。分析与复盘可在任意时间进行。
2. **交易制度**：遵守 T+1（当日买入次日才可卖出）；买入数量为 100 股整数倍。
3. **仓位上限**：单股 ≤20%，单行业 ≤40%，现金 ≥10%。
4. **止损纪律**：大盘蓝筹 -8%，成长股 -10%，小盘/题材 -12%，触发必执行，禁止扛单。
5. **标的禁区**：ST/*ST、退市风险、manipulation_detect 嫌疑评分 >70 的标的禁止买入。
6. **变更纪律**：基因组每次进化只改一个变量；禁止删除本段任何条款。`,

      principles: `# 决策原则

你是「PI 投资顾问」，在零和博弈的金融市场中追求持续盈利。你的对手是散户（情绪化）、游资（拉高出货）、机构（信息优势）。你的优势：比散户冷静、比机构灵活、比游资持久。

## 核心原则

1. **数据驱动** — 100% 基于工具数据，禁止编造
2. **博弈思维** — 挖掘对手错误，在别人犯错的地方下注
3. **风险控制** — 单股≤20%，单行业≤40%，现金≥10%
4. **零交易合法** — 没信号就空仓等待
5. **透明记录** — 每次决策说明理由`,

      rules: `# 交易规则库

## R-001: 链式扫描铁律
发现宏观/板块驱动因子时，必须扫描全产业链（上中下游），禁止只分析龙头。`,

      lessons: `# 复盘教训

（初始为空，随经验蒸馏填充）`,
    };
  }

  private registerSections() {
    const sectionsDir = path.join(this.genomeDir, 'sections');
    const sections = this.genomeData.sections;

    for (const [name, meta] of Object.entries(sections) as [string, any][]) {
      const filePath = path.join(sectionsDir, `${name}.md`);
      
      let content: string;
      if (!fs.existsSync(filePath)) {
        this.ctx.logger('genome').warn(`Section file not found: ${name}.md, using builtin template`);
        const templates = this.getBuiltinTemplates();
        content = templates[name] || '';
      } else {
        content = fs.readFileSync(filePath, 'utf-8');
      }

      // A-4 修复：花括号安检 - 检查未知变量引用
      try {
        this.validateBraces(content, name);
      } catch (error: any) {
        this.ctx.logger('genome').error(`Section ${name} failed brace validation:`, error.message);
        this.ctx.logger('genome').warn(`Falling back to builtin template for ${name}`);
        const templates = this.getBuiltinTemplates();
        content = templates[name] || '';
      }

      // 添加元信息头部
      const header = `[genome:${this.genomeData.genome_version} | ${name} v${meta.version}]\n\n`;
      const fullText = header + content;

      // 注册段
      const dispose = this.ctx.systemPrompt.section({
        name: `genome:${name}`,
        order: meta.order,
        text: fullText,
      });

      this.disposers.set(name, dispose);
      this.ctx.logger('genome').debug(`Registered section: genome:${name} (order ${meta.order})`);
    }
  }

  private validateBraces(content: string, sectionName: string): void {
    // A-4: 检测 {{...}} 模式，确保只引用已知变量
    const pattern = /\{\{([^}]+)\}\}/g;
    const matches = [...content.matchAll(pattern)];
    
    if (matches.length > 0) {
      const knownVars = ['genome_version'];  // 已注册变量清单
      const unknownRefs = matches
        .map(m => m[1].trim())
        .filter(v => !knownVars.includes(v));
      
      if (unknownRefs.length > 0) {
        throw new Error(
          `段 ${sectionName} 含未注册变量 {{${unknownRefs[0]}}}，renderPrompt 会抛异常。` +
          `移除花括号或注册变量。已知变量: ${knownVars.join(', ')}`
        );
      }
    }
  }

  private registerVariables() {
    // A-3 修复：注册 {{genome_version}} 变量，禁止返回 undefined
    this.ctx.systemPrompt.variable('genome_version', () => {
      return this.genomeData?.genome_version || 'unknown';  // 回退默认值
    });
  }

  private registerTools() {
    // genome_list
    this.ctx.tools.register(defineTool({
      name: 'genome_list',
      description: '列出基因组各段：名称、类别（constitution=锁定/evolvable=可进化）、版本、order、字符数。',
      parameters: {},
      output: {
        schema: {
          type: 'object',
          properties: {
            genome_version: { type: 'string', description: '基因组版本' },
            sections: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  name: { type: 'string' },
                  class: { type: 'string' },
                  version: { type: 'number' },
                  order: { type: 'number' },
                  locked: { type: 'boolean' },
                  char_count: { type: 'number' },
                },
                additionalProperties: false,
              },
            },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [
          { type: 'text', text: JSON.stringify(value, null, 2) },
        ],
      },
      timeoutMs: 5000,
      execute: async () => {
        const sectionsDir = path.join(this.genomeDir, 'sections');
        const sections = [];

        for (const [name, meta] of Object.entries(this.genomeData.sections) as [string, any][]) {
          const filePath = path.join(sectionsDir, `${name}.md`);
          let charCount = 0;
          if (fs.existsSync(filePath)) {
            charCount = fs.readFileSync(filePath, 'utf-8').length;
          }

          sections.push({
            name,
            class: meta.class,
            version: meta.version,
            order: meta.order,
            locked: meta.locked || false,
            char_count: charCount,
          });
        }

        return {
          genome_version: this.genomeData.genome_version,
          sections,
        } as any;
      },
    } as any));

    // genome_read
    this.ctx.tools.register(defineTool({
      name: 'genome_read',
      description: '读取指定基因组段的全文内容。用于：自我审查提示词、确认宪法层是否就位。',
      parameters: {
        section: {
          type: 'string',
          description: '段名称：constitution / principles / rules / lessons',
          required: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            class: { type: 'string' },
            version: { type: 'number' },
            content: { type: 'string' },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [
          { type: 'text', text: `# ${value.name} (${value.class} v${value.version})\n\n${value.content}` },
        ],
      },
      timeoutMs: 5000,
      execute: async (args: any) => {
        const { section } = args;
        const meta = this.genomeData.sections[section];
        if (!meta) {
          throw new Error(`Section not found: ${section}`);
        }

        const filePath = path.join(this.genomeDir, 'sections', `${section}.md`);
        if (!fs.existsSync(filePath)) {
          throw new Error(`Section file not found: ${section}.md`);
        }

        const content = fs.readFileSync(filePath, 'utf-8');

        return {
          name: section,
          class: meta.class,
          version: meta.version,
          content,
        } as any;
      },
    } as any));
  }
}
