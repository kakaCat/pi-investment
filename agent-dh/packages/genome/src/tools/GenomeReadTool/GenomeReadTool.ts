import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import * as fs from 'fs';
import * as path from 'path';
import { genomeReadPrompt, type GenomeReadParams, type GenomeReadResult } from './prompt';

export class GenomeReadTool extends BaseTool<GenomeReadParams, GenomeReadResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'genome_read',
    category: 'genome',
    version: '1.0.0',
    timeoutMs: 5000,
  };

  protected readonly prompt = genomeReadPrompt;

  constructor(
    private genomeDir: string,
    private genomeData: any
  ) {
    super();
  }

  protected validate(params: GenomeReadParams): ValidationResult {
    const { section } = params;

    // 检查 section 是否存在
    if (!this.genomeData.sections[section]) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'section',
        issue: `段 ${section} 不存在`,
        expected: `可用段: ${Object.keys(this.genomeData.sections).join(', ')}`,
      };
    }

    return { success: true };
  }

  protected async execute(params: GenomeReadParams, context: ToolContext): Promise<GenomeReadResult> {
    const { section } = params;
    const meta = this.genomeData.sections[section];

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
    };
  }

  protected wrap(data: GenomeReadResult, context: ToolContext): ToolResponse<GenomeReadResult> {
    const { name, class: className, version, content } = data;

    const charCount = content.length;
    const lineCount = content.split('\n').length;

    const message = `${name} (${className} v${version}): ${lineCount} 行, ${charCount} 字符`;

    return {
      success: true,
      data,
      message,
      metadata: {
        section: name,
        class: className,
        version,
        char_count: charCount,
        line_count: lineCount,
      },
    };
  }
}
