/**
 * Agent-DH 自重启器（独立进程，agent 死后继续执行）。
 * 用法: node --import tsx/esm scripts/self-restart.ts <pid> <port> <repoRoot> <stateDir> <startScript> <logPath>
 * 职责: sleep → kill 旧进程 → start.sh 拉起 → 端口健康检查 → 失败自动回滚 base 分支重拉。
 * 约束: 自包含，只准 import node 内置模块。
 */
import { execFileSync, spawn } from 'node:child_process';
import { appendFileSync, openSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const [pidS, portS, repoRoot, stateDir, startScript, logPath] = process.argv.slice(2);
const pid = Number(pidS);
const port = Number(portS);

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

function writeResult(result: Record<string, unknown>): void {
  writeFileSync(join(stateDir, 'restart-result.json'), JSON.stringify({ ...result, ts: new Date().toISOString() }, null, 2));
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
  await sleep(5000); // 给 agent 留时间输出完回复、落盘会话
  await killOld();

  startAgent();
  if (await waitPort(120_000)) {
    log('health check ok');
    writeResult({ status: 'ok' });
    return;
  }

  // 启动失败：回滚到 base 分支重拉一次
  const pending = readPending();
  log(`health check FAILED, rolling back to ${pending.base_branch}`);
  try {
    git(['checkout', pending.base_branch]);
  } catch (e) {
    log(`git checkout ${pending.base_branch} failed: ${String(e)}`);
    writeResult({ status: 'dead', failed_branch: pending.checkpoint_branch, log_path: logPath, error: 'rollback checkout failed' });
    return;
  }
  startAgent();
  if (await waitPort(120_000)) {
    log('rollback boot ok');
    writeResult({ status: 'rolled_back', failed_branch: pending.checkpoint_branch, log_path: logPath });
  } else {
    log('rollback boot FAILED, giving up');
    writeResult({ status: 'dead', failed_branch: pending.checkpoint_branch, log_path: logPath });
  }
}

main().catch((e) => {
  log(`restarter crashed: ${String(e)}`);
  writeResult({ status: 'dead', log_path: logPath, error: String(e) });
  process.exitCode = 1;
});
