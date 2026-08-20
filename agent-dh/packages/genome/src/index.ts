import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import * as fs from 'fs';
import * as path from 'path';

export default class GenomePlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    genomeDir: z.string().default('~/.dsh-agent-dh/genome'),
  }).default({} as any);

  private genomeDir: string;
  private genomeData: any = null;
  private initialized = false;

  constructor(ctx: Context, config: any) {
    super(ctx, 'genome');
    
    // 展开 ~ 路径
    this.genomeDir = config.genomeDir.replace(/^~/, process.env.HOME || '');
    
    // 立即注册工具（不等待 ready 事件）
    this.registerTools();
  }

  private ensureInitialized() {
    if (this.initialized) return;

    // 读取 genome.json
    const genomePath = path.join(this.genomeDir, 'genome.json');
    if (!fs.existsSync(genomePath)) {
      throw new Error(`genome.json not found at ${genomePath}. Please initialize genome directory first.`);
    }

    this.genomeData = JSON.parse(fs.readFileSync(genomePath, 'utf-8'));
    this.initialized = true;
    this.ctx.logger('genome').info(`Genome loaded: version ${this.genomeData.genome_version}`);
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
        this.ensureInitialized();

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
        this.ensureInitialized();

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
