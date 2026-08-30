/**
 * ⚠️ DEPRECATED（2026-08-30）：重启器已收进 lifecycle 包（packages/lifecycle/src/restarter/restarter.ts，
 * 构建产物 packages/lifecycle/dist/restarter/restarter.mjs），self_restart 工具改为 spawn 包内重启器，
 * 不再依赖本脚本。本文件仅存档，勿再引用。
 *
 * Agent-DH 自重启器（独立进程，agent 死后继续执行）。
 * 用法: node --import tsx/esm scripts/self-restart.ts <pid> <port> <repoRoot> <stateDir> <startScript> <logPath>
 * 职责: sleep → kill 旧进程 → start.sh 拉起 → 端口健康检查 → 失败自动回滚 base 分支重拉。
 * 约束: 自包含，只准 import node 内置模块。
 */
import { execFileSync, spawn } from 'node:child_process';
import { appendFileSync, copyFileSync, existsSync, mkdirSync, openSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

const [pidS, portS, repoRoot, stateDir, startScript, logPath] = process.argv.slice(2);
const pid = Number(pidS);
const port = Number(portS);
// 测试/调优钩子：环境变量覆盖等待时长（生产缺省 5s 启动延迟、120s 健康检查）
const PRE_KILL_DELAY_MS = Number(process.env.SELF_RESTART_PRE_KILL_DELAY_MS) || 5000;
const HEALTH_TIMEOUT_MS = Number(process.env.SELF_RESTART_HEALTH_TIMEOUT_MS) || 120_000;

// A-5（2026-08-21）：profile 侧配置文件（cordis.patch.yml/package.json）不在 git 安全网内，
// 若新插件配置导致启动失败，git 回滚救不回来（patch.yml 仍引用坏插件 → boot loop）。
// 每次重启前备份，回滚路径先恢复配置再重拉。
const profileDir = dirname(startScript);
const configBackupDir = join(stateDir, 'config-backup-auto');
const PROFILE_CONFIGS = ['cordis.patch.yml', 'package.json'];

function backupProfileConfigs(): void {
  try {
    mkdirSync(configBackupDir, { recursive: true });
    for (const f of PROFILE_CONFIGS) {
      const src = join(profileDir, f);
      if (existsSync(src)) copyFileSync(src, join(configBackupDir, f));
    }
    log('profile configs backed up');
  } catch (e) { log(`config backup failed (non-fatal): ${String(e)}`); }
}

function restoreProfileConfigs(): void {
  try {
    for (const f of PROFILE_CONFIGS) {
      const bak = join(configBackupDir, f);
      if (existsSync(bak)) copyFileSync(bak, join(profileDir, f));
    }
    log('profile configs restored from backup');
  } catch (e) { log(`config restore failed (non-fatal): ${String(e)}`); }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const log = (msg: string) => {
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  appendFileSync(logPath, line);
};

function git(args: string[]): string {
  return execFileSync('git', args, { cwd: repoRoot, encoding: 'utf8' }).trim();
}

function readPending(): { base_branch: string; checkpoint_branch: string | null; attempt: number } {
  return JSON.parse(readFileSync(join(stateDir, 'pending-resume.json'), 'utf8'));
}

/**
 * 原子写 restart-result.json（tmp+rename，防写途中被强杀留下截断 JSON）。
 * 不动 restarting.lock —— 锁只在流程终结时由 finish() 清除。
 */
function writeResultFile(result: Record<string, unknown>): void {
  const finalPath = join(stateDir, 'restart-result.json');
  const tmpPath = finalPath + '.tmp';
  writeFileSync(tmpPath, JSON.stringify({ ...result, ts: new Date().toISOString() }, null, 2));
  renameSync(tmpPath, finalPath);
}

/** 终态写结果并释放 restarting.lock */
function finish(result: Record<string, unknown>): void {
  writeResultFile(result);
  rmSync(join(stateDir, 'restarting.lock'), { force: true });
}

async function waitPort(timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/`, { signal: AbortSignal.timeout(3000) });
      if (res.status > 0) return true; // 端口通即可，不关心状态码
    } catch { /* 还没起来 */ }
    await sleep(2000);
  }
  return false;
}

function startAgent(): void {
  const out = openSync(logPath, 'a');
  const child = spawn('bash', [startScript, String(port)], {
    detached: true,
    stdio: ['ignore', out, out],
  });
  child.unref();
  log(`spawned start.sh pid=${child.pid}`);
}

async function killOld(): Promise<void> {
  try { process.kill(pid, 'SIGTERM'); } catch { return; }
  for (let i = 0; i < 30; i++) {
    try { process.kill(pid, 0); } catch { log(`old pid=${pid} exited`); return; }
    await sleep(1000);
  }
  try { process.kill(pid, 'SIGKILL'); } catch { /* already dead */ }
  log(`old pid=${pid} SIGKILLed`);
}

async function main(): Promise<void> {
  log(`self-restart start: pid=${pid} port=${port}`);
  await sleep(PRE_KILL_DELAY_MS); // 给 agent 留时间输出完回复、落盘会话
  await killOld();

  backupProfileConfigs();  // A-5：拉起前先备份 profile 配置

  // 预写结果：新进程的 lifecycle 插件在构造期（早于 HTTP 监听）读 restart-result.json，
  // 若等健康检查通过后才写，插件读到的是上一周期的旧结果（rolled_back 会被误报为成功）。
  // 结果文件只被成功启动的进程读取，预写不产生谎言窗口。
  writeResultFile({ status: 'ok' });
  startAgent();
  if (await waitPort(HEALTH_TIMEOUT_MS)) {
    log('health check ok');
    finish({ status: 'ok' });
    return;
  }

  // 启动失败：回滚到 base 分支重拉一次
  const pending = readPending();
  log(`health check FAILED, rolling back to ${pending.base_branch}`);
  try {
    git(['checkout', pending.base_branch]);
  } catch (e) {
    log(`git checkout ${pending.base_branch} failed: ${String(e)}`);
    finish({ status: 'dead', failed_branch: pending.checkpoint_branch, log_path: logPath, error: 'rollback checkout failed' });
    return;
  }
  // 同样预写：回滚后的第二次启动，插件构造期必须能读到 rolled_back
  writeResultFile({ status: 'rolled_back', failed_branch: pending.checkpoint_branch, log_path: logPath });
  restoreProfileConfigs();  // A-5：git 回滚不管 profile 配置，必须先恢复再重拉
  startAgent();
  if (await waitPort(HEALTH_TIMEOUT_MS)) {
    log('rollback boot ok');
    finish({ status: 'rolled_back', failed_branch: pending.checkpoint_branch, log_path: logPath });
  } else {
    log('rollback boot FAILED, giving up');
    finish({ status: 'dead', failed_branch: pending.checkpoint_branch, log_path: logPath });
  }
}

main().catch((e) => {
  log(`restarter crashed: ${String(e)}`);
  finish({ status: 'dead', log_path: logPath, error: String(e) });
  process.exitCode = 1;
});
