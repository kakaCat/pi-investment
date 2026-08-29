import type { ToolPrompt } from '@pi-investment/core-tool';

export interface GenomeListParams {
  class?: 'core' | 'domain' | 'runtime';
}

export interface GenomeSectionInfo {
  name: string;
  class: string;
  version: string;
  description: string;
  char_count: number;
}

export interface GenomeListResult {
  sections: GenomeSectionInfo[];
  total: number;
  by_class?: {
    core: number;
    domain: number;
    runtime: number;
  };
}

export const genomeListPrompt: ToolPrompt<GenomeListParams, GenomeListResult> = {
  description: '列出基因组中的所有段（sections）',
  useCases: [
    '查看基因组结构',
    '了解各类段的数量分布',
    '筛选特定类别的段',
    '审计基因组内容',
  ],
  examples: [
    {
      input: {},
      output: {
        sections: [
          {
            name: 'identity',
            class: 'core',
            version: '1.0.0',
            description: 'Agent 身份定义',
            char_count: 1234,
          },
        ],
        total: 10,
        by_class: { core: 3, domain: 5, runtime: 2 },
      },
      description: '列出所有段',
    },
    {
      input: { class: 'core' },
      output: {
        sections: [
          {
            name: 'identity',
            class: 'core',
            version: '1.0.0',
            description: 'Agent 身份定义',
            char_count: 1234,
          },
        ],
        total: 3,
      },
      description: '只列出核心段',
    },
  ],
};
