import { execFileSync } from 'node:child_process';

function timestamp(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

export class GitRepo {
  constructor(private cwd: string) {}

  private git(args: string[]): string {
    return execFileSync('git', args, { cwd: this.cwd, encoding: 'utf8' }).trim();
  }

  currentBranch(): string { return this.git(['branch', '--show-current']); }
  isClean(): boolean { return this.git(['status', '--porcelain']).length === 0; }
  head(): string { return this.git(['rev-parse', 'HEAD']); }

  hasChanges(paths: string[]): boolean {
    return this.git(['status', '--porcelain', '--', ...paths]).length > 0;
  }

  /** 有改动则建 wip 分支并提交，返回分支名与提交文件清单；无改动返回 null（不切分支） */
  createWipBranch(prefix: string, paths: string[], message: string): { branch: string; files: string[] } | null {
    if (!this.hasChanges(paths)) return null;
    const branch = `${prefix}/${timestamp()}`;
    this.git(['checkout', '-b', branch]);
    this.git(['add', '-A', '--', ...paths]);
    this.git(['commit', '-m', message]);
    const files = this.git(['show', '--pretty=format:', '--name-only', 'HEAD'])
      .split('\n').map((f) => f.trim()).filter(Boolean);
    return { branch, files };
  }

  checkout(branch: string): void { this.git(['checkout', branch]); }
  /** 硬重置到指定提交（丢弃工作区未提交改动）——rollback 语义：彻底放弃 wip 检查点的内容 */
  resetHard(ref: string): void { this.git(['reset', '--hard', ref]); }
  mergeFfOnly(branch: string): void { this.git(['merge', '--ff-only', branch]); }
  /** 删除分支：force=false 用 -d（仅合并过的分支可删，安全）；force=true 用 -D（未合并也删，rollback 语义） */
  deleteBranch(branch: string, force = false): void {
    this.git(force ? ['branch', '-D', branch] : ['branch', '-d', branch]);
  }
}
