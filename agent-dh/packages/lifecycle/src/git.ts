import { execFileSync } from 'node:child_process';

export class GitRepo {
  constructor(
    private cwd: string,
    /** 可注入时钟（测试用递增时钟避免同秒建分支撞名；默认真实时间，语义不变） */
    private clock: () => Date = () => new Date(),
  ) {}

  private git(args: string[]): string {
    return execFileSync('git', args, { cwd: this.cwd, encoding: 'utf8' }).trim();
  }

  /** 执行 git 探测命令（忽略非零退出码） */
  private gitTry(args: string[]): boolean {
    try {
      execFileSync('git', args, { cwd: this.cwd, encoding: 'utf8' });
      return true;
    } catch {
      return false;
    }
  }

  currentBranch(): string { return this.git(['branch', '--show-current']); }
  isClean(): boolean { return this.git(['status', '--porcelain']).length === 0; }
  head(): string { return this.git(['rev-parse', 'HEAD']); }

  /** ref（分支或提交）是否存在 */
  refExists(ref: string): boolean {
    return this.gitTry(['rev-parse', '--verify', '--quiet', `${ref}^{commit}`]);
  }

  /** 分支是否存在 */
  branchExists(branch: string): boolean {
    return this.gitTry(['rev-parse', '--verify', '--quiet', `refs/heads/${branch}`]);
  }

  /** ref 是否已并入 into（是 into 的祖先） */
  isMerged(ref: string, into: string): boolean {
    return this.gitTry(['merge-base', '--is-ancestor', ref, into]);
  }

  /**
   * 判断 branch 相对 base 有多少"patch 不等价"的提交（即内容尚未并入 base）。
   * 用 git cherry（patch-id 语义）——比 merge-base 更贴近"内容是否已合入"：
   *   对 branch 上每个提交输出一行，'-' = base 已有等价提交（被 cherry-pick 过），'+' = 无等价。
   * 返回 '+' 行数：0 = branch 全部提交已等价存在于 base。
   */
  cherryPatchMissing(base: string, branch: string): number {
    const out = this.git(['cherry', base, branch]);
    const lines = out.split('\n').filter((l) => l.trim() !== '');
    return lines.filter((l) => l.trim().startsWith('+')).length;
  }

  hasChanges(paths: string[]): boolean {
    return this.git(['status', '--porcelain', '--', ...paths]).length > 0;
  }

  private ts(): string {
    const d = this.clock();
    const p = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
  }

  /** 有改动则建 wip 分支并提交，返回分支名与提交文件清单；无改动返回 null（不切分支） */
  createWipBranch(prefix: string, paths: string[], message: string): { branch: string; files: string[] } | null {
    if (!this.hasChanges(paths)) return null;
    const branch = `${prefix}/${this.ts()}`;
    this.git(['checkout', '-b', branch]);
    this.git(['add', '-A', '--', ...paths]);
    this.git(['commit', '-m', message]);
    const files = this.git(['show', '--pretty=format:', '--name-only', 'HEAD'])
      .split('\n').map((f) => f.trim()).filter(Boolean);
    return { branch, files };
  }

  /** 有改动则提交到当前分支（不切新分支）。wip-on-wip 续提交路径用：已在 agent-self/* 上再次重启时，
   *  不建链式新分支，而是续提交到同一 wip（杜绝 base 溯源断裂与新链滞留）。 */
  commitOnCurrent(paths: string[], message: string): string | null {
    if (!this.hasChanges(paths)) return null;
    this.git(['add', '-A', '--', ...paths]);
    this.git(['commit', '-m', message]);
    return this.head();
  }

  checkout(branch: string): void { this.git(['checkout', branch]); }
  /** 硬重置到指定提交（丢弃工作区未提交改动）——rollback 语义：彻底放弃 wip 检查点的内容 */
  resetHard(ref: string): void { this.git(['reset', '--hard', ref]); }
  /** 快进合并：仅当 branch 是当前 HEAD 的祖先（可快进）时成功，否则抛错 */
  mergeFfOnly(branch: string): void { this.git(['merge', '--ff-only', branch]); }
  /** 删除分支：force=false 用 -d（仅合并过的分支可删，安全）；force=true 用 -D（未合并也删，rollback 语义） */
  deleteBranch(branch: string, force = false): void {
    this.git(force ? ['branch', '-D', branch] : ['branch', '-d', branch]);
  }

  /**
   * 策略化收尾合并（修复 mergeFfOnly 太脆：base 一旦前进 ff 必败，wip 永久滞留"请人工处理"）。
   * 调用方应先 checkout(base)。按序判定：
   *   ① branch 已并入 base（branch 是 base 祖先）→ 无需合并，outcome=already-merged
   *   ② branch 内容已等价在 base（git cherry 全 '-'，patch-id 相同=被 cherry-pick 过）→ 无需合并，
   *     outcome=already-cherried（分支非祖先，删除 wip 需 force=true）
   *   ③ 快进可行（base 是 branch 祖先的反向场景）→ merge --ff-only
   *   ④ 真分叉 → 3-way merge 生成合并提交（冲突则 abort 并抛错交人工，wip 保留不丢内容）
   * 返回 outcome + merged_hash（无新提交时为 base 当前 head）。
   */
  finalizeMerge(
    base: string,
    branch: string,
    mergeMessage: string,
  ): { outcome: 'already-merged' | 'already-cherried' | 'ff-merged' | 'merged' | 'conflict'; merged_hash: string } {
    if (!this.branchExists(branch)) {
      // wip 分支已不存在（先前清理过）——视作已处理，返回 base 当前 head
      return { outcome: 'already-merged', merged_hash: this.head() };
    }
    if (this.isMerged(branch, base)) {
      // ① 内容已物理并入 base
      return { outcome: 'already-merged', merged_hash: this.head() };
    }
    if (this.cherryPatchMissing(base, branch) === 0) {
      // ② 内容已等价并入（cherry-pick 过，hash 不同 → 非祖先 → 需 force 删除）
      return { outcome: 'already-cherried', merged_hash: this.head() };
    }
    try {
      // ③ 快进优先
      this.mergeFfOnly(branch);
      return { outcome: 'ff-merged', merged_hash: this.head() };
    } catch {
      try {
        // ④ base 前进过：3-way 合并提交
        this.git(['merge', '--no-ff', branch, '-m', mergeMessage]);
        return { outcome: 'merged', merged_hash: this.head() };
      } catch (e: any) {
        try { this.git(['merge', '--abort']); } catch { /* 忽略 */ }
        throw new Error(`3-way merge 冲突：${e?.message ?? e}（wip=${branch} 已中止合并并保留，待人工处理）`);
      }
    }
  }

  /**
   * 整链清理：合并成功后删除所有"内容已并入 ref"的 agent-self/* 遗留分支（同一 wip 链上的兄弟/祖先分支）。
   * 判定与 finalizeMerge 一致：物理祖先或 patch 等价即视为已收，可安全删除。
   * 绝不删除内容未并入的分支（如 144904 内容仍在 feat 分支上未入 main——必须保留）。
   * 返回清理的分支名列表。
   */
  cleanupWipChain(prefix: string, ref: string): string[] {
    const out = this.git(['branch', '--list', `${prefix}/*`]);
    const branches = out.split('\n').map((b) => b.trim()).filter(Boolean);
    const removed: string[] = [];
    for (const b of branches) {
      if (b === this.currentBranch()) continue; // 当前所在分支由调用方处理
      const merged = this.isMerged(b, ref) || this.cherryPatchMissing(ref, b) === 0;
      if (merged) {
        try {
          this.deleteBranch(b, true); // 等价并入场景非祖先，须 -D
          removed.push(b);
        } catch { /* 删除失败不阻塞（如被锁），留待下次 */ }
      }
    }
    return removed;
  }

  /**
   * 溯源 agent-self/* wip 分支的"链根干线"（改动1/改动2 共用）。链式 wip（agent-self/A → agent-self/B，
   * 旧版 restart 在 wip 上又重启造成）时，B 的父提交在 A 上、A 的父提交在干线上——沿 first-parent
   * 向上找第一个"父提交不落在任何 agent-self/* 分支上"的提交，其父所在分支即链根干线。
   * 返回干线分支名（优先 main/master）；溯源失败返回 null。
   */
  resolveChainBase(wipBranch: string): string | null {
    if (!this.branchExists(wipBranch)) return null; // 分支不存在 → 无可溯源
    const log = this.git(['log', '--format=%H', '--first-parent', wipBranch]);
    const commits = log.split('\n').map((s) => s.trim()).filter(Boolean);
    for (const c of commits) {
      // 该提交的父提交（切出点）；根提交无父则跳过
      let parent: string;
      try { parent = this.git(['rev-parse', c + '^']); } catch { continue; }
      const containing = this.git(['branch', '--contains', parent, '--format=%(refname:short)'])
        .split('\n').map((s) => s.trim()).filter(Boolean);
      const realBranches = containing.filter((b) => !b.startsWith('agent-self/'));
      if (realBranches.length > 0) {
        // 找到干线：父提交落在非 agent-self 分支上
        return realBranches.find((b) => b === 'main' || b === 'master') ?? realBranches[0];
      }
      // 父提交也在 agent-self/* 上 → 链式 wip，继续向上溯
    }
    return null;
  }
}
