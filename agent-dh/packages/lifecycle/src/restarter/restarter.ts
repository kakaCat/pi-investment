/**
 * Agent-DH 自重启器（lifecycle 包内实现，独立进程，agent 死后继续执行）。
 * 由 self_restart 工具（scheduleRestart）spawn：node dist/restarter.mjs <pid> <port> <repoRoot> <stateDir> <startScript> <logPath>
 *
 * 职责: sleep → kill 旧进程 → start.sh 拉起 → 端口健康检查 → 失败自动回滚 base 分支重拉。
 * 约束: 自包含，只准 import node 内置模块（不依赖 tsx、不依赖任何 @pi-investment 包）。
 * 测试钩子:
 *   SELF_RESTART_DRY_RUN=1            演练模式：不 kill/不 git/不启动，只验证参数、写结果、释放锁
 *   SELF_RESTART_PRE_KILL_DELAY_MS=…   覆盖 kill 前等待（默认 5000ms）
 *   SELF_RESTART_HEALTH_TIMEOUT_MS=…   覆盖健康检查超时（默认 120000ms）
 */
import { execFileSync, spawn } from 'node:child_process';
import { appendFileSync, copyFileSync, existsSync, mkdirSync, openSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { pathToFileURL } from 'node:url';

export const USAGE = '用法: node dist/restarter.mjs <pid> <port> <repoRoot> <stateDir> <startScript> <logPath>';

export interface RestarterArgs {
  pid: number;
  port: number;
  repoRoot: string;
  stateDir: string;
  startScript: string;
  logPath: string;
}

export function parseArgs(argv: string[]): RestarterArgs {
  const [pidS, portS, repoRoot, stateDir, startScript, logPath] = argv;
  const pid = Number(pidS);
  const port = Number(portS);
  if (!pidS || !portS || !repoRoot || !stateDir || !startScript || !logPath || !Number.isFinite(pid) || !Number.isFinite(port)) {
    throw new Error(USAGE);
  }
  return { pid, port, repoRoot, stateDir, startScript, logPath };
}

/** A-5（2026-08-21）：profile 侧配置文件（cordis.patch.yml/package.json）不在 git 安全网内，
 *  若新插件配置导致启动失败，git 回滚救不回来（patch.yml 仍引用坏插件 → boot loop）。
 *  每次重启前备份，回滚路径先恢复配置再重拉。 */
function backupProfileConfigs(opts: { profileDir: string; configBackupDir: string; log: (m: string) => void }): void {
  const { profileDir, configBackupDir, log } = opts;
  try {
    mkdirSync(configBackupDir, { recursive: true });
    for (const f of ['cordis.patch.yml', 'package.json']) {
      const src = join(profileDir, f);
      if (existsSync(src)) copyFileSync(src, join(configBackupDir, f));
    }
    log('profile configs backed up');
  } catch (e) { log('config backup failed (non-fatal): ' + String(e)); }
}

function restoreProfileConfigs(opts: { profileDir: string; configBackupDir: string; log: (m: string) => void }): void {
  const { profileDir, configBackupDir, log } = opts;
  try {
    for (const f of ['cordis.patch.yml', 'package.json']) {
      const bak = join(configBackupDir, f);
      if (existsSync(bak)) copyFileSync(bak, join(profileDir, f));
    }
    log('profile configs restored from backup');
  } catch (e) { log('config restore failed (non-fatal): ' + String(e)); }
}

export interface RestarterEnv {
  dryRun?: boolean;
  preKillDelayMs?: number;
  healthTimeoutMs?: number;
}

export function makeLogger(logPath: string): (msg: string) => void {
  return (msg: string) => {
    try {
      appendFileSync(logPath, '[' + new Date().toISOString() + '] ' + msg + '\n');
    } catch { /* 日志失败不致命 */ }
  };
}

export function writeResultFile(stateDir: string, result: Record<string, unknown>): void {
  const finalPath = join(stateDir, 'restart-result.json');
  const tmpPath = finalPath + '.tmp';
  writeFileSync(tmpPath, JSON.stringify({ ...result, ts: new Date().toISOString() }, null, 2));
  renameSync(tmpPath, finalPath);
}

export function finish(stateDir: string, result: Record<string, unknown>): void {
  writeResultFile(stateDir, result);
  rmSync(join(stateDir, 'restarting.lock'), { force: true });
}

/** 主流程。导出供测试/复用；被直接执行时由入口调用。 */
export async function runRestarter(args: RestarterArgs, env: RestarterEnv = {}): Promise<void> {
  const { pid, port, repoRoot, stateDir, startScript, logPath } = args;
  const dryRun = env.dryRun ?? false;
  const preKillDelayMs = env.preKillDelayMs ?? 5000;
  const healthTimeoutMs = env.healthTimeoutMs ?? 120_000;
  const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
  const log = makeLogger(logPath);
  const profileDir = dirname(startScript);
  const configBackupDir = join(stateDir, 'config-backup-auto');

  const git = (gArgs: string[]): string => execFileSync('git', gArgs, { cwd: repoRoot, encoding: 'utf8' }).trim();

  const readPending = (): { base_branch: string; checkpoint_branch: string | null; attempt: number } => {
    const p = join(stateDir, 'pending-resume.json');
    if (!existsSync(p)) throw new Error('pending-resume.json 不存在，无法回滚');
    return JSON.parse(readFileSync(p, 'utf8'));
  };

  const waitPort = async (timeoutMs: number): Promise<boolean> => {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      try {
        const res = await fetch('http://127.0.0.1:' + port + '/', { signal: AbortSignal.timeout(3000) });
        if (res.status > 0) return true; // 端口通即可，不关心状态码
      } catch { /* 还没起来 */ }
      await sleep(2000);
    }
    return false;
  };

  const startAgent = (): void => {
    const out = openSync(logPath, 'a');
    const child = spawn('bash', [startScript, String(port)], { detached: true, stdio: ['ignore', out, out] });
    child.unref();
    log('spawned start.sh pid=' + child.pid);
  };

  const killOld = async (): Promise<void> => {
    try { process.kill(pid, 'SIGTERM'); } catch { return; }
    for (let i = 0; i < 30; i++) {
      try { process.kill(pid, 0); } catch { log('old pid=' + pid + ' exited'); return; }
      await sleep(1000);
    }
    try { process.kill(pid, 'SIGKILL'); } catch { /* already dead */ }
    log('old pid=' + pid + ' SIGKILLed');
  };

  log('self-restart start: pid=' + pid + ' port=' + port + ' dryRun=' + dryRun);
  if (dryRun) {
    // 演练模式：跳过全部副作用，验证参数/日志/结果/锁释放链路
    backupProfileConfigs({ profileDir, configBackupDir, log });
    writeResultFile(stateDir, { status: 'ok', dry_run: true });
    finish(stateDir, { status: 'ok', dry_run: true });
    log('DRY RUN complete (no kill/git/start performed)');
    return;
  }

  await sleep(preKillDelayMs); // 给 agent 留时间输出完回复、落盘会话
  await killOld();

  backupProfileConfigs({ profileDir, configBackupDir, log });

  // 预写结果：新进程的 lifecycle 插件在构造期（早于 HTTP 监听）读 restart-result.json，
  // 若等健康检查通过后才写，插件读到的是上一周期的旧结果（rolled_back 会被误报为成功）。
  writeResultFile(stateDir, { status: 'ok' });
  startAgent();
  if (await waitPort(healthTimeoutMs)) {
    log('health check ok');
    finish(stateDir, { status: 'ok' });
    return;
  }

  // 启动失败：回滚到 base 分支重拉一次
  let pending: { base_branch: string; checkpoint_branch: string | null; attempt: number };
  try {
    pending = readPending();
  } catch (e) {
    log('rollback aborted: ' + String(e));
    finish(stateDir, { status: 'dead', failed_branch: null, log_path: logPath, error: String(e) });
    return;
  }
  log('health check FAILED, rolling back to ' + pending.base_branch);
  try {
    git(['checkout', pending.base_branch]);
  } catch (e) {
    log('git checkout ' + pending.base_branch + ' failed: ' + String(e));
    finish(stateDir, { status: 'dead', failed_branch: pending.checkpoint_branch, log_path: logPath, error: 'rollback checkout failed' });
    return;
  }
  // 同样预写：回滚后的第二次启动，插件构造期必须能读到 rolled_back
  writeResultFile(stateDir, { status: 'rolled_back', failed_branch: pending.checkpoint_branch, log_path: logPath });
  restoreProfileConfigs({ profileDir, configBackupDir, log });
  startAgent();
  if (await waitPort(healthTimeoutMs)) {
    log('rollback boot ok');
    finish(stateDir, { status: 'rolled_back', failed_branch: pending.checkpoint_branch, log_path: logPath });
  } else {
    log('rollback boot FAILED, giving up');
    finish(stateDir, { status: 'dead', failed_branch: pending.checkpoint_branch, log_path: logPath });
  }
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const dryRun = process.env.SELF_RESTART_DRY_RUN === '1';
  const preKillDelayMs = Number(process.env.SELF_RESTART_PRE_KILL_DELAY_MS) || undefined;
  const healthTimeoutMs = Number(process.env.SELF_RESTART_HEALTH_TIMEOUT_MS) || undefined;
  await runRestarter(args, { dryRun, preKillDelayMs, healthTimeoutMs });
}

// 仅直接执行时运行（被打包成 dist/restarter.mjs 后 argv[1] 即本文件）
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((e) => {
    const msg = String(e && e.message ? e.message : e);
    try {
      const args = parseArgs(process.argv.slice(2));
      appendFileSync(args.logPath, '[' + new Date().toISOString() + '] restarter crashed: ' + msg + '\n');
    } catch { /* 参数都解析不了时无处写日志 */ }
    console.error(msg);
    process.exitCode = 1;
  });
}
