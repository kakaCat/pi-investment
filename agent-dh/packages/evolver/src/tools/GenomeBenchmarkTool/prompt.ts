/**
 * GenomeBenchmarkTool - 候选健康检查 / benchmark 静态腿模板（L4-B）
 */

import type { ToolPrompt, ParameterDefinition } from '@pi-investment/core-tool';

export interface GenomeBenchmarkParams {
  section?: string;
  candidate_id?: string;
  include_promoted?: boolean;
  reject_failed?: boolean;
}

export interface GenomeBenchmarkResult {
  reviewed: Array<{
    id: string;
    section: string;
    genome_version: string;
    status: string;
    health_passed: boolean | null;   // null = 复核失败/未执行（降级标注，绝不假装已质检）
    substantive: boolean | null;
    size_delta: number;
    rule_changes?: { added: string[]; removed: string[] };
    issues: string[];
    note?: string;
  }>;
  summary: string;
  total_reviewed: number;
  structural_pass_count: number;
  structural_fail_count: number;
  empty_update_count: number;
  rejected_count: number;
  degraded_count: number;  // health_check 缺失/复核失败（无法质检，如实标注）
}

export const genomeBenchmarkPrompt: ToolPrompt<GenomeBenchmarkParams> = {
  description: 'L4-B 候选健康检查：对 watching candidate（可指定段/单条/含历史）执行结构复核（花括号未知变量/超限/规则ID重复/空更新）+ 变异画像（diff 字符差、规则增删），结构不通过且在看守期的候选防御性置为 rejected（不自动回滚，note 建议 genome_rollback）。用于：登记复核、裁决前质检、历史候选画像审计。',
  useCases: [
    '对全部 watching 候选做结构复核，拦截格式噪声变异（g1→g18 审计发现 38% 版本为验收/测试噪声）',
    '复核指定 candidate 的健康状态，供验证门裁决引用',
    'include_promoted=true 对历史候选补画像（P4 元学习归因数据）',
  ],
  notes: [
    '健康检查为纯静态腿：结构校验与 genome_update 写入时 guard 同口径，此处做登记期复核留痕',
    'candidate 内容取登记时 genome 版本的 git 快照（非当前文件），事后复核不漂移',
    '空更新（与基线去空白后相同）= 噪声候选特征，标记但不自动改状态',
    '结构复核不通过（passed=false）且 status=watching 且 reject_failed=true（默认）→ 防御性置 rejected',
    'health_check 缺失/复核失败 → degraded 标注（null），绝不假装已质检',
    '本工具只做静态检查与状态标注，不触发回测（策略类候选回测腿在 validation_gate）',
  ],
  relatedTools: ['validation_gate', 'prompt_evolver', 'genome_promote', 'genome_rollback', 'genome_history'],
  parameters: {
    section: {
      type: 'string',
      description: '只复核指定段（principles/rules/lessons），不传则全部',
    } as ParameterDefinition,
    candidate_id: {
      type: 'string',
      description: '只复核指定候选 ID（candidates.json 的 id），不传则按状态过滤',
    } as ParameterDefinition,
    include_promoted: {
      type: 'boolean',
      description: 'true：连同已转正/已拒绝的历史候选一起复核补画像（审计用）；false（默认）：只看守中的 watching',
    } as ParameterDefinition,
    reject_failed: {
      type: 'boolean',
      description: 'true（默认）：结构复核不通过（passed=false）的 watching 候选防御性置为 rejected；false：仅标记不拒绝',
    } as ParameterDefinition,
  },

  examples: [
    {
      title: '复核全部看守候选',
      params: {},
      expectedResult: '对 candidates.json 中全部 watching 候选执行结构复核并输出画像摘要',
    },
    {
      title: '历史候选画像补全（审计）',
      params: { include_promoted: true },
      expectedResult: '连同 promoted/rejected 历史候选一起复核，输出各候选结构画像',
    },
  ],
  output: {
    schema: {
      type: 'object',
      additionalProperties: true,
      properties: {
        reviewed: {
          type: 'array',
          items: {
            type: 'object',
            additionalProperties: true,
            properties: {
              id: { type: 'string' },
              section: { type: 'string' },
              genome_version: { type: 'string' },
              status: { type: 'string' },
              health_passed: { oneOf: [{ type: 'boolean' }, { type: 'null' }] },
              substantive: { oneOf: [{ type: 'boolean' }, { type: 'null' }] },
              size_delta: { type: 'number' },
              rule_changes: { type: 'object', additionalProperties: true },
              issues: { type: 'array', items: { type: 'string' } },
              note: { type: 'string' },
            },
          },
        },
        summary: { type: 'string' },
        total_reviewed: { type: 'number' },
        structural_pass_count: { type: 'number' },
        structural_fail_count: { type: 'number' },
        empty_update_count: { type: 'number' },
        rejected_count: { type: 'number' },
        degraded_count: { type: 'number' },
      },
    },
    render: (_args: GenomeBenchmarkParams, data: any) => {
      const rows = data?.reviewed ?? [];
      return [{
        type: 'text',
        text: [
          `## L4-B 候选健康检查`,
          `**概要**: ${data?.summary ?? ''}`,
          `**复核 ${data?.total_reviewed ?? 0} 条** | 结构通过 ${data?.structural_pass_count ?? 0} | 结构不通过 ${data?.structural_fail_count ?? 0} | 空更新 ${data?.empty_update_count ?? 0} | 拒绝 ${data?.rejected_count ?? 0} | 降级（无法质检）${data?.degraded_count ?? 0}`,
          ``,
          ...rows.map((r: any) =>
            `### ${r.section}@${r.genome_version} [${r.id}] status=${r.status}` +
            `\n- 结构复核: ${r.health_passed === null ? '⚠️ 未质检（degraded）' : r.health_passed ? '通过' : '不通过'} | 实质变更: ${r.substantive === null ? '未知' : r.substantive ? '有' : '无（空更新）'} | diff ${r.size_delta >= 0 ? '+' : ''}${r.size_delta} 字符` +
            (r.rule_changes ? `\n- 规则定义: 新增 [${(r.rule_changes.added || []).join(', ') || '无'}] 移除 [${(r.rule_changes.removed || []).join(', ') || '无'}]` : '') +
            (r.issues && r.issues.length ? `\n- 问题: ${r.issues.join('; ')}` : '') +
            (r.note ? `\n- ${r.note}` : '')
          ),
        ].join('\n'),
      }];
    },
  },
};
