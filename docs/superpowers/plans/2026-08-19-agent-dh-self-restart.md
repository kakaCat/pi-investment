# Agent-DH 自修复重启工具 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 agent-dh 增加 lifecycle 插件（self_restart/self_finalize/self_status 三工具）+ 独立 TS 重启器，实现带 git wip 分支安全网的自修复重启与自动续跑闭环。

**Architecture:** lifecycle 插件跑在 DSH 进程内负责 git 检查点与状态落盘；`scripts/self-restart.ts` 以 detached 进程执行 kill→拉起→健康检查→失败自动回滚；新进程 ready 后插件通过 `ctx.agents` 注册表拿到 investor agent 并 `followup()` 注入续跑消息。

**Tech Stack:** TypeScript（tsx 模式直跑）、cordis Service、vitest、git CLI。

**设计依据:** [docs/rfcs/002-agent-dh-self-restart.md](../../rfcs/002-agent-dh-self-restart.md)（commit 0540e39a）

---

## 通用执行规则块（每个任务提示词开头逐字复制）

```
你是 pi-investment 仓库的执行工程师。通用规则：
1. 必须在 worktree 中工作：git worktree add .claude/worktrees/self-restart -b feat/agent-dh-self-restart，
   建后立即 git rebase main（基于本地 main，不是 origin/main）。所有改动只发生在这个 worktree。
2. 只准新建/修改本任务 Files 列出的文件，其他文件一律不碰。
3. 契约代码逐字复制，不许自创字段名、文件名、参数名。
4. 测试命令写死：在 worktree 的 agent-dh 目录下执行 pnpm --filter @pi-investment/lifecycle test。
   （若依赖未装，先在 worktree 的 agent-dh 目录执行 pnpm install。）
5. 每个验收命令必须真跑并把真实输出贴回来；禁止声称"通过"而不贴输出。
6. 禁止 git push、禁止合并 main；完成后 git add 本任务文件并 commit 即可，Claude 验收后统一 merge-back。
7. 仓库约定：pi-investment 是 monorepo，agent-dh 是其子目录；git 命令的 cwd 是仓库根（worktree 根），
   但 wip 提交只 add agent-dh/ 路径。
```

## 并行轨道图与难度分级

```
轨道A: Task 2 (state.ts)  ──┐
轨道B: Task 3 (git.ts)    ──┼──> Task 5 (index.ts 插件) ──> Task 6 (profile 注册) ──> Task 7 (E2E) ──> Task 8 (文档)
轨道C: Task 4 (重启器)    ──┘         ▲
Task 1 (脚手架) 是全部任务的前置 ──────┘
```

- **Task 1** 脚手架（L，机械）
- **Task 2** state.ts（M，契约已写死）— 依赖 Task 1，与 3/4 并行
- **Task 3** git.ts（M，契约已写死）— 依赖 Task 1，与 2/4 并行
- **Task 4** self-restart.ts 重启器（M，代码已写死但涉及进程生命周期，Claude 重点审）— 依赖 Task 1，与 2/3 并行
- **Task 5** index.ts 插件（H，cordis 生命周期 + agent 注入，Claude 亲审或亲做）— 依赖 2/3/4
- **Task 6** profile 注册（L）— 依赖 5；注意改的是 `~/.dsh/profiles/investment/`（仓库外）
- **Task 7** E2E 验收（H，Claude 亲做）
- **Task 8** 文档更新（L）— 依赖 7

文件不相交证明：Task 2 只碰 `src/state.ts`+`src/state.test.ts`；Task 3 只碰 `src/git.ts`+`src/git.test.ts`；Task 4 只碰 `scripts/self-restart.ts`；三者无交集，可并行。

## Claude 验收规程

1. 对照本计划逐字核对契约（文件名、导出名、参数名、状态文件字段）
2. 亲自跑：`pnpm --filter @pi-investment/lifecycle test` 必须全绿
3. 回查事实源：`ctx.agents.roots()`、`agent.followup()`、`createUserMessage` 的用法必须与 `vendor/dsh/agent/lib/types/` 和 DSH schedule 包一致
4. E2E 两条路径（正常+崩溃回滚）必须真实跑过并贴输出
5. 全过后走 merge-back；任何一项不过打回重做

---

### Task 1: lifecycle 包脚手架（L）

**Files:**
- Create: `agent-dh/packages/lifecycle/package.json`
- Modify: `agent-dh/package.json`（devDependencies 加 tsx）

**说明：** lifecycle 重启器以 `node --import tsx/esm` 运行，tsx 必须是 agent-dh 根的显式 devDependency（pnpm 隔离 node_modules，传递依赖不可见）。

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "@pi-investment/lifecycle",
  "version": "0.1.0",
  "description": "lifecycle plugin for Agent-DH: self-restart with git safety net",
  "type": "module",
  "main": "./src/index.ts",
  "exports": {
    ".": {
      "import": "./src/index.ts",
      "types": "./src/index.ts"
    }
  },
  "scripts": {
    "test": "vitest run --passWithNoTests"
  },
  "dependencies": {
    "@deepseek-ai/cordis": "workspace:^",
    "@deepseek-ai/schemastery": "workspace:^",
    "@deepseek-ai/dsh-tools": "workspace:^",
    "@deepseek-ai/dsh-llm": "workspace:^",
    "@deepseek-ai/dsh-agent": "workspace:^"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "typescript": "^5.3.3"
  }
}
```

- [ ] **Step 2: agent-dh 根加 tsx 并安装**

```bash
cd agent-dh && pnpm add -Dw tsx && pnpm install
```

预期：`packages/lifecycle/node_modules` 生成；`node --import tsx/esm -e "console.log('ok')"` 在 agent-dh 目录下输出 `ok`。

- [ ] **Step 3: Commit**

```bash
git add agent-dh/packages/lifecycle/package.json agent-dh/package.json agent-dh/pnpm-lock.yaml
git commit -m "feat(agent-dh): lifecycle 包脚手架 + tsx devDep"
```

---

### Task 2: state.ts 状态存取（M）

**Files:**
- Create: `agent-dh/packages/lifecycle/src/state.ts`
- Test: `agent-dh/packages/lifecycle/src/state.test.ts`

**职责：** pending-resume / restart-result / 速率计数 / 锁文件 / attempt 计数的全部读写。所有写操作先写临时文件再 rename（防中途崩溃留半截 JSON——本进程随时可能被 kill）。

- [ ] **Step 1: 写失败测试** `src/state.test.ts`

```typescript
import { mkdtempSync, readFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { StateStore } from './state.js';

describe('StateStore', () => {
  let dir: string;
  let store: StateStore;
  beforeEach(() => { dir = mkdtempSync(join(tmpdir(), 'lifecycle-')); store = new StateStore(dir); });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  it('pending 写读回环 + markDone 改名', () => {
    expect(store.readPending()).toBeNull();
    store.writePending({
      reason: 'r', resume_task: 't', checkpoint_branch: 'agent-self/x',
      base_branch: 'main', last_known_good: 'abc', attempt: 1, ts: '2026-08-19T00:00:00Z',
    });
    expect(store.readPending()?.checkpoint_branch).toBe('agent-self/x');
    store.markPendingDone();
    expect(store.readPending()).toBeNull();
    expect(existsSync(join(dir, 'pending-resume.done.json'))).toBe(true);
    expect(JSON.parse(readFileSync(join(dir, 'pending-resume.done.json'), 'utf8')).resume_task).toBe('t');
  });

  it('速率限制：窗口内计数，超窗重置', () => {
    const now = Date.parse('2026-08-19T10:00:00Z');
    expect(store.checkRateLimit(3, now).allowed).toBe(true);
    store.bumpCounter(now);
    store.bumpCounter(now);
    store.bumpCounter(now);
    expect(store.checkRateLimit(3, now).allowed).toBe(false);
    const later = now + 3_700_000; // 超过 1 小时
    expect(store.checkRateLimit(3, later).allowed).toBe(true);
  });

  it('锁文件互斥获取与释放', () => {
    expect(store.acquireLock()).toBe(true);
    expect(store.acquireLock()).toBe(false); // 重入被拒
    store.releaseLock();
    expect(store.acquireLock()).toBe(true);
  });

  it('attempt 计数：同任务累加，换任务重置，clearAttempt 清零', () => {
    expect(store.nextAttempt('修复A')).toBe(1);
    expect(store.nextAttempt('修复A')).toBe(2);
    expect(store.nextAttempt('修复B')).toBe(1);
    store.clearAttempt();
    expect(store.nextAttempt('修复B')).toBe(1);
  });

  it('last-known-good 读写', () => {
    expect(store.readLastKnownGood()).toBeNull();
    store.writeLastKnownGood('deadbeef');
    expect(store.readLastKnownGood()).toBe('deadbeef');
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd agent-dh && pnpm --filter @pi-investment/lifecycle test
```
预期：FAIL（`./state.js` 不存在）。

- [ ] **Step 3: 实现** `src/state.ts`

```typescript
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
```

- [ ] **Step 4: 跑测试确认全绿**

```bash
cd agent-dh && pnpm --filter @pi-investment/lifecycle test
```
预期：5 个测试 PASS。

- [ ] **Step 5: Commit**

```bash
git add agent-dh/packages/lifecycle/src/state.ts agent-dh/packages/lifecycle/src/state.test.ts
git commit -m "feat(agent-dh): lifecycle StateStore 状态存取 + 测试"
```

---

### Task 3: git.ts git 操作封装（M）

**Files:**
- Create: `agent-dh/packages/lifecycle/src/git.ts`
- Test: `agent-dh/packages/lifecycle/src/git.test.ts`

**职责：** wip 分支检查点 / checkout / ff-only 合并 / 删分支。测试用临时目录建真实 git 仓库。

- [ ] **Step 1: 写失败测试** `src/git.test.ts`

```typescript
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { GitRepo } from './git.js';

describe('GitRepo', () => {
  let dir: string;
  let repo: GitRepo;
  const git = (args: string[]) =>
    execFileSync('git', args, { cwd: dir, encoding: 'utf8' }).trim();

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'lifecycle-git-'));
    git(['init', '-b', 'main']);
    git(['config', 'user.email', 'test@test.com']);
    git(['config', 'user.name', 'test']);
    mkdirSync(join(dir, 'agent-dh'));
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v1');
    git(['add', '-A']);
    git(['commit', '-m', 'init']);
    repo = new GitRepo(dir);
  });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  it('currentBranch / head / hasChanges', () => {
    expect(repo.currentBranch()).toBe('main');
    expect(repo.head()).toMatch(/^[0-9a-f]{40}$/);
    expect(repo.hasChanges(['agent-dh/'])).toBe(false);
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    expect(repo.hasChanges(['agent-dh/'])).toBe(true);
  });

  it('createWipBranch：有改动建新分支并提交，工作区内容不变', () => {
    writeFileSync(join(dir, 'agent-dh/a.txt'), 'v2');
    const mainHead = repo.head();
    const branch = repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: test');
    expect(branch).toMatch(/^agent-self\/\d{8}-\d{6}$/);
    expect(repo.currentBranch()).toBe(branch);
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v2');
    // 回 main 后文件回到 v1，且 wip 分支可 ff 合回
    repo.checkout('main');
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v1');
    repo.mergeFfOnly(branch!);
    expect(repo.head()).not.toBe(mainHead);
    expect(readFileSync(join(dir, 'agent-dh/a.txt'), 'utf8')).toBe('v2');
    repo.deleteBranch(branch!);
    expect(git(['branch', '--list', branch!])).toBe('');
  });

  it('createWipBranch：无改动返回 null 且不建分支', () => {
    expect(repo.createWipBranch('agent-self', ['agent-dh/'], 'wip: noop')).toBeNull();
    expect(repo.currentBranch()).toBe('main');
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd agent-dh && pnpm --filter @pi-investment/lifecycle test
```
预期：FAIL（`./git.js` 不存在）。

- [ ] **Step 3: 实现** `src/git.ts`

```typescript
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
  head(): string { return this.git(['rev-parse', 'HEAD']); }

  hasChanges(paths: string[]): boolean {
    return this.git(['status', '--porcelain', '--', ...paths]).length > 0;
  }

  /** 有改动则建 wip 分支并提交，返回分支名；无改动返回 null（不切分支） */
  createWipBranch(prefix: string, paths: string[], message: string): string | null {
    if (!this.hasChanges(paths)) return null;
    const branch = `${prefix}/${timestamp()}`;
    this.git(['checkout', '-b', branch]);
    this.git(['add', '-A', '--', ...paths]);
    this.git(['commit', '-m', message]);
    return branch;
  }

  checkout(branch: string): void { this.git(['checkout', branch]); }
  mergeFfOnly(branch: string): void { this.git(['merge', '--ff-only', branch]); }
  deleteBranch(branch: string): void { this.git(['branch', '-d', branch]); }
}
```

- [ ] **Step 4: 跑测试确认全绿**

```bash
cd agent-dh && pnpm --filter @pi-investment/lifecycle test
```
预期：git 3 个测试 PASS（state 的 5 个若已合并也应 PASS）。

- [ ] **Step 5: Commit**

```bash
git add agent-dh/packages/lifecycle/src/git.ts agent-dh/packages/lifecycle/src/git.test.ts
git commit -m "feat(agent-dh): lifecycle GitRepo wip 分支封装 + 测试"
```

---

### Task 4: scripts/self-restart.ts 重启器（M，Claude 重点审）

**Files:**
- Create: `agent-dh/scripts/self-restart.ts`

**铁律（违反即打回）：本文件自包含，只允许 import node 内置模块，禁止 import `packages/` 下任何代码。** 它的职责是在插件崩掉时兜底回滚，自身不能依赖可能崩掉的东西。

**运行方式：** `node --import tsx/esm scripts/self-restart.ts <pid> <port> <repoRoot> <stateDir> <startScript> <logPath>`，由插件以 `detached + unref` spawn，agent 进程死后继续执行。

- [ ] **Step 1: 实现** `agent-dh/scripts/self-restart.ts`

```typescript
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
```

- [ ] **Step 2: 语法烟测（不触发真实重启）**

注意：脚本顶层会立即执行 main()，不能直接 import 试跑。只做编译检查：

```bash
cd agent-dh && npx tsc --noEmit --module esnext --moduleResolution bundler --target es2022 --skipLibCheck scripts/self-restart.ts
```
预期：无输出（编译通过）。

- [ ] **Step 3: Commit**

```bash
git add agent-dh/scripts/self-restart.ts
git commit -m "feat(agent-dh): self-restart.ts 独立重启器（健康检查+自动回滚）"
```

---

### Task 5: index.ts 插件主体（H）

**Files:**
- Create: `agent-dh/packages/lifecycle/src/index.ts`

**关键契约（已验证，逐字使用）：**
- 服务注入：`static inject = ['tools', 'agents']`，`ctx.agents.roots()` 返回 `Agent[]`（`vendor/dsh/agent/lib/types/index.d.ts` AgentRegistry）
- 消息投递：`agent.followup(createUserMessage({ content: [{ type: 'text', text }], source: { kind: 'plugin', plugin: 'lifecycle' } }))`——与 DSH 官方 schedule 包 `packages/schedule/schedule/src/runtime.ts:271-275` 同一模式
- `createUserMessage` 来自 `@deepseek-ai/dsh-llm`
- agent 匹配：`String(a.id).startsWith(config.agentId)`（配置 id 是 session id 前缀），兜底取 `roots()[0]`
- 续跑触发：`ctx.on('ready')` 时若 roots 为空，挂一次性 `ctx.on('agent/created')` 监听

- [ ] **Step 1: 实现** `src/index.ts`

```typescript
import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { GitRepo } from './git.js';
import { PendingResume, RestartResult, StateStore } from './state.js';

export interface Config {
  repoRoot: string;
  agentDhRoot: string;
  profileDir: string;
  port?: number;
  agentId?: string;
  maxRestartsPerHour?: number;
}

function renderResumeMessage(pending: PendingResume, result: RestartResult | null): string {
  const head = '【自修复续跑】此消息由 lifecycle 插件自动注入，不是用户消息。';
  if (result?.status === 'rolled_back') {
    const stopHint = pending.attempt >= 2
      ? '这是同一任务的第 2 次失败，已回滚且【不再允许自动重启重试】。请人工介入或仔细修复后再试。'
      : '请用 git diff 复盘失败分支，修复后可再次 self_restart。';
    return `${head}
你上次因「${pending.reason}」的修改导致启动失败，已自动回滚到 ${pending.base_branch}。
失败分支 ${result.failed_branch ?? '(无)'} 已保留，崩溃日志：${result.log_path ?? '(无)'}。
${stopHint}`;
  }
  if (result?.status === 'dead') {
    return `${head}
上次修改导致启动失败，且回滚后也未能启动（status=dead）。服务可能处于人工恢复状态。
失败分支 ${result.failed_branch ?? '(无)'}，日志：${result.log_path ?? '(无)'}。请只做诊断，不要 self_restart。`;
  }
  return `${head}
重启成功。你之前因「${pending.reason}」重启，检查点分支：${pending.checkpoint_branch ?? '(无代码改动)'}。
请继续执行验证任务：${pending.resume_task || '(无，纯维护重启，无需续跑)'}
验证通过后调用 self_finalize(action=merge) 合并回 ${pending.base_branch}；
验证失败则修复后再次 self_restart，或 self_finalize(action=rollback) 放弃修改。`;
}

export default class LifecyclePlugin extends Service {
  static inject = ['tools', 'agents'];
  static Config = z.object({
    repoRoot: z.string(),
    agentDhRoot: z.string(),
    profileDir: z.string(),
    port: z.number().default(13080),
    agentId: z.string().default('investor'),
    maxRestartsPerHour: z.number().default(3),
  })

  private repo: GitRepo;
  private state: StateStore;
  private cfg: Required<Config>;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'lifecycle');
    this.cfg = {
      port: 13080, agentId: 'investor', maxRestartsPerHour: 3, ...config,
    } as Required<Config>;
    this.repo = new GitRepo(this.cfg.repoRoot);
    this.state = new StateStore(join(this.cfg.profileDir, 'state'));
    this.registerTools();
    this.setupResume();
  }

  /** 新进程 ready 后检测 pending-resume.json，向 investor agent 注入续跑消息 */
  private setupResume(): void {
    this.ctx.on('ready', () => {
      const pending = this.state.readPending();
      if (!pending) return;
      const result = this.state.readRestartResult();
      const text = renderResumeMessage(pending, result);
      const deliver = (): boolean => {
        const roots: Agent[] = this.ctx.agents.roots();
        const agent = roots.find((a) => String(a.id).startsWith(this.cfg.agentId)) ?? roots[0];
        if (!agent) return false;
        agent.followup(createUserMessage({
          content: [{ type: 'text', text }],
          source: { kind: 'plugin', plugin: 'lifecycle' },
        }));
        this.state.markPendingDone();
        this.ctx.logger.info(`lifecycle: resume message delivered (${result?.status ?? 'ok'})`);
        return true;
      };
      if (!deliver()) {
        const dispose = this.ctx.on('agent/created', () => { if (deliver()) dispose(); });
        setTimeout(() => dispose(), 60_000);
      }
    });
  }

  private json(value: unknown) {
    return [{ type: 'text' as const, text: JSON.stringify(value, null, 2) }];
  }

  private registerTools(): void {
    const { ctx } = this;

    ctx.tools.register(defineTool({
      name: 'self_restart',
      description: '重启 agent 自身（自修复）。用途：①修改插件代码后重启生效并自动续跑验证；②状态异常时冷启动恢复；③定期维护。重启前自动把未提交改动存入 wip 分支检查点；若新代码导致启动失败会自动回滚，不会变砖。重启后自动收到续跑消息。每小时最多 3 次。',
      parameters: {
        reason: { type: 'string', description: '重启原因，如「修复 strategy 插件筛选 bug」', required: true },
        resume_task: { type: 'string', description: '重启后要自动执行的验证任务描述；纯维护重启传空字符串', required: true },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean' },
            message: { type: 'string' },
            checkpoint_branch: { type: 'string' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        if (!this.state.acquireLock()) {
          return { success: false, message: '已有重启进行中（restarting.lock 存在），拒绝重入' } as any;
        }
        try {
          const now = Date.now();
          const rate = this.state.checkRateLimit(this.cfg.maxRestartsPerHour, now);
          if (!rate.allowed) {
            return { success: false, message: `本小时已重启 ${rate.count} 次，达到上限 ${this.cfg.maxRestartsPerHour}，拒绝执行` } as any;
          }
          const base = this.repo.currentBranch();
          const branch = this.repo.createWipBranch('agent-self', ['agent-dh/'], `wip(agent-self): ${args.reason}`);
          const attempt = this.state.nextAttempt(args.resume_task);
          this.state.writePending({
            reason: args.reason,
            resume_task: args.resume_task,
            checkpoint_branch: branch,
            base_branch: base,
            last_known_good: this.state.readLastKnownGood() ?? this.repo.head(),
            attempt,
            ts: new Date(now).toISOString(),
          });
          this.state.bumpCounter(now);
          const logPath = join(this.cfg.profileDir, 'state', `restart-${Date.now()}.log`);
          const child = spawn('node', [
            '--import', 'tsx/esm',
            join(this.cfg.agentDhRoot, 'scripts/self-restart.ts'),
            String(process.pid), String(this.cfg.port),
            this.cfg.repoRoot, join(this.cfg.profileDir, 'state'),
            join(this.cfg.profileDir, 'start.sh'), logPath,
          ], { detached: true, stdio: 'ignore', cwd: this.cfg.agentDhRoot });
          child.unref();
          return {
            success: true,
            checkpoint_branch: branch,
            attempt,
            message: `重启已安排，5 秒后执行，当前会话将被终止。检查点：${branch ?? '无代码改动'}。日志：${logPath}`,
          } as any;
        } catch (e) {
          this.state.releaseLock();
          return { success: false, message: `self_restart 失败：${String(e)}` } as any;
        }
      },
    } as any));

    ctx.tools.register(defineTool({
      name: 'self_finalize',
      description: '自修复验证完成后的收尾。merge：把 wip 检查点分支合并回基线分支（验证通过时调用）；rollback：切回基线分支放弃修改（验证失败且不可修复时调用）。',
      parameters: {
        action: { type: 'string', enum: ['merge', 'rollback'], description: 'merge=验证通过合并回基线；rollback=放弃修改切回基线', required: true },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean' },
            action: { type: 'string' },
            message: { type: 'string' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        const done = this.state.readPendingDone();
        if (!done?.checkpoint_branch) {
          return { success: false, action: args.action, message: '没有待收尾的 wip 检查点（pending-resume.done.json 不存在或无分支）' } as any;
        }
        try {
          this.repo.checkout(done.base_branch);
          if (args.action === 'merge') {
            this.repo.mergeFfOnly(done.checkpoint_branch);
            this.repo.deleteBranch(done.checkpoint_branch);
            this.state.writeLastKnownGood(this.repo.head());
            this.state.clearAttempt();
            return { success: true, action: 'merge', message: `已合并 ${done.checkpoint_branch} 到 ${done.base_branch}，last_known_good 已更新` } as any;
          }
          return { success: true, action: 'rollback', message: `已切回 ${done.base_branch}，修改保留在分支 ${done.checkpoint_branch} 供复盘` } as any;
        } catch (e) {
          return { success: false, action: args.action, message: `self_finalize 失败：${String(e)}` } as any;
        }
      },
    } as any));

    ctx.tools.register(defineTool({
      name: 'self_status',
      description: '查看自身生命周期状态：当前 git 分支/HEAD、待续跑任务、上次重启结果、本小时重启次数、last_known_good。用于自修复决策前的自检。',
      parameters: {},
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 10000,
      execute: async () => {
        const now = Date.now();
        return {
          branch: this.repo.currentBranch(),
          head: this.repo.head(),
          has_uncommitted_changes: this.repo.hasChanges(['agent-dh/']),
          pending: this.state.readPending(),
          pending_done: this.state.readPendingDone(),
          last_restart_result: this.state.readRestartResult(),
          restarts_this_hour: this.state.checkRateLimit(this.cfg.maxRestartsPerHour, now).count,
          max_restarts_per_hour: this.cfg.maxRestartsPerHour,
          last_known_good: this.state.readLastKnownGood(),
        } as any;
      },
    } as any));
  }
}
```

- [ ] **Step 2: 编译检查**

```bash
cd agent-dh && npx tsc --noEmit -p tsconfig.json 2>&1 | grep lifecycle
```
预期：lifecycle 相关无错误输出（仓库基线其他错误不算回归，见 CLAUDE.md 既有失败清单惯例）。

- [ ] **Step 3: 单测全绿确认**

```bash
cd agent-dh && pnpm --filter @pi-investment/lifecycle test
```
预期：state 5 个 + git 3 个全 PASS（index.ts 无单测，E2E 覆盖）。

- [ ] **Step 4: Commit**

```bash
git add agent-dh/packages/lifecycle/src/index.ts
git commit -m "feat(agent-dh): lifecycle 插件 self_restart/self_finalize/self_status + ready 续跑注入"
```

---

### Task 6: DSH profile 注册（L）

**Files（仓库外，直接改线上 profile）：**
- Modify: `~/.dsh/profiles/investment/package.json`（dependencies 加一行）
- Modify: `~/.dsh/profiles/investment/cordis.patch.yml`（投资插件段加一条 insert）

- [ ] **Step 1: package.json dependencies 增加**

```json
"@pi-investment/lifecycle": "file:../../../pi-investment/agent-dh/packages/lifecycle"
```
（与其他 14 个插件的 file: 写法一致；若实际相对路径不同，以现有行为准照抄格式。）

- [ ] **Step 2: cordis.patch.yml 在投资插件段追加**

```yaml
    - id: lifecycle
      name: '@pi-investment/lifecycle'
      config:
        repoRoot: /Users/yunpeng/pi-investment
        agentDhRoot: /Users/yunpeng/pi-investment/agent-dh
        profileDir: /Users/yunpeng/.dsh/profiles/investment
        port: 13080
        agentId: investor
        maxRestartsPerHour: 3
```

- [ ] **Step 3: 安装并验证加载**

```bash
cd ~/.dsh/profiles/investment && pnpm install
```
预期：无报错。

- [ ] **Step 4: Commit（仓库内无文件改动，跳过；在 E2E 通过后将 profile 变更说明记入 Task 8 文档）**

---

### Task 7: E2E 验收（H，Claude 亲做）

**前置：** quantsys-v2 :5001 在跑；DSH profile 未运行（验收全程由此任务控制）。

- [ ] **Step 1: 冷启动烟测**

```bash
cd ~/.dsh/profiles/investment && nohup ./start.sh 13080 > /tmp/dh-e2e.log 2>&1 &
sleep 20 && curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:13080/
```
预期：端口通（000 以外）。日志中无 lifecycle 插件加载报错。

- [ ] **Step 2: 工具可见性**

通过 Web UI（http://localhost:13080）向 investor agent 发：「调用 self_status 并原样返回结果」。
预期：返回 JSON 含 `branch`、`head`、`restarts_this_hour` 字段。

- [ ] **Step 3: 正常路径**

让 agent：修改某插件的一处 description 文案 → 调 `self_restart(reason="E2E正常路径", resume_task="调用 self_status 确认自己在 wip 分支上")`。
人工观察：
- 5 秒后 :13080 断开再恢复（`state/restart-*.log` 有 `health check ok`）
- 新会话自动收到【自修复续跑】消息并执行 self_status
- agent 调 `self_finalize(merge)` 后 `git branch --list 'agent-self/*'` 为空，main 多了一个 `wip(agent-self)` 提交

- [ ] **Step 4: 崩溃路径（核心安全验证）**

手工在 `packages/investment/src/index.ts` 第一行插入 `this is not valid typescript!!!`（不提交），然后通过 Web UI 让 agent 调 `self_restart(reason="E2E崩溃路径", resume_task="无")`。
预期：
- 新进程起不来，120 秒后 `state/restart-result.json` 为 `{"status":"rolled_back", ...}`
- `git branch --show-current` 已回到 main，工作区的语法错误已消失（回滚生效）
- agent 复活并收到 rolled_back 续跑消息，消息含失败分支名和日志路径
- `git branch --list 'agent-self/*'` 能看到失败分支（未删除）

- [ ] **Step 5: 限流验证**

让 agent 连续调 4 次 self_restart（前 3 次之间人工 kill 重启器进程防真重启，或等每次重启完成）。第 4 次预期返回 `success: false` 且消息含「达到上限」。
验证后清理：`rm ~/.dsh/profiles/investment/state/restart-counter.json`。

- [ ] **Step 6: 现场清理**

E2E 产生的 wip 提交若不保留：`git reset --hard <E2E前main HEAD>`（确认无其他改动混入后）。清空 `~/.dsh/profiles/investment/state/` 下的测试残留。

---

### Task 8: 文档更新（L）

**Files:**
- Modify: `agent-dh/CLAUDE.md`

- [ ] **Step 1: 插件表增加一行**

在「### Infrastructure Packages」表后追加（或并入 Core 表）：

```markdown
| `@pi-investment/lifecycle` | 3 | 自修复重启：self_restart/self_finalize/self_status，git wip 分支安全网，启动失败自动回滚，ready 后自动续跑 |
```

并新增小节：

```markdown
### 自修复重启（lifecycle 插件）

- agent 可通过 `self_restart(reason, resume_task)` 重启自身：改动自动存入 `agent-self/*` wip 分支，重启器（`scripts/self-restart.ts`，detached 独立进程）负责 kill→拉起→健康检查→失败自动回滚
- 验证通过后 `self_finalize(merge)` 合回基线分支；失败可 rollback
- 状态文件在 `~/.dsh/profiles/investment/state/`；限流每小时 3 次
- 详见 docs/rfcs/002-agent-dh-self-restart.md
```

- [ ] **Step 2: Commit**

```bash
git add agent-dh/CLAUDE.md
git commit -m "docs(agent-dh): lifecycle 插件与自修复重启说明"
```

---

## Self-Review 记录

- **Spec 覆盖**：RFC 002 的三工具 ✓(Task5)、重启器 ✓(Task4)、git 闭环 ✓(Task3/5)、续跑注入 ✓(Task5)、护栏（限流/锁/attempt/main 保护/现场保留）✓(Task2/4/5)、状态文件 ✓(Task2)、profile 注册 ✓(Task6)、E2E（正常+崩溃+限流）✓(Task7)、文档 ✓(Task8)
- **类型一致性**：`PendingResume`/`RestartResult` 字段在 Task2 定义，Task4/5 使用一致；`createWipBranch(prefix, paths, message)` 签名 Task3 定义 Task5 调用一致；`checkRateLimit(max, now)`/`bumpCounter(now)`/`nextAttempt(task)` 一致
- **已知取舍**：index.ts 不写单测（cordis 运行时依赖重，E2E 覆盖）；`pending.attempt >= 2` 时仅改提示词不硬阻断（agent 仍可选择修复后再重启，硬阻断在「dead」状态）
