/**
 * boot-hook：LifecyclePlugin 构造期调用的接线层（REQ-370b24，2026-09）。
 *
 * 设计目标：让"重启/收尾 bug 后滞留 agent-self"成为可审计的确定性自动修复，而不是
 * 依赖提醒 + LLM 收尾。本层只做三件事：
 *  1. 调 planBootRecovery/applyBootRecovery（不变量的判定与执行在 boot-recovery.ts）
 *  2. 有任何动作/issue 时追加 JSONL 机器审计（boot-recovery-audit.jsonl）
 *  3. 返回报告供调用方打日志；任何异常由调用方 try/catch 吞掉——boot 绝不能被修复逻辑阻断
 */
import { appendFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import type { BootRecoveryDeps, BootRecoveryReport } from './boot-recovery.js';
import { planBootRecovery, applyBootRecovery } from './boot-recovery.js';

export interface BootHookDeps extends BootRecoveryDeps {
  /** 审计文件（JSONL，逐行 JSON；无动作时不创建文件） */
  auditPath: string;
}

export function onBoot(deps: BootHookDeps): BootRecoveryReport {
  const report = planBootRecovery(deps);
  applyBootRecovery(deps, report);
  if (report.actions.length > 0 || report.issues.length > 0) {
    try {
      mkdirSync(dirname(deps.auditPath), { recursive: true });
      appendFileSync(deps.auditPath, `${JSON.stringify({
        ts: new Date(deps.now).toISOString(),
        actions: report.actions,
        issues: report.issues,
        headAfter: deps.repo.currentBranch(),
      })}\n`, 'utf8');
    } catch (e) {
      // 审计失败不阻断 boot；由调用方 logger.warn 报告
      throw new Error(`boot-recovery audit failed: ${String(e)}`);
    }
  }
  return report;
}
