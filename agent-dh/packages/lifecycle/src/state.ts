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
    return JSON.parse(readFileSync(p, 'utf8')) as T;
  }

  readPending(): PendingResume | null { return this.readJson('pending-resume.json'); }
  writePending(p: PendingResume): void { this.writeJson('pending-resume.json', p); }

  markPendingDone(): void {
    const p = this.path('pending-resume.json');
    if (existsSync(p)) renameSync(p, this.path('pending-resume.done.json'));
  }

  readPendingDone(): PendingResume | null { return this.readJson('pending-resume.done.json'); }
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

  acquireLock(): boolean {
    try {
      writeFileSync(this.path('restarting.lock'), String(Date.now()), { flag: 'wx' });
      return true;
    } catch {
      return false;
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
