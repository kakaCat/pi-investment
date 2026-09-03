/**
 * GenomeBenchmarkTool - 候选健康检查 / L4-B benchmark 静态腿
 *
 * 2026-09-03（w-8366e526）：L4 零基线审计发现 g1→g18 中 38% 版本为验收/测试噪声，
 * R-005→R-010"只增不验"。validation_gate 对文本变异（rules/lessons/principles）没有
 * 任何内容层面质检，只能干等记忆样本。本工具提供静态腿：对 candidate 做结构复核
 * （与 genome_update 写入时 guard 同口径——花括号未知变量 / 超限 / 规则ID重复 / 空更新）
 * + 变异画像（diff 字符差 / 规则增删），并把结构不通过的看守候选防御性置为 rejected。
 *
 * 命名：明确避开 quantsys-v2 的 benchmark_run（性能 benchmark，语义不同，撞名会造成
 * 架构混淆——两链并存审计结论 2026-09-03）。
 */
import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { Context } from '@deepseek-ai/cordis';
import { genomeBenchmarkPrompt, GenomeBenchmarkParams, GenomeBenchmarkResult } from './prompt';
import {
  readCandidates,
  writeCandidates,
  attachHealthCheck,
  type CandidateRecord,
} from '../../candidates';
import * as path from 'path';

export class GenomeBenchmarkTool extends BaseTool<GenomeBenchmarkParams, GenomeBenchmarkResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'genome_benchmark',
    category: 'evolver',
    version: '1.0.0',
    timeoutMs: 30000, // 30s（纯本地 fs + git，无需 LLM）
  };

  protected readonly prompt = genomeBenchmarkPrompt;

  constructor(private ctx: Context) {
    super();
  }

  protected validate(params: GenomeBenchmarkParams): ValidationResult {
    if (params.section !== undefined) {
      const valid = ['principles', 'rules', 'lessons'];
      if (!valid.includes(params.section)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'section',
          issue: `section 必须是 ${valid.join('/')} 之一（constitution 为宪法层禁止进化，无可复核候选）`,
          received: params.section,
          expected: valid.join(' | '),
        };
      }
    }
    return { success: true };
  }

  protected async execute(params: GenomeBenchmarkParams): Promise<GenomeBenchmarkResult> {
    const genomeDir = this.genomeDir;
    const includePromoted = params.include_promoted ?? false;
    // 安全默认值显式兜底（工程教训：schema default 不一定被注入）
    const rejectFailed = params.reject_failed !== false;

    const all = readCandidates(genomeDir);

    // 过滤目标候选
    let targets = all;
    if (params.candidate_id) {
      targets = targets.filter(c => c.id === params.candidate_id);
      if (targets.length === 0) {
        return {
          reviewed: [],
          summary: `未找到 candidate_id=${params.candidate_id}（不存在或非候选记录）`,
          total_reviewed: 0,
          structural_pass_count: 0,
          structural_fail_count: 0,
          empty_update_count: 0,
          rejected_count: 0,
          degraded_count: 0,
        };
      }
    } else {
      if (params.section) targets = targets.filter(c => c.section === params.section);
      if (!includePromoted) targets = targets.filter(c => c.status === 'watching');
    }

    const reviewed: GenomeBenchmarkResult['reviewed'] = [];
    let failCount = 0;
    let emptyCount = 0;
    let rejectedCount = 0;
    let degradedCount = 0;

    for (const c of targets) {
      // 复核：用登记时快照重算 health_check 并写回 rec（防止早期候选缺字段 / 记录漂移）
      const hc = attachHealthCheck(genomeDir, c);

      if (hc === null) {
        // 复核失败（无 git 快照 / 读取异常）→ 降级标注，绝不假装已质检
        degradedCount++;
        reviewed.push({
          id: c.id,
          section: c.section,
          genome_version: c.genome_version,
          status: c.status,
          health_passed: null,
          substantive: null,
          size_delta: 0,
          issues: ['健康检查无法执行（缺登记快照或 genome git 历史），已降级标注'],
          note: c.note,
        });
        continue;
      }

      const issues = hc.issues.map(i => i.message);
      if (!hc.passed) failCount++;
      if (hc.issues.some(i => i.code === 'empty_update')) emptyCount++;

      let status = c.status;
      let note = c.note;

      // 防御性拒绝：结构不通过（含空更新噪声）的看守候选——理论上 genome_update 的 guard
      // 已拦截非法内容，此处是防御手写/历史遗留候选。不自动回滚（回滚是主动行为），
      // 只改状态并提示；健康检查误判有保护：内容未过 guard 的候选本就不该在看守中。
      if (!hc.passed && status === 'watching' && rejectFailed) {
        const prev = c.status;
        c.status = 'rejected';
        note = `L4-B 结构复核拒绝：${issues.join('；')}` +
          (note ? `（原 note: ${note}）` : '') +
          '。建议 genome_rollback 复原 active 内容。';
        c.note = note;
        status = 'rejected';
        rejectedCount++;
        // 记录原状态便于追溯（防御性拒绝不应静默）
        (c as any)._benchmark_prev_status = prev;
      } else if (!hc.passed && status === 'watching') {
        // reject_failed=false：仅标注
        c.note = `L4-B 复核不通过（未拒绝，reject_failed=false）：${issues.join('；')}`;
        note = c.note;
      }

      reviewed.push({
        id: c.id,
        section: c.section,
        genome_version: c.genome_version,
        status,
        health_passed: hc.passed,
        substantive: hc.substantive,
        size_delta: hc.size_delta,
        rule_changes: hc.rule_changes,
        issues,
        note,
      });
    }

    // 落盘（health_check 刷新 + 防御性拒绝状态）
    if (targets.length > 0) writeCandidates(genomeDir, all);

    const passCount = reviewed.filter(r => r.health_passed === true).length;
    const summary =
      `复核 ${reviewed.length} 条 candidate` +
      (params.candidate_id ? `（candidate_id=${params.candidate_id}）` : params.section ? `（section=${params.section}）` : includePromoted ? '（含历史候选）' : '（仅 watching）') +
      `：结构通过 ${passCount}，不通过 ${failCount}，空更新 ${emptyCount}，防御性拒绝 ${rejectedCount}，降级 ${degradedCount}`;

    return {
      reviewed,
      summary,
      total_reviewed: reviewed.length,
      structural_pass_count: passCount,
      structural_fail_count: failCount,
      empty_update_count: emptyCount,
      rejected_count: rejectedCount,
      degraded_count: degradedCount,
    };
  }

  protected wrap(result: GenomeBenchmarkResult, context: ToolContext): ToolResponse<GenomeBenchmarkResult> {
    return { success: true, data: result };
  }

  private get genomeDir(): string {
    // @ts-ignore ctx.genome 由 genome 插件注入（cordis service），无类型声明
    return this.ctx.genome.genomeDir;
  }
}
