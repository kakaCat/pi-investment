import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';

export interface PendingResume {
  reason: string;
  resume_task: string;
  checkpoint_branch: string | null;
  base_branch: string;
  last_known_good: string;
  attempt: number;
  ts: string;
}

export interface RestartResult {
  status: 'ok' | 'rolled_back' | 'dead';
  failed_branch?: string;
  log_path?: string;
  ts: string;
}

interface RestartCounter { window_start: number; count: number }
interface AttemptState { task: string; count: number }

const RATE_WINDOW_MS = 3_600_000;

export class StateStore {
  constructor(private dir: string) {
    mkdirSync(dir, { recursive: true });
  }

  private path(name: string): string { return join(this.dir, name); }

  /** 原子写：先 tmp 再 rename，进程被 kill 也不留半截文件 */
  private writeJson(name: string, value: unknown): void {
    const tmp = this.path(name + '.tmp');
    writeFileSync(tmp, JSON.stringify(value, null, 2));
    renameSync(tmp, this.path(name));
  }

  private readJson<T>(name: string): T | null {
    const p = this.path(name);
    if (!existsSync(p)) return null;
    try {
      return JSON.parse(readFileSync(p, 'utf8')) as T;
    } catch {
      // 文件截断/损坏（如写途中被强杀）按无状态处理，不能让读异常击穿插件加载
      return null;
    }
  }

  readPending(): PendingResume | null { return this.readJson('pending-resume.json'); }
  writePending(p: PendingResume): void { this.writeJson('pending-resume.json', p); }

  markPendingDone(): void {
    const p = this.path('pending-resume.json');
    if (existsSync(p)) renameSync(p, this.path('pending-resume.done.json'));
  }

  readPendingDone(): PendingResume | null { return this.readJson('pending-resume.done.json'); }
  /** finalize 完成后清掉 done 文件，保证 self_finalize 可重复调用不报错 */
  clearPendingDone(): void { rmSync(this.path('pending-resume.done.json'), { force: true }); }
  readRestartResult(): RestartResult | null { return this.readJson('restart-result.json'); }

  checkRateLimit(maxPerHour: number, now: number): { allowed: boolean; count: number } {
    const c = this.readJson<RestartCounter>('restart-counter.json');
    const count = c && now - c.window_start < RATE_WINDOW_MS ? c.count : 0;
    return { allowed: count < maxPerHour, count };
  }

  bumpCounter(now: number): void {
    const c = this.readJson<RestartCounter>('restart-counter.json');
    if (c && now - c.window_start < RATE_WINDOW_MS) {
      this.writeJson('restart-counter.json', { window_start: c.window_start, count: c.count + 1 });
    } else {
      this.writeJson('restart-counter.json', { window_start: now, count: 1 });
    }
  }

  /**
   * 互斥锁（wx 独占创建）。锁内容为获取时刻的时间戳：
   * 发现锁已存在且超过 staleMs（默认 15 分钟，覆盖最长单次重启周期），
   * 视为机器掉电/重启器被强杀留下的死锁，强行接管。
   */
  acquireLock(staleMs = 15 * 60 * 1000): boolean {
    try {
      writeFileSync(this.path('restarting.lock'), String(Date.now()), { flag: 'wx' });
      return true;
    } catch {
      try {
        const ts = Number(readFileSync(this.path('restarting.lock'), 'utf8'));
        if (!Number.isFinite(ts) || Date.now() - ts <= staleMs) return false;
        rmSync(this.path('restarting.lock'), { force: true });
        writeFileSync(this.path('restarting.lock'), String(Date.now()), { flag: 'wx' });
        return true;
      } catch {
        return false; // 接管竞争失败，按未获取处理
      }
    }
  }

  releaseLock(): void {
    rmSync(this.path('restarting.lock'), { force: true });
  }

  nextAttempt(task: string): number {
    const a = this.readJson<AttemptState>('attempt.json');
    const count = a && a.task === task ? a.count + 1 : 1;
    this.writeJson('attempt.json', { task, count });
    return count;
  }

  clearAttempt(): void { rmSync(this.path('attempt.json'), { force: true }); }

  readLastKnownGood(): string | null {
    const p = this.path('last-known-good');
    return existsSync(p) ? readFileSync(p, 'utf8').trim() : null;
  }

  writeLastKnownGood(hash: string): void {
    const tmp = this.path('last-known-good.tmp');
    writeFileSync(tmp, hash);
    renameSync(tmp, this.path('last-known-good'));
  }
}
