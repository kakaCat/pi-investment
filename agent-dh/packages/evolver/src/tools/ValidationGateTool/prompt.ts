/**
 * ValidationGateTool - 验证门模板
 */

import type { ToolPrompt, ParameterDefinition } from '@pi-investment/core-tool';

export interface ValidationGateParams {
  force?: boolean;
  min_samples?: number;
}

/**
 * F1 状态一致性诊断（2026-09-06，w-a8a89c6a）：每轮 gate 裁决前对候选登记文件
 * （candidates.json）与 genome.json history 做一致性核验——补"文件层语义故障零
 * DB 痕迹"的可观测性空白：孤儿候选（登记了但 genome 侧无此版本）/ 未登记版本
 * （genome history stage=candidate 但 candidates.json 无记录 → 验证门无案可裁，
 * g16 principles v6 即历史 bug 真实残留）/ 原子写 .tmp 中断残留。
 * healthy=false 时执行方应按 SOP 落 decision_audit + 飞书，而非静默。
 */
export interface ConsistencyReport {
  healthy: boolean;
  checked_at: string;
  /** C1：watching 候选的 genome_version 不在 genome history（无法转正/回滚依据） */
  orphan_candidates: Array<{ id: string; section: string; genome_version: string }>;
  /** C2：genome history stage=candidate 但 candidates.json 无对应登记 */
  unregistered_versions: Array<{ section: string; genome_version: string; section_version?: number; ts?: string; reason?: string }>;
  /** C3：genomeDir 下原子写 .tmp 残留（写半途崩溃痕迹） */
  atomic_leftovers: string[];
  issues: string[];
}

export interface ValidationGateResult {
  verdicts: Array<{
    id: string;
    section: string;
    genome_version: string;
    verdict: 'watching' | 'promoted' | 'rejected' | 'extended' | 'rejected_by_backtest';
    cand_avg?: number;
    base_avg?: number;
    cand_samples?: number;
    rolled_back_to?: number;
    observe_until?: string;
    note?: string;
    backtest_verdict?: any;
  }>;
  summary: string;
  total_candidates: number;
  promoted_count: number;
  rejected_count: number;
  watching_count: number;
  /** F1 状态一致性诊断（healthy=false 时有异常项，见 issues） */
  consistency?: ConsistencyReport;
}

export const validationGatePrompt: ToolPrompt<ValidationGateParams> = {
  description: 'RFC 008 验证门：裁决观察期到期的 candidate 版本（对比基准期打标经验），决定提升或回滚。用于：每日自动裁决、人工强制裁决。',
  useCases: [
    '每日盘后自动裁决到期的 candidate（定时任务）',
    '人工强制裁决所有观察中的 candidate（验收/紧急）',
    '查看验证门裁决历史与候选版本统计',
  ],
  notes: [
    '默认仅裁决观察期到期（observe_until 已过）的 candidate',
    'candidate 期样本数 < min_samples 时自动延期 2 天',
    'candidate 期零样本时拒绝转正（统计无效）',
    'force=true 跳过时间与样本门槛，强制裁决所有 watching 候选',
    '裁决通过 → genome_promote 转正；显著恶化 → genome_rollback 回滚',
  ],
  relatedTools: ['genome_promote', 'genome_rollback', 'prompt_evolver', 'candidate_status'],
  parameters: {
    force: {
      type: 'boolean',
      description: 'true：跳过时间与样本数门槛，强制裁决所有 watching 状态的 candidate；false（默认）：仅裁决观察期到期的',
    } as ParameterDefinition,

    min_samples: {
      type: 'number',
      description: 'candidate 期最小样本数门槛，默认 3（少于此数会延期 2 天）',
    } as ParameterDefinition,
  },

  examples: [
    {
      title: '自动裁决（定时任务）',
      params: {
        force: false,
        min_samples: 3,
      },
      expectedResult: '仅裁决观察期到期且样本充足的 candidate',
    },
    {
      title: '人工强制裁决',
      params: {
        force: true,
        min_samples: 1,
      },
      expectedResult: '强制裁决所有 watching 状态的 candidate（用于紧急情况）',
    },
  ],
  output: {
    schema: {
      type: 'object',
      additionalProperties: true,
      properties: {
        verdicts: {
          type: 'array',
          items: { type: 'object', additionalProperties: true },
        },
        summary: { type: 'string' },
        total_candidates: { type: 'number' },
        promoted_count: { type: 'number' },
        rejected_count: { type: 'number' },
        watching_count: { type: 'number' },
      },
    },
    render: (_args: ValidationGateParams, data: any) => {
      const v = data?.verdicts ?? [];
      return [{
        type: 'text',
        text: [
          `## 验证门裁决结果`,
          `**概要**: ${data?.summary ?? ''}`,
          `**候选总数**: ${data?.total_candidates ?? 0} | 转正 ${data?.promoted_count ?? 0} | 拒绝 ${data?.rejected_count ?? 0} | 观察中 ${data?.watching_count ?? 0}`,
          ``,
          ...v.map((x: any, i: number) => {
            const health =
              x.health_passed === null
                ? x.verdict === 'promoted' || x.verdict === 'rejected' || x.verdict === 'extended'
                  ? ' | ⚠️ 无结构复核记录（仅经验样本证据，未过 genome_benchmark）'
                  : ''
                : x.health_passed
                  ? (x.substantive === false ? ' | ⚠️ 内容无实质变更/空更新' : ' | ✅ 结构复核通过')
                  : ` | ❌ 结构复核不通过（${(x.health_issues || []).join('；')}）`;
            return (
              `### 候选 ${i + 1}: ${x.section}@${x.genome_version} → ${x.verdict}${health}` +
              (x.cand_avg !== undefined ? `（cand ${x.cand_avg.toFixed(3)} vs base ${x.base_avg?.toFixed(3)}）` : '') +
              (x.note ? `\n${x.note}` : '')
            );
          }),
        ].join('\n'),
      }];
    },
  },
};
