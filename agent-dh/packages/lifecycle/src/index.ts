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

  /** 启动时检测 pending-resume.json，向 investor agent 注入续跑消息 */
  private setupResume(): void {
    const pending = this.state.readPending();
    if (!pending) return;
    const result = this.state.readRestartResult();
    const text = renderResumeMessage(pending, result);
    const deliver = (agent: Agent | undefined): boolean => {
      if (!agent) return false;
      try {
        agent.followup(createUserMessage({
          content: [{ type: 'text', text }],
          source: { kind: 'plugin', plugin: 'lifecycle' },
        }));
      } catch (e) {
        // 投递失败不标记 done：pending 保留，等 agent/created 兜底或下次启动重投
        this.ctx.logger.warn(`lifecycle: resume followup failed: ${String(e)}`);
        return false;
      }
      this.state.markPendingDone();
      this.ctx.logger.info(`lifecycle: resume message delivered (${result?.status ?? 'ok'})`);
      return true;
    };
    // 立即尝试（本插件晚于 agent 创建加载时，roots 里已有目标）
    const roots: Agent[] = this.ctx.agents.roots();
    if (deliver(roots.find((a) => String(a.id).startsWith(this.cfg.agentId)) ?? roots[0])) return;
    // 否则等 agent 创建事件（插件先于 agent-loop 完成配置化启动时）
    const dispose = this.ctx.on('agent/created', ({ agent }) => {
      if (String(agent.id).startsWith(this.cfg.agentId) && deliver(agent)) dispose();
    });
    setTimeout(() => dispose(), 60_000);
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
        // 限流检查必须在 acquireLock 之前：拒绝路径不会 spawn 重启器，
        // 而锁只由重启器清除，先拿锁再拒绝会永久泄漏锁文件（self_restart 变砖）
        const now = Date.now();
        const rate = this.state.checkRateLimit(this.cfg.maxRestartsPerHour, now);
        if (!rate.allowed) {
          return { success: false, message: `本小时已重启 ${rate.count} 次，达到上限 ${this.cfg.maxRestartsPerHour}，拒绝执行` } as any;
        }
        if (!this.state.acquireLock()) {
          return { success: false, message: '已有重启进行中（restarting.lock 存在），拒绝重入' } as any;
        }
        try {
          const base = this.repo.currentBranch();
          const baseHead = this.repo.head(); // 必须先于 createWipBranch 捕获，否则拿到的是 wip 提交
          const wip = this.repo.createWipBranch('agent-self', ['agent-dh/'], `wip(agent-self): ${args.reason}`);
          const branch = wip?.branch ?? null;
          const attempt = this.state.nextAttempt(args.resume_task);
          this.state.writePending({
            reason: args.reason,
            resume_task: args.resume_task,
            checkpoint_branch: branch,
            base_branch: base,
            last_known_good: this.state.readLastKnownGood() ?? baseHead,
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
            checkpoint_files: wip?.files ?? [],
            attempt,
            message: `重启已安排，数秒后执行，当前会话将被终止。检查点：${branch ?? '无代码改动'}${wip ? `（含 ${wip.files.length} 个文件，如有不属于本次修复的改动请留意：${wip.files.join(', ')}）` : ''}。日志：${logPath}`,
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
            this.state.clearPendingDone(); // 收尾完成即清档，保证 self_finalize 幂等
            return { success: true, action: 'merge', message: `已合并 ${done.checkpoint_branch} 到 ${done.base_branch}，last_known_good 已更新` } as any;
          }
          this.state.clearPendingDone();
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
