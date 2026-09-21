/**
 * restart-planner：self_restart 编排的纯函数模块（2026-09，REQ-370b24 可测化重构）。
 *
 * 动机：scheduleRestart 原是 LifecyclePlugin 私有方法，依赖 Cordis 容器无法直接单测；
 * finalize 测试只能"复刻逻辑"，容易与真实实现漂移。本模块把同段逻辑抽为
 * 依赖注入的纯函数：repo/state 全部传入（测试用真实临时 git 仓库 + StateStore），
 * spawn 注入（测试只记录不真起进程），base 溯源策略注入（index 传 resolveTrunkBase，
 * 测试传恒等干线）。
 *
 * 约束：不 import cordis / dsh-* / 任何运行时服务；保持与原 scheduleRestart 行为逐行一致
 * （本阶段=重构等价迁移，行为不变；新不变量如"HEAD 交还 main"由后续改动在 restarter 侧落地）。
 */
import type { PendingResume } from './state.js';

/** GitRepo 最小面（结构类型，测试/生产可传真实 GitRepo） */
export interface PlannerGit {
  currentBranch(): string;
  commitOnCurrent(paths: string[], message: string): string | null;
  createWipBranch(prefix: string, paths: string[], message: string): { branch: string; files: string[] } | null;
  head(): string;
}

/** StateStore 最小面 */
export interface PlannerState {
  checkRateLimit(maxPerHour: number, now: number): { allowed: boolean; count: number };
  acquireLock(staleMs?: number): boolean;
  releaseLock(): void;
  nextAttempt(task: string): number;
  writePending(p: PendingResume): void;
  readPending(): PendingResume | null;
  readLastKnownGood(): string | null;
  bumpCounter(now: number): void;
}

export interface RestartPlannerDeps {
  repo: PlannerGit;
  state: PlannerState;
  /** 已停在 agent-self/* 时的干线溯源（index 传 this.resolveTrunkBase；测试传恒等 main） */
  resolveBase: (curBranch: string) => string;
  resolveRestarterPath: () => string;
  profileDir: string;
  /**
   * 自我重启拉起的启动脚本绝对路径（2026-09-12，w-f9c9a5c1）。
   * 缺省 = `${profileDir}/start.sh`（历史行为，等价迁移不变量）。
   * 显式配置后，自我重启拉起的是 profile 之外的启动器（如 agent-dh 仓库内的
   * `agent-dh/scripts/start.sh`），让「开机自启（launchd）」与「自我重启」指向
   * 同一入口，消除两份 start.sh 相互漂移（历史上 launchd 与自我重启曾各拉一份）。
   */
  startScript?: string;
  agentDhRoot: string;
  repoRoot: string;
  port: number;
  processPid: number;
  captureLastUserMessage: (originAgentId: string | null | undefined) => string | null;
  spawnRestarter: (cmd: string, args: string[], opts: { detached: boolean; stdio: 'ignore'; cwd: string }) => void;
}

export interface RestartPlan {
  checkpointBranch: string | null;
  baseBranch: string;
  attempt: number;
  logPath: string;
  restarter: string;
  reason: string;
}

export interface RestartRequest {
  reason: string;
  preserveContext: boolean;
  originAgentId?: string | null;
  maxRestartsPerHour: number;
  /** 注入时钟（限流判定），测试可固定 */
  now: number;
}

/**
 * ① 限流 → ② 互斥锁 → ③ wip 检查点（main 上新建 agent-self/*；已在 wip 上则续提交同分支）
 * → ④ pending 落盘 → ⑤ spawn 重启器（detached+unref）。
 * 锁生命周期：spawn 成功前失败由本模块释放（catch）；spawn 后锁归重启器（finish 释放）。
 */
export function planAndScheduleRestart(deps: RestartPlannerDeps, req: RestartRequest): RestartPlan {
  const { repo, state, resolveBase, resolveRestarterPath, profileDir, agentDhRoot, repoRoot, port, processPid, captureLastUserMessage, spawnRestarter } = deps;
  const { reason, preserveContext, originAgentId, maxRestartsPerHour, now } = req;
  // 启动脚本：显式配置优先，缺省沿用 profileDir/start.sh（历史行为不变）
  const startScript = deps.startScript && deps.startScript.length > 0
    ? deps.startScript
    : joinPath(profileDir, 'start.sh');

  // ① 限流（必须先于拿锁：拒绝路径不持有锁，否则锁永远无人释放——50cb6084 Critical 修复）
  const rate = state.checkRateLimit(maxRestartsPerHour, now);
  if (!rate.allowed) {
    throw new Error(`本小时已重启 ${rate.count} 次，达到上限 ${maxRestartsPerHour}，拒绝执行`);
  }
  // ② 互斥锁：防并发重启（锁由重启器在流程终结时释放，本进程只负责创建）
  if (!state.acquireLock()) {
    throw new Error('已有重启进行中（restarting.lock 存在），拒绝重入');
  }
  try {
    // ③ 未提交代码 → wip 检查点（git 安全网，启动失败可回滚）
    // base 溯源 + 续提交（改动1，2026-09-06, w-856b64ef）：
    //   旧逻辑 base=currentBranch()：wip-on-wip 会把旧 wip 记为 base → 链根是 wip，永远合不进 main。
    //   新逻辑：当停在 agent-self/* 上时，base 溯源到链根干线；未提交改动续提交到同一 wip。
    const curBranch = repo.currentBranch();
    const onWip = curBranch.startsWith('agent-self/');
    const base = onWip ? resolveBase(curBranch) : curBranch;
    let wip: { branch: string } | null = null;
    if (onWip) {
      repo.commitOnCurrent(['agent-dh/'], `wip(agent-self): ${reason}（续 @ ${curBranch}）`);
      wip = { branch: curBranch };
    } else {
      wip = repo.createWipBranch('agent-self', ['agent-dh/'], `wip(agent-self): ${reason}`);
    }
    const branch = wip?.branch ?? null;
    // ④ 持久化 pending（重启后 setupResume 据此回投续跑消息；含上次消息内容便于接续）
    const attempt = state.nextAttempt(preserveContext ? 'continue previous task' : 'maintenance');
    state.writePending({
      reason,
      resume_task: preserveContext ? 'continue previous task' : 'maintenance',
      checkpoint_branch: branch,
      base_branch: base,
      last_known_good: state.readLastKnownGood() ?? repo.head(),
      attempt,
      ts: new Date(now).toISOString(),
      origin_agent_id: originAgentId ?? null,
      last_user_message: captureLastUserMessage(originAgentId),
    });
    state.bumpCounter(now);
    // ⑤ spawn 包内重启器（detached + unref；重启器自行 kill 本进程，本进程无需 exit）
    const logPath = joinPath(profileDir, 'state', `restart-${now}.log`);
    const restarter = resolveRestarterPath();
    const tsxFlag = restarter.endsWith('.ts') ? ['--import', 'tsx/esm'] : [];
    spawnRestarter(processExecPath(), [
      ...tsxFlag, restarter,
      String(processPid), String(port),
      repoRoot, joinPath(profileDir, 'state'),
      startScript, logPath,
    ], { detached: true, stdio: 'ignore', cwd: agentDhRoot });
    return { checkpointBranch: branch, baseBranch: base, attempt, logPath, restarter, reason };
  } catch (e) {
    // 只有 spawn 成功前失败才由本进程释放锁；spawn 后锁归重启器管
    state.releaseLock();
    throw e;
  }
}

/* ---- 纯函数（不 import node:path / node:child_process，便于浏览器/测试宿主兼容） ---- */

export function joinPath(...parts: string[]): string {
  return parts.join('/').replace(/\/+/g, '/');
}

export function processExecPath(): string {
  return process.execPath;
}
