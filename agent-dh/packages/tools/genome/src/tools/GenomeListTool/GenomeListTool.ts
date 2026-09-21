import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import * as fs from 'fs';
import * as path from 'path';
import { genomeListPrompt, type GenomeListParams, type GenomeListResult, type GenomeSectionInfo } from './prompt';

const VALID_CLASSES = ['constitution', 'evolvable'] as const;

export class GenomeListTool extends BaseTool<GenomeListParams, GenomeListResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'genome_list',
    category: 'genome',
    version: '2.0.0',
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

    if (className && !(VALID_CLASSES as readonly string[]).includes(className)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'class',
        issue: `无效的类别: ${className}`,
        expected: 'constitution 或 evolvable',
      };
    }

    return { success: true };
  }

  protected async execute(params: GenomeListParams, context: ToolContext): Promise<GenomeListResult> {
    const { class: filterClass } = params;
    const sections: GenomeSectionInfo[] = [];
    const byClass = { constitution: 0, evolvable: 0 };

    for (const [name, meta] of Object.entries(this.genomeData.sections)) {
      const section = meta as any;
      const className = section.class as 'constitution' | 'evolvable';

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
      if (className === 'constitution') byClass.constitution++;
      else if (className === 'evolvable') byClass.evolvable++;
    }

    const result: GenomeListResult = { sections, total: sections.length };
    // B-4 修复：undefined 字段会导致工具输出 "not lossless JSON"，按需拼装
    if (!filterClass) result.by_class = byClass;
    return result;
  }

  protected wrap(data: GenomeListResult, context: ToolContext): ToolResponse<GenomeListResult> {
    const { sections, total, by_class } = data;

    let message = `共 ${total} 个段`;
    if (by_class) {
      message += ` (constitution: ${by_class.constitution}, evolvable: ${by_class.evolvable})`;
    }

    const metadata: Record<string, unknown> = { total };
    if (by_class) metadata.by_class = by_class;
    return {
      success: true,
      data,
      message,
      metadata,
    };
  }
}
