/**
 * exit-finalize：self_finalize(action=exit) 的退出前显式收尾（P0 修复，2026-09-10）。
 *
 * 缺陷（实测复现）：exit 清 pending/pendingDone 却不回干线 → 新进程 boot 时 boot-recovery 的
 * I3 把"设计性退出"误判为"崩溃滞留" → 静默 checkout 回干线；工作区里只存在于 wip 分支上的文件
 * （典型：其他窗口被重启检查点收走的未提交改动）从磁盘消失，且无人被告知（stranded watchdog
 * 因 HEAD 已回干线而短路）。根因是 exit 与 I3 对同一状态的判定互相矛盾——exit 主动制造了
 * I3 专门要消灭的那种状态。
 *
 * 修复：exit 退出前自己把收尾做完（此刻进程还活着、调用方还能拿到结果）：
 *   ① wip 相对干线有独有内容 → 归档到具名分支 wip/rescued-<检查点>-<MMDD-HHmm>
 *   ② 回干线（与 I3 的目标一致，HEAD 不再滞留 → 下次 boot I3 无动作）
 *   ③ 把独有文件按"未提交改动"形态取回工作区（作者窗口可继续在原位置编辑；不夹带他人内容进干线）
 *   ④ 归档成功后删除已无必要的 agent-self 检查点分支（内容全在归档分支，零丢失）
 *
 * 顺序不可调换：必须先回干线再取回文件。留在检查点分支上时这些文件与 HEAD 一致，取回等于空操作，
 * 而随后的 checkout(base) 又会把它们更新成干线版本——顺序反了等于什么都没保住。
 *
 * 纯逻辑 + 注入 repo（真实=GitRepo），便于用真实 git 仓库测试；任何 git 异常都不抛出，
 * 只记进 error 字段——exit 的首要语义是"能退出"。
 */
import { rescueBranchName } from './boot-recovery.js';

export interface ExitFinalizeRepo {
  currentBranch(): string;
  checkout(branch: string): void;
  /** 缺省视为"无独有内容"（老实现向后兼容） */
  hasDivergentContent?(branch: string, base: string): boolean;
  listDivergentFiles?(branch: string, base: string): string[];
  createArchiveBranch?(name: string, from: string): string;
  restorePathsFrom?(ref: string, paths: string[]): string[];
  branchExists?(branch: string): boolean;
  deleteBranch?(branch: string, force?: boolean): void;
}

export interface ExitFinalizeResult {
  /** 跳过原因（无检查点/不在检查点分支上）；非空 = 未做任何 git 操作 */
  skipped: string | null;
  /** 归档分支名（有独有内容且归档成功） */
  archived: string | null;
  /** 取回工作区的文件（"未提交改动"形态） */
  restored: string[];
  /** 退出前切到的干线分支 */
  checkedOutTo: string | null;
  /** 归档成功后删除的检查点分支 */
  deleted: string | null;
  /** 部分失败信息（不抛出，仍允许退出；检查点分支此时保留） */
  error: string | null;
}

export function exitFinalize(
  repo: ExitFinalizeRepo,
  opts: { checkpoint: string | null; base: string; now?: number },
): ExitFinalizeResult {
  const res: ExitFinalizeResult = {
    skipped: null, archived: null, restored: [], checkedOutTo: null, deleted: null, error: null,
  };
  const { checkpoint, base } = opts;
  if (!checkpoint) { res.skipped = 'no-checkpoint'; return res; }
  const head = repo.currentBranch();
  if (head !== checkpoint) { res.skipped = `not-on-checkpoint(HEAD=${head})`; return res; }
  try {
    const divergent = repo.hasDivergentContent?.(checkpoint, base) ?? false;
    const files = divergent ? (repo.listDivergentFiles?.(checkpoint, base) ?? []) : [];
    if (divergent) {
      res.archived = repo.createArchiveBranch?.(rescueBranchName(checkpoint, opts.now ?? Date.now()), checkpoint) ?? null;
    }
    repo.checkout(base);
    res.checkedOutTo = base;
    if (res.archived && files.length > 0) {
      res.restored = repo.restorePathsFrom?.(res.archived, files) ?? [];
    }
    // 删除条件：已成功切回干线（工作区已就位），且独有内容已有归属（归档成功）或本来就没有独有内容。
    // 归档失败时绝不删——那时 wip 分支是独有内容的唯一载体。
    if (res.checkedOutTo && (!divergent || res.archived) && repo.branchExists?.(checkpoint)) {
      try { repo.deleteBranch?.(checkpoint, true); res.deleted = checkpoint; }
      catch { /* 删不掉就留着（内容全在归档分支，零丢失），不影响退出 */ }
    }
  } catch (e: any) {
    res.error = e?.message ? String(e.message) : String(e);
  }
  return res;
}

/** 收尾结果 → 一句话摘要（工具结果 / osWrite 审计用）；无动作时返回空串 */
export function describeExitFinalize(r: ExitFinalizeResult): string {
  const parts: string[] = [];
  if (r.archived) parts.push(`wip 独有内容已归档到 ${r.archived}`);
  if (r.restored.length > 0) parts.push(`${r.restored.length} 个文件已按未提交改动取回工作区`);
  if (r.checkedOutTo) parts.push(`已回到干线 ${r.checkedOutTo}`);
  if (r.deleted) parts.push(`检查点分支 ${r.deleted} 已收（内容在归档分支）`);
  if (r.error) parts.push(`退出前收尾部分失败：${r.error}（检查点分支保留，内容未丢）`);
  return parts.join('；');
}
