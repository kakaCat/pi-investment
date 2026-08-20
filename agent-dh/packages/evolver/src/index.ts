/**
 * Evolver Plugin - Prompt Evolution Engine
 * P1-2: 接收 experience_distill 建议，生成段更新提案，调用 genome_update 应用
 */
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';

export default class EvolverPlugin extends Service {
  static inject = ['tools', 'genome'];  // 依赖 genome 插件
  static Config = z.object({}).default({} as any);

  constructor(ctx: Context, config: any) {
    super(ctx, 'evolver');
    this.registerTools();
  }

  private registerTools(): void {
    // P1-2: prompt_evolver - 提示词进化工具
    this.ctx.tools.register(defineTool({
      name: 'prompt_evolver',
      description: 'P1-2 提示词进化：接收 distill 建议，生成段更新提案，调用 genome_update 应用。用于：每日蒸馏、手动应用改进、A/B 测试新规则。',
      parameters: {
        suggestions: {
          type: 'array',
          description: 'experience_distill 输出的建议数组',
          items: {
            type: 'object',
            properties: {
              type: { type: 'string' },
              section: { type: 'string' },
              content: { type: 'string' },
              reason: { type: 'string' },
            },
            additionalProperties: true,
          },
          required: true,
        },
        dry_run: {
          type: 'boolean',
          description: 'true（默认）：只生成预览，不执行；false：实际调用 genome_update',
          default: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            proposals: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  section: { type: 'string' },
                  action: { type: 'string' },
                  content: { type: 'string' },
                  reason: { type: 'string' },
                  preview_diff: { type: 'string' },
                },
                additionalProperties: false,
              },
            },
            applied: { type: 'boolean' },
            results: {
              type: 'array',
              items: {
                type: 'object',
                additionalProperties: true,
              },
            },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [
          { type: 'text', text: JSON.stringify(value, null, 2) },
        ],
      },
      timeoutMs: 60000,
      execute: async (args: any) => {
        const { suggestions, dry_run } = args;
        const proposals = [];
        const results = [];

        // @ts-ignore
        const genome = this.ctx.genome;
        if (!genome || !genome.genomeData) {
          throw new Error('Genome plugin not available');
        }

        // 解析每条建议，生成提案
        for (const suggestion of suggestions) {
          if (suggestion.type === 'info') {
            continue;  // 跳过信息性建议
          }

          const section = suggestion.section;
          if (!section || !genome.genomeData.sections[section]) {
            continue;  // 跳过无效段
          }

          // 读取当前段内容
          const currentContent = await this.readSection(section);
          let newContent = currentContent;
          let action = 'modify';

          // 根据 type 生成新内容
          if (suggestion.type === 'add_rule') {
            // 追加规则到 rules 段
            newContent = currentContent.trim() + '\n' + suggestion.content;
            action = 'add';
          } else if (suggestion.type === 'modify_principle') {
            // 修改 principles（简化：追加到末尾）
            newContent = currentContent.trim() + '\n' + suggestion.content;
            action = 'modify';
          }

          // 生成 diff 预览
          const preview_diff = this.generateDiff(currentContent, newContent);

          const proposal = {
            section,
            action,
            content: newContent,
            reason: suggestion.reason || '经验蒸馏建议',
            preview_diff,
          };

          proposals.push(proposal);

          // 如果非 dry_run，执行 genome_update
          if (!dry_run) {
            try {
              // 调用 genome_update 工具（通过 ctx.tools）
              const updateResult = await this.callGenomeUpdate(
                section,
                newContent,
                suggestion.reason || '经验蒸馏建议'
              );
              results.push({
                section,
                success: true,
                result: updateResult,
              });
            } catch (error: any) {
              results.push({
                section,
                success: false,
                error: error.message,
              });
            }
          }
        }

        return {
          proposals,
          applied: !dry_run,
          results: dry_run ? [] : results,
        } as any;
      },
    } as any));
  }

  /**
   * 读取段内容
   */
  private async readSection(sectionName: string): Promise<string> {
    // @ts-ignore
    const genome = this.ctx.genome;
    const fs = await import('fs');
    const path = await import('path');
    
    const genomeDir = genome.genomeDir;
    const filePath = path.join(genomeDir, 'sections', `${sectionName}.md`);
    
    if (!fs.existsSync(filePath)) {
      throw new Error(`Section file not found: ${sectionName}.md`);
    }
    
    return fs.readFileSync(filePath, 'utf-8');
  }

  /**
   * 生成简单的 diff 预览
   */
  private generateDiff(oldContent: string, newContent: string): string {
    const oldLines = oldContent.split('\n');
    const newLines = newContent.split('\n');
    
    const added = newLines.filter(line => !oldLines.includes(line));
    
    if (added.length === 0) {
      return '(无变化)';
    }
    
    return added.map(line => `+ ${line}`).join('\n');
  }

  /**
   * 调用 genome_update 工具
   */
  private async callGenomeUpdate(
    section: string,
    content: string,
    reason: string
  ): Promise<any> {
    // 通过 ctx.tools 调用 genome_update
    const tool = this.ctx.tools.list().find(t => t.name === 'genome_update');
    if (!tool) {
      throw new Error('genome_update tool not found');
    }

    // @ts-ignore - tool.execute exists
    return await tool.execute({
      section,
      content,
      reason,
      force: false,
    });
  }
}
