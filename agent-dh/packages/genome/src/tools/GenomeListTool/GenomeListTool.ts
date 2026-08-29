import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import * as fs from 'fs';
import * as path from 'path';
import { genomeListPrompt, type GenomeListParams, type GenomeListResult, type GenomeSectionInfo } from './prompt';

export class GenomeListTool extends BaseTool<GenomeListParams, GenomeListResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'genome_list',
    category: 'genome',
    version: '1.0.0',
    timeoutMs: 5000,
  };

  protected readonly prompt = genomeListPrompt;

  constructor(
    private genomeDir: string,
    private genomeData: any
  ) {
    super();
  }

  protected validate(params: GenomeListParams): ValidationResult {
    const { class: className } = params;

    if (className && !['core', 'domain', 'runtime'].includes(className)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'class',
        issue: `无效的类别: ${className}`,
        expected: 'core, domain, 或 runtime',
      };
    }

    return { success: true };
  }

  protected async execute(params: GenomeListParams, context: ToolContext): Promise<GenomeListResult> {
    const { class: filterClass } = params;
    const sections: GenomeSectionInfo[] = [];
    const byClass = { core: 0, domain: 0, runtime: 0 };

    for (const [name, meta] of Object.entries(this.genomeData.sections)) {
      const section = meta as any;
      const className = section.class;

      // 应用过滤
      if (filterClass && className !== filterClass) {
        continue;
      }

      // 读取文件获取字符数
      const filePath = path.join(this.genomeDir, 'sections', `${name}.md`);
      let charCount = 0;
      if (fs.existsSync(filePath)) {
        const content = fs.readFileSync(filePath, 'utf-8');
        charCount = content.length;
      }

      sections.push({
        name,
        class: className,
        version: section.version,
        description: section.description || '',
        char_count: charCount,
      });

      // 统计类别
      if (className === 'core') byClass.core++;
      else if (className === 'domain') byClass.domain++;
      else if (className === 'runtime') byClass.runtime++;
    }

    return {
      sections,
      total: sections.length,
      by_class: filterClass ? undefined : byClass,
    };
  }

  protected wrap(data: GenomeListResult, context: ToolContext): ToolResponse<GenomeListResult> {
    const { sections, total, by_class } = data;

    let message = `共 ${total} 个段`;
    if (by_class) {
      message += ` (core: ${by_class.core}, domain: ${by_class.domain}, runtime: ${by_class.runtime})`;
    }

    return {
      success: true,
      data,
      message,
      metadata: {
        total,
        by_class,
      },
    };
  }
}
