/**
 * ValidationGateTool - 验证门工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { Context } from '@deepseek-ai/cordis';
import type { OsMemoryStore } from '../../index';
import { validationGatePrompt, ValidationGateParams, ValidationGateResult, ConsistencyReport } from './prompt';
import * as fs from 'fs';
import * as path from 'path';

/**
 * L4-B（2026-09-03）：观察期候选记录——与 ../../candidates.ts 共享同一实现。
 * 此前本文件复制了一份接口导致漂移风险（candidates.ts 新增 health_check 后本地副本会漏字段），
 * 现统一从共享模块 import type。本地 writeCandidates 仍保留（与共享模块语义一致）。
 */
import type { CandidateRecord } from '../../candidates';
import { canAutoRollback } from '../../rollbackGuard';

/** 提取候选健康检查的裁决摘要（供 verdict 输出与转正防御） */
function healthSummary(hc: CandidateRecord['health_check']): {
  health_passed: boolean | null;
  substantive: boolean | null;
  health_issues: string[];
} {
  if (!hc) return { health_passed: null, substantive: null, health_issues: [] };
  return {
    health_passed: hc.passed,
    substantive: hc.substantive,
    health_issues: hc.issues.map(i => i.message),
  };
}

/**
 * 验证门工具类
 *
 * 裁决观察期到期的 candidate 版本，对比基准期打标经验，决定提升或回滚
 */
export class ValidationGateTool extends BaseTool<ValidationGateParams, ValidationGateResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'validation_gate',
    category: 'evolver',
    version: '1.0.0',
    timeoutMs: 120000, // 120s（回测和裁决可能较慢）
  };

  protected readonly prompt = validationGatePrompt;

  constructor(
    private ctx: Context,
    private osMemory: OsMemoryStore,
    private observeDays: number
  ) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(params: ValidationGateParams): ValidationResult {
    if (params.min_samples !== undefined) {
      if (typeof params.min_samples !== 'number' || params.min_samples < 1) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'min_samples',
          issue: 'min_samples 必须是正整数',
          received: params.min_samples,
          expected: '>= 1',
        };
      }
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(params: ValidationGateParams, context: ToolContext): Promise<ValidationGateResult> {
    const force = params.force || false;
    const minSamples = params.min_samples || 3;

    // F1 状态一致性诊断（2026-09-06）：裁决前核验 candidates.json ↔ genome.json history，
    // 补文件层语义故障的可观测性（孤儿候选/未登记版本/原子写残留）。healthy=false 不阻断
    // 裁决，但 summary 带警告，执行方按 SOP 落 decision_audit + 飞书。
    const consistency = this.runConsistencyCheck();

    const verdicts = await this.judgeCandidates(force, minSamples);

    const promotedCount = verdicts.filter(v => v.verdict === 'promoted').length;
    const rejectedCount = verdicts.filter(v => v.verdict === 'rejected' || v.verdict === 'rejected_by_backtest').length;
    const watchingCount = verdicts.filter(v => v.verdict === 'watching' || v.verdict === 'extended').length;
    // 回滚守卫拦截数（2026-09-12）：判为"应回滚"但因候选已被后续变更取代而未执行——
    // 单列出来，避免与真正回滚混为一谈（统计诚实）
    const noRollbackCount = verdicts.filter(v => v.verdict === 'rejected_no_rollback').length;

    let summary = `裁决完成：${promotedCount} 转正，${rejectedCount} 回滚，${watchingCount} 继续观察`;
    if (noRollbackCount > 0) {
      summary += `；⚠️ ${noRollbackCount} 条判应回滚但被守卫拦下（候选已被后续变更取代，未执行破坏性回滚，详见 verdicts.note）`;
    }
    if (!consistency.healthy) {
      summary += `；⚠️ 状态一致性 ${consistency.issues.length} 项异常（孤儿候选 ${consistency.orphan_candidates.length} / 未登记版本 ${consistency.unregistered_versions.length} / 原子写残留 ${consistency.atomic_leftovers.length}，详见 consistency，需 decision_audit 留痕）`;
    }

    return {
      verdicts,
      summary,
      total_candidates: verdicts.length,
      promoted_count: promotedCount,
      rejected_count: rejectedCount,
      watching_count: watchingCount,
      no_rollback_count: noRollbackCount,
      consistency,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: ValidationGateResult, context: ToolContext): ToolResponse<ValidationGateResult> {
    return {
      success: true,
      data: result,
    };
  }

  // ===== 私有辅助方法 =====

  private get candidatesPath(): string {
    // @ts-ignore
    return path.join(this.ctx.genome.genomeDir, 'candidates.json');
  }

  private readCandidates(): CandidateRecord[] {
    try {
      if (!fs.existsSync(this.candidatesPath)) return [];
      return JSON.parse(fs.readFileSync(this.candidatesPath, 'utf-8'));
    } catch {
      return [];
    }
  }

  private writeCandidates(list: CandidateRecord[]): void {
    const tmp = this.candidatesPath + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(list, null, 2));
    fs.renameSync(tmp, this.candidatesPath);
  }

  /**
   * 读取某段当前版本号（genome.json.sections[section].version）。
   * 读不到返回 null —— 调用方（回滚守卫）按 fail-closed 处理，绝不猜。
   */
  private readCurrentSectionVersion(section: string): number | null {
    try {
      const p = path.join(this.ctx.genome.genomeDir, 'genome.json');
      if (!fs.existsSync(p)) return null;
      const raw = JSON.parse(fs.readFileSync(p, 'utf-8'));
      const v = raw?.sections?.[section]?.version;
      return Number.isFinite(Number(v)) ? Number(v) : null;
    } catch {
      return null;
    }
  }

  /**
   * 读取 genome.json 的 history 数组（与 candidates.json 同目录）
   */
  private readGenomeHistory(): any[] {
    try {
      const p = path.join(this.ctx.genome.genomeDir, 'genome.json');
      if (!fs.existsSync(p)) return [];
      const data = JSON.parse(fs.readFileSync(p, 'utf-8'));
      return Array.isArray(data.history) ? data.history : [];
    } catch {
      return [];
    }
  }

  /**
   * F1 状态一致性诊断（2026-09-06，w-a8a89c6a）
   *
   * 背景：进化状态存本地文件（candidates.json / genome.json），业务 DB 无表无错误通道——
   * 状态漂移/孤儿残留不产生任何 DB 错误（文件读写成功、工具返回 success），只能人工审计
   * 发现（2026-09-06 实证：8/25 孤儿 candidates.json 曾误导审计）。本腿在每轮 gate 自动
   * 核验并把异常项带给执行方（healthy=false → summary 警告 → 执行方 decision_audit 落 DB）：
   *
   * C1 孤儿候选：watching 候选的 genome_version 不在 genome history → 登记了但 genome 侧
   *    无此版本（genome.json 被回滚/重建覆盖或登记错乱），promote/rollback 无依据。
   * C2 未登记版本：genome history 中 stage=candidate 条目在 candidates.json 无对应登记 →
   *    写 genome 未登记/登记丢失（registerCandidate 断链，g16 principles v6 即 9/3 修复前
   *    历史 bug 的真实残留：8/28 应用后从未被 gate 裁决，观察版实际运行 9 天）→ 验证门无案可裁。
   * C3 原子写残留：genomeDir 下 *.tmp（原子写 tmp+rename 中途崩溃的痕迹）。
   */
  private runConsistencyCheck(): ConsistencyReport {
    const issues: string[] = [];
    const orphanCandidates: ConsistencyReport['orphan_candidates'] = [];
    const unregisteredVersions: ConsistencyReport['unregistered_versions'] = [];
    const atomicLeftovers: string[] = [];

    const candidates = this.readCandidates();
    const history = this.readGenomeHistory();
    const historyVersions = new Set(history.map((h: any) => h.version));

    // C1 孤儿候选（watching/extended 是待裁对象；promoted 版本若不在 history 属历史迁移，不在此列）
    for (const c of candidates) {
      if ((c.status === 'watching' || c.status === 'extended') && c.genome_version && !historyVersions.has(c.genome_version)) {
        orphanCandidates.push({ id: c.id, section: c.section, genome_version: c.genome_version });
        issues.push(
          `孤儿候选 ${c.id}（${c.section} ${c.genome_version}）：genome_version 不在 genome history，promote/rollback 无依据——genome.json 被重建覆盖或登记错乱`
        );
      }
    }

    // C2 未登记版本：history stage=candidate 条目无 candidates.json 对应（同 section + genome_version）
    const registeredKeys = new Set(
      candidates
        .filter((c: any) => c.status === 'watching' || c.status === 'extended' || c.status === 'promoted')
        .map((c: any) => `${c.section}:${c.genome_version}`)
    );
    for (const h of history) {
      if (h.stage === 'candidate') {
        const key = `${h.section}:${h.version}`;
        if (!registeredKeys.has(key)) {
          unregisteredVersions.push({
            section: h.section,
            genome_version: h.version,
            section_version: h.section_version,
            ts: h.ts,
            reason: (h.reason || '').slice(0, 120),
          });
          issues.push(
            `未登记候选版本 ${h.version}（${h.section} v${h.section_version}，${(h.ts || '').slice(0, 10)} 应用）：genome history stage=candidate 但 candidates.json 无记录——写 genome 未登记/登记丢失，验证门无案可裁（观察版滞留，实际内容在运行）`
          );
        }
      }
    }

    // C3 原子写 .tmp 残留
    try {
      const dir = this.ctx.genome.genomeDir;
      for (const f of fs.readdirSync(dir)) {
        if (f.endsWith('.tmp')) atomicLeftovers.push(f);
      }
    } catch {
      // genomeDir 不可读则跳过（不误报）
    }
    if (atomicLeftovers.length > 0) {
      issues.push(`原子写中断残留：${atomicLeftovers.join(', ')}——写入半途崩溃痕迹，需人工确认 genome.json/candidates.json 完整性`);
    }

    return {
      healthy: issues.length === 0,
      checked_at: new Date().toISOString(),
      orphan_candidates: orphanCandidates,
      unregistered_versions: unregisteredVersions,
      atomic_leftovers: atomicLeftovers,
      issues,
    };
  }

  /**
   * 从记忆库取某基因组代数的打标经验奖励
   */
  private async searchRewards(genomeVersion: string): Promise<{ count: number; avg: number }> {
    try {
      const res = await this.osMemory.searchMemory({ q: `genome:${genomeVersion}`, kind: 'experience', limit: 50 });
      const items = res?.items || [];
      const rewards: number[] = [];

      for (const it of items) {
        try {
          const tagged = it.payload?.genome_context?.genome_version;
          if (tagged !== genomeVersion) continue;

          const content = typeof it.content === 'string' ? JSON.parse(it.content) : it.content;
          if (typeof content?.reward === 'number') {
            const tool = content?.action?.tool;
            if (tool && !['portfolio_trade', 'algo_execute'].includes(tool)) continue;
            rewards.push(content.reward);
          }
        } catch {
          // 单条解析失败跳过
        }
      }

      return {
        count: rewards.length,
        avg: rewards.length ? rewards.reduce((a, b) => a + b, 0) / rewards.length : 0,
      };
    } catch {
      return { count: 0, avg: 0 };
    }
  }

  /**
   * 裁决候选版本
   */
  private async judgeCandidates(force: boolean, minSamples: number): Promise<any[]> {
    const list = this.readCandidates();
    const now = Date.now();
    const verdicts: any[] = [];

    for (const c of list.filter(x => x.status === 'watching')) {
      const expired = now >= Date.parse(c.observe_until);
      if (!expired && !force) {
        verdicts.push({
          id: c.id,
          section: c.section,
          genome_version: c.genome_version,
          verdict: 'watching',
          observe_until: c.observe_until,
          ...healthSummary(c.health_check),
        });
        continue;
      }

      // L4-B 静态腿防御（2026-09-03）：结构复核不通过（braces/size/规则ID重复/空更新）
      // 的候选直接拒绝，不浪费回测与观察——内容级噪声即使跑满观察期也不该转正。
      // 注意：结构非法内容理论上已被 genome_update 的 guard 拦截，此防御针对
      // 手写/历史遗留/绕过 guard 的候选。health_check 缺失（null，如旧候选未复核）
      // 不拒绝，只降级标注——绝不因"没质检"假装通过或借故拒绝。
      if (c.health_check && !c.health_check.passed) {
        c.status = 'rejected';
        c.note = `L4-B 结构复核拒绝：${c.health_check.issues.map(i => i.message).join('；')}（验证门防御，未调用 rollback；若内容为候选版需 genome_rollback 复原）`;
        verdicts.push({
          id: c.id,
          section: c.section,
          genome_version: c.genome_version,
          verdict: 'rejected',
          ...healthSummary(c.health_check),
          note: c.note,
        });
        continue;
      }

      // 回测腿（策略类 candidate）
      if (c.strategy_id && c.mutation_type !== 'prompt') {
        const backtestWindows = [
          { label: '全区间', symbol: '002716', start_date: '2025-01-02', end_date: '2026-08-21' },
        ];
        const results: any[] = [];
        let passed = true;
        let reason = '';

        try {
          for (const w of backtestWindows) {
            const res = await this.callTool('strategy_execute', {
              strategy_id: c.strategy_id,
              mode: 'backtest',
              symbols: [w.symbol],
              start_date: w.start_date,
              end_date: w.end_date,
              initial_capital: 100000,
            });

            const bt = res?.backtest_result?.data ?? res?.backtest_result ?? res ?? {};
            results.push({
              label: w.label,
              symbol: w.symbol,
              start_date: w.start_date,
              end_date: w.end_date,
              sharpe: bt.sharpeRatio ?? 0,
              return_pct: (bt.totalReturn ?? 0) * 100,
              max_drawdown_pct: (bt.maxDrawdown ?? 0) * 100,
            });

            const isBad = (bt.sharpeRatio ?? 0) < 0 || (bt.maxDrawdown ?? 0) < -0.30 || (bt.totalTrades ?? 0) === 0;
            if (isBad) {
              passed = false;
              reason = `回测腿拒绝：${w.label} sharpe=${(bt.sharpeRatio ?? 0).toFixed(2)} mdd=${((bt.maxDrawdown ?? 0) * 100).toFixed(1)}% trades=${bt.totalTrades ?? 0}`;
            }
          }
        } catch (e: any) {
          passed = false;
          reason = `回测腿异常：${e.message}`;
        }

        c.backtest_verdict = { passed, windows: results, reason: reason || '回测达标' };

        if (!passed) {
          c.status = 'rejected';
          c.note = `回测腿拒绝：${reason}`;
          verdicts.push({
            id: c.id,
            section: c.section,
            verdict: 'rejected_by_backtest',
            backtest_verdict: c.backtest_verdict,
            ...healthSummary(c.health_check),
          });
          this.writeCandidates(list);
          continue;
        }
      }

      // 模拟盘观察门
      const [cand, base] = await Promise.all([
        this.searchRewards(c.genome_version),
        this.searchRewards(c.baseline_version),
      ]);

      if (!force && cand.count < minSamples) {
        c.observe_until = new Date(now + 2 * 86400000).toISOString();
        c.note = `证据不足延期（candidate 样本 ${cand.count} < ${minSamples}）`;
        verdicts.push({
          id: c.id,
          section: c.section,
          verdict: 'extended',
          cand_samples: cand.count,
          note: c.note,
          ...healthSummary(c.health_check),
        });
        continue;
      }

      // 零样本拒绝转正
      if (cand.count === 0) {
        c.observe_until = new Date(now + 2 * 86400000).toISOString();
        c.note = `零样本拒绝转正（candidate 期无数据，统计无效）`;
        verdicts.push({
          id: c.id,
          section: c.section,
          verdict: 'extended',
          cand_samples: 0,
          note: c.note,
          ...healthSummary(c.health_check),
        });
        continue;
      }

      const drop = base.avg - cand.avg;
      if (drop > 0.1) {
        // 显著恶化 → 回滚（先过 staleness 守卫，2026-09-12，w-adb088f2）
        const guard = canAutoRollback(
          { id: c.id, section: c.section, section_version: c.section_version },
          this.readCurrentSectionVersion(c.section),
        );
        if (!guard.allowed) {
          c.status = 'rejected';
          c.note = `回滚守卫拒绝自动回滚：${guard.reason}`;
          this.writeCandidates(list);
          verdicts.push({
            id: c.id,
            section: c.section,
            genome_version: c.genome_version,
            verdict: 'rejected_no_rollback',
            cand_avg: cand.avg,
            base_avg: base.avg,
            note: c.note,
            ...healthSummary(c.health_check),
          });
          continue;
        }
        try {
          await this.callTool('genome_rollback', {
            section: c.section,
            to_section_version: c.section_version - 1,
            reason: `验证门裁决：candidate 平均奖励 ${cand.avg.toFixed(3)} 显著低于基准 ${base.avg.toFixed(3)}（样本 ${cand.count}/${base.count}）`,
          });
          c.status = 'rejected';
          verdicts.push({
            id: c.id,
            section: c.section,
            verdict: 'rejected',
            cand_avg: cand.avg,
            base_avg: base.avg,
            rolled_back_to: c.section_version - 1,
            ...healthSummary(c.health_check),
          });
        } catch (e: any) {
          verdicts.push({
            id: c.id,
            section: c.section,
            verdict: 'reject_failed',
            error: e.message,
          });
        }
      } else {
        // 转正
        try {
          const hs = healthSummary(c.health_check);
          const healthNote =
            hs.health_passed === null
              ? '（⚠️ 无结构复核记录：候选未过 genome_benchmark 静态腿，仅经验样本证据）'
              : hs.substantive === false
                ? '（⚠️ 内容无实质变更/空更新——低价值转正，谨慎）'
                : '';
          await this.callTool('genome_promote', {
            section: c.section,
            // 绑定候选版本（2026-09-12）：避免"转正最新 candidate"把同段尚未裁决的候选改错
            genome_version: c.genome_version,
            reason: `观察期达标：candidate 平均奖励 ${cand.avg.toFixed(3)} vs 基准 ${base.avg.toFixed(3)}（样本 ${cand.count}/${base.count}）${healthNote}`,
          });
          c.status = 'promoted';
          verdicts.push({
            id: c.id,
            section: c.section,
            verdict: 'promoted',
            cand_avg: cand.avg,
            base_avg: base.avg,
            ...hs,
            health_note: healthNote || undefined,
          });
        } catch (e: any) {
          verdicts.push({
            id: c.id,
            section: c.section,
            verdict: 'promote_failed',
            error: e.message,
          });
        }
      }
    }

    this.writeCandidates(list);
    return verdicts;
  }

  /**
   * 调用其他工具
   */
  private async callTool(name: string, args: Record<string, any>): Promise<any> {
    const result = await (this.ctx.tools as any).execute({
      name,
      arguments: args,
      signal: new AbortController().signal,
    });
    if (result?.isError) {
      throw new Error(result?.error?.message || `${name} 调用失败`);
    }
    return result?.value ?? result;
  }
}
