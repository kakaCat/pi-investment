/**
 * boot-recovery：boot 时刻的确定性状态修复（REQ-370b24，2026-09）。
 *
 * 解决的问题（用户描述）：重启流程出现 bug / 中途死亡后，共享 checkout 的 HEAD 可能滞留
 * 在 agent-self/* 上，后续所有窗口继续在同一分支堆 commit → 管理混乱。修复必须是
 * 工程确定性（可测试不变量），不是 LLM 判断。
 *
 * 不变量（每条都有测试）：
 *  I1 陈旧锁（restarting.lock ts 超过 staleMs，说明重启器中途死亡）→ 移除锁
 *  I2 新鲜锁（重启器仍在健康检查）→ 不动（动会破坏回滚记账）
 *  I3 HEAD 在 agent-self/* 且无 pending/pendingDone（滞留/孤儿态）→ 自动 checkout 回干线
 *     （分支不删除、内容零丢失；杜绝后续窗口继续堆 commit）
 *     I3-救援（2026-09-10 加）：切回干线前，若该 wip 相对干线有独有内容，先归档到具名分支
 *     wip/rescued-<原分支>-<MMDD-HHmm>。原因：工作区里"只存在于 wip 上"的文件（典型=其他窗口
 *     被重启检查点收走的未提交改动）会随 checkout 从磁盘消失，此前没有任何人被告知——
 *     现在既有具名归属分支，也由调用方主动播报（index.ts announceWipRescue）。
 *  I4 pending.checkpoint_branch 与 HEAD 分支不匹配 → 只报 issue 不擅动
 *      （回滚成功态=pending 还在但 HEAD 已回 base，属正常；见 restarter 语义）
 *  I5 幂等：plan 结果确定；apply 后再次 plan 无动作
 *
 * 纯模块：repo/state/锁文件全部注入；本文件不做任何写操作，写由 applyBootActions 执行。
 */
export interface BootGit {
  currentBranch(): string;
  checkout(branch: string): void;
  /** 可选（缺省视为"无独有内容"→ 不建救援分支，保持老实现向后兼容） */
  hasDivergentContent?(branch: string, base: string): boolean;
  /** 可选：在 from 处建归档/救援分支，返回实际分支名 */
  createArchiveBranch?(name: string, from: string): string;
}
export interface BootStateLike {
  readPending(): { checkpoint_branch: string | null; base_branch: string } | null;
  readPendingDone(): { checkpoint_branch: string | null; base_branch: string } | null;
}
export interface BootRecoveryDeps {
  repo: BootGit;
  state: BootStateLike;
  /** 读取 restarting.lock 的写入时刻（ms）；无锁返回 null */
  readLockTs: () => number | null;
  /** 执行 stale 锁移除（真实=StateStore.releaseLock） */
  releaseLock: () => void;
  /** 锁接管阈值（默认 15min，与 StateStore.acquireLock 一致） */
  staleMs?: number;
  now: number;
  /** 干线候选解析：stranded 时回哪条（默认先 main 后 master 的逻辑由调用方给） */
  resolveBase: (branch: string) => string | null;
}
export type BootAction =
  | { kind: 'releaseStaleLock' }
  | { kind: 'rescueWip'; from: string; ref: string }
  | { kind: 'checkoutBase'; from: string; to: string };

/**
 * 救援归档分支名（纯函数，便于测试与幂等断言）：
 *   wip/rescued-agent-self-20260910-210017-0910-2133
 * 分支名里的 '/' 会被替换，避免造出 refs/heads/wip/rescued/... 的多级路径。
 */
export function rescueBranchName(branch: string, now: number): string {
  const d = new Date(now);
  const p = (n: number) => String(n).padStart(2, '0');
  const slug = branch.replace(/[^A-Za-z0-9._-]/g, '-').replace(/^-+|-+$/g, '');
  return `wip/rescued-${slug}-${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}`;
}

export interface BootRecoveryReport {
  actions: BootAction[];
  issues: string[];
}

export function planBootRecovery(deps: BootRecoveryDeps): BootRecoveryReport {
  const { repo, state, readLockTs, staleMs = 15 * 60 * 1000, now, resolveBase } = deps;
  const actions: BootAction[] = [];
  const issues: string[] = [];

  // I1/I2：锁
  const lockTs = readLockTs();
  if (lockTs !== null) {
    if (now - lockTs > staleMs) actions.push({ kind: 'releaseStaleLock' });
    // 新鲜锁：重启器仍在健康检查窗口，保持不动
  }

  // I3/I4：分支
  const branch = repo.currentBranch();
  const onWip = branch.startsWith('agent-self/');
  const pending = state.readPending() ?? state.readPendingDone();
  if (onWip) {
    if (!pending) {
      const base = resolveBase(branch);
      if (base) {
        // 顺序即语义：先把 wip 独有内容归档成具名分支，再切回干线（否则内容只剩"某个 agent-self 分支"）
        if (repo.hasDivergentContent?.(branch, base)) {
          actions.push({ kind: 'rescueWip', from: branch, ref: rescueBranchName(branch, now) });
        }
        actions.push({ kind: 'checkoutBase', from: branch, to: base });
      } else issues.push(`stranded on ${branch} but no trunk branch resolvable`);
    } else if (pending.checkpoint_branch && pending.checkpoint_branch !== branch) {
      issues.push(
        `pending.checkpoint_branch=${pending.checkpoint_branch} != HEAD=${branch}（回滚成功态属正常，勿自动处理）`,
      );
    }
    // pending.checkpoint_branch === branch：正常续跑态，setupResume 接管
  }
  return { actions, issues };
}

export function applyBootRecovery(deps: BootRecoveryDeps, report: BootRecoveryReport): void {
  for (const a of report.actions) {
    if (a.kind === 'checkoutBase') deps.repo.checkout(a.to);
    else if (a.kind === 'rescueWip') {
      // 归档失败不阻塞回干线（wip 分支本身仍在，内容未丢）；调用方按 report 播报
      try { deps.repo.createArchiveBranch?.(a.ref, a.from); }
      catch { /* 保持 fail-safe：救援是尽力而为，绝不能阻断 boot */ }
    }
    else if (a.kind === 'releaseStaleLock') deps.releaseLock();
  }
}

/** plan + apply 一步执行，返回报告供断言/审计 */
export function runBootRecovery(deps: BootRecoveryDeps): BootRecoveryReport {
  const report = planBootRecovery(deps);
  applyBootRecovery(deps, report);
  return report;
}
