import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { readFileSync, appendFileSync, writeFileSync, existsSync } from 'node:fs';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { assembleContextFor } from '@deepseek-ai/dsh-agent';
import { renderPrompt } from '@deepseek-ai/dsh-system-prompt';
import { AgentOSClient } from '@pi-investment/agent-os-client';
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
  static inject = ['tools', 'agents', 'systemPrompt'];
  static Config = z.object({
    repoRoot: z.string(),
    agentDhRoot: z.string(),
    profileDir: z.string(),
    port: z.number().default(13080),
    agentId: z.string().default('investor'),
    maxRestartsPerHour: z.number().default(10),
    agentOS: z.object({
      baseURL: z.string().default('http://localhost:8080'),  // 窗口注册表落 Agent OS（核心层）
    }).default({} as any),
  })

  private repo: GitRepo;
  private state: StateStore;
  private cfg: Required<Config> & { agentOS?: { baseURL: string } };
  private identity: { id: string; name: string; role: string; instance: string; port: number };
  private aos: any;  // AgentOSClient（窗口注册表落 OS 记忆库）

  constructor(ctx: Context, config: Config) {
    super(ctx, 'lifecycle');
    this.cfg = {
      port: 13080, agentId: 'investor', maxRestartsPerHour: 10, ...config,
    } as Required<Config>;
    this.repo = new GitRepo(this.cfg.repoRoot);
    this.state = new StateStore(join(this.cfg.profileDir, 'state'));
    this.identity = this.loadIdentity();
    this.registerIdentitySection();
    // 窗口注册表（2026-08-21 用户需求：窗口随机打开，但要能按编码调动；落 Agent OS）
    this.aos = new AgentOSClient({
      baseURL: (config as any).agentOS?.baseURL || 'http://localhost:8080',
      agentId: this.cfg.agentId,
    });
    this.setupWindowRegistry();
    this.registerTools();
    this.setupResume();
    this.setupOsReminderPoller();  // OS 提醒体系：60s 轮询信箱并投递（2026-08-25，dsh-schedule 会话级提醒 fork 即死的替代）
  }

  // ===== OS 提醒体系（2026-08-25 用户决策：提醒走 OS，不走 dsh session-local）=====
  // 权威注册表 = Agent OS scheduler（postgres 持久，重启/fork 不死）
  // 触发链路：OS cron 任务 → os-remind-bridge.sh → OS 记忆库信箱 → 本轮询 → followup 投递
  private reminderPollTimer: ReturnType<typeof setInterval> | null = null;

  private setupOsReminderPoller(): void {
    const poll = async () => {
      try {
        const myWindow = this.windowCode(this.identity.id);
        const res: any = await this.aos.memory.search({ query: 'reminder', tag: `office:reminder:${myWindow}`, top_k: 50 });
        const items: any[] = res?.memories || res?.items || [];
        for (const it of items) {
          let p: any = null;
          try { p = typeof it.content === 'string' ? JSON.parse(it.content) : it.content; } catch { continue; }
          if (!p || p.delivered) continue;
          // 投递到当前 investor 会话（roots 兜底与 setupResume 同款）
          const roots: any[] = this.ctx.agents.roots();
          const agent = roots.find((a) => String(a.id).startsWith(this.cfg.agentId)) ?? roots[0];
          if (!agent?.followup) continue;  // 不在线，留在信箱等上线补投
          try {
            agent.followup(createUserMessage({
              content: [{ type: 'text', text: `【OS 提醒】${p.task ?? ''}\n\n${p.prompt}\n\n（来源：Agent OS 定时任务 ${p.task_id ?? ''}，触发于 ${p.fired_at ?? ''}）` }],
              source: { kind: 'plugin', plugin: 'lifecycle' },
            }));
            await this.osWrite('memory_write', {
              title: `reminder ${p.task ?? ''} delivered`,
              content: JSON.stringify({ ...p, delivered: true, delivered_at: new Date().toISOString() }),
              namespace: 'data',
              tags: ['office:delivered', `office:reminder:${myWindow}`],
            });
          } catch { /* 投递失败留下次 */ }
        }
      } catch { /* OS 宕机等异常静默，下轮重试 */ }
    };
    this.reminderPollTimer = setInterval(poll, 60_000);
    poll().catch(() => {});  // 启动即查一轮
    this.ctx.on('dispose' as any, () => {
      if (this.reminderPollTimer) { clearInterval(this.reminderPollTimer); this.reminderPollTimer = null; }
    });
  }

  /** 窗口编码：session-<uuid> → w-<前8位>；其他 agent id 原样返回 */
  private windowCode(agentId: string): string {
    return agentId.startsWith('session-') ? `w-${agentId.slice(8, 16)}` : agentId;
  }

  /**
   * 窗口注册表：监听 agent/created（新窗口=新会话 agent），自动登记。
   * 双轨：OS Skills API（结构化档案，category=window）+ OS 记忆库（事件流水）。
   * 所有 OS 写走 osWrite（outbox 防丢）。
   */
  private setupWindowRegistry(): void {
    this.ctx.on('agent/created' as any, (agent: any) => {
      this.registerWindow(agent).catch(() => { /* 注册失败不影响 agent 创建 */ });
    });
    // 启动时重放 outbox（OS 宕机期间的积压登记）
    this.replayOutbox().catch(() => {});
  }

  // ===== 办公室持久化：outbox 防丢（2026-08-21 用户要求"别丢信息"）=====

  private get outboxPath(): string {
    return join(this.cfg.profileDir, 'state', 'os-outbox.jsonl');
  }

  /** 声明式 OS 操作执行器（outbox 可重放的前提：操作可序列化） */
  private async osExec(op: string, payload: any): Promise<any> {
    if (op === 'memory_write') return this.aos.memory.write(payload);
    if (op === 'skill_upsert') return this.skillUpsert(payload);
    throw new Error(`unknown os op: ${op}`);
  }

  /**
   * OS 写操作统一入口：成功则顺带重放积压；失败则追加 outbox（jsonl），
   * 下次成功写或下次启动时重放——OS 宕机期间的信息不丢。
   */
  private async osWrite(op: string, payload: any): Promise<{ queued: boolean }> {
    try {
      await this.osExec(op, payload);
      await this.replayOutbox();
      return { queued: false };
    } catch (e: any) {
      appendFileSync(this.outboxPath, JSON.stringify({ ts: new Date().toISOString(), op, payload }) + '\n');
      this.ctx.logger.warn(`lifecycle: OS write failed (${op}), queued to outbox: ${e?.message}`);
      return { queued: true };
    }
  }

  private async replayOutbox(): Promise<void> {
    if (!existsSync(this.outboxPath)) return;
    const lines = readFileSync(this.outboxPath, 'utf-8').split('\n').filter(Boolean);
    if (lines.length === 0) return;
    const remaining: string[] = [];
    for (const line of lines) {
      try {
        const e = JSON.parse(line);
        await this.osExec(e.op, e.payload);
      } catch {
        remaining.push(line);  // 仍失败则保留，下轮再试
      }
    }
    writeFileSync(this.outboxPath, remaining.length ? remaining.join('\n') + '\n' : '');
  }

  /** OS Skills API upsert（窗口结构化档案：name=window:<code>，metadata 带技能/忙闲/任务） */
  private async skillUpsert(p: {
    window: string; session_id: string; agent_id: string; role: string;
    skills?: string[]; status?: string; task?: string | null; note?: string | null;
  }): Promise<void> {
    const base = (this.cfg as any).agentOS?.baseURL || 'http://localhost:8080';
    const listRes = await fetch(`${base}/api/v1/skills`);
    if (!listRes.ok) throw new Error(`skills list failed: ${listRes.status}`);
    const listData: any = await listRes.json();
    const skills: any[] = listData?.skills ?? listData ?? [];
    const existing = skills.find((s: any) => s.name === `window:${p.window}`);

    // OS Skills API 要求 content 必填（2026-08-21 E2E 实测："name, owner, and content are required"）
    const desc = `窗口 ${p.window}（${p.role}）${p.task ? `当前任务：${p.task}` : '空闲'}`;
    const body = {
      name: `window:${p.window}`,
      description: desc,
      category: 'window',
      owner: p.agent_id,
      status: 'active',
      content: desc,
      metadata: {
        window: p.window,
        session_id: p.session_id,
        agent_id: p.agent_id,
        skills: p.skills ?? [],
        availability: p.status ?? 'idle',
        task: p.task ?? null,
        note: p.note ?? null,
        updated_at: new Date().toISOString(),
      },
    };
    const res = await fetch(existing ? `${base}/api/v1/skills/${existing.id}` : `${base}/api/v1/skills`, {
      method: existing ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`skill upsert failed: ${res.status}`);
  }

  private async registerWindow(agent: any): Promise<void> {
    const sessionId = String(agent?.id ?? '');
    if (!sessionId) return;
    const window = this.windowCode(sessionId);
    const profile = {
      window,
      session_id: sessionId,
      agent_id: this.identity.id,
      role: this.identity.name,
      skills: [] as string[],
      task: null,
      status: 'idle',
      started_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    // 双轨：记忆库事件流水 + Skills API 结构化档案（都走 outbox 防丢）
    await this.osWrite('memory_write', {
      title: `window ${window} 上线`,
      content: JSON.stringify(profile),
      namespace: 'data',
      tags: ['system:windows', 'window', window],
    });
    await this.osWrite('skill_upsert', profile);

    // 上线补投离线信箱（办公室交流层）：该窗口离线期间的消息逐条投递
    this.deliverOfflineInbox(agent, window).catch(() => {});
  }

  /** 上线补投：读 office:inbox:<window> 中未投递的消息，followup 给对方 */
  private async deliverOfflineInbox(agent: any, window: string): Promise<void> {
    try {
      const res: any = await this.aos.memory.search({ query: 'inbox', tag: `office:inbox:${window}`, top_k: 50 });
      const items: any[] = res?.memories || res?.items || [];
      for (const it of items) {
        let p: any = null;
        try { p = typeof it.content === 'string' ? JSON.parse(it.content) : it.content; } catch { continue; }
        if (!p || p.delivered) continue;
        agent.followup(createUserMessage({
          content: [{ type: 'text', text: `【离线消息】你在离线期间收到来自窗口 ${p.from} 的消息（${p.ts}）：\n\n${p.message}\n\n回信方式：window_message(window='${p.from}', message='...')` }],
          source: { kind: 'plugin', plugin: 'lifecycle' },
        }));
        // 标记已投递（append-only：写一条 delivered 标记记录）
        await this.osWrite('memory_write', {
          title: `inbox ${window} delivered`,
          content: JSON.stringify({ ...p, delivered: true, delivered_at: new Date().toISOString() }),
          namespace: 'data',
          tags: ['office:delivered', `office:inbox:${window}`],
        });
      }
    } catch { /* 补投失败不影响上线 */ }
  }

  /**
   * Agent 身份注册表（2026-08-21）：每个 agent 有唯一 id 和名字，提高自我认知。
   * 读 profileDir/agents.json；当前 agent 按 cfg.agentId 匹配，alias_of 归并到主身份。
   */
  private loadIdentity(): { id: string; name: string; role: string; instance: string; port: number } {
    const fallback = { id: this.cfg.agentId, name: this.cfg.agentId, role: '未注册角色', instance: 'unknown', port: this.cfg.port };
    try {
      const registry = JSON.parse(readFileSync(join(this.cfg.profileDir, 'agents.json'), 'utf-8'));
      const agents: any[] = registry.agents || [];
      let me = agents.find(a => a.id === this.cfg.agentId) || agents.find(a => a.primary) || agents[0];
      if (!me) return fallback;
      if (me.alias_of) {
        const primary = agents.find(a => a.id === me.alias_of);
        if (primary) me = { ...primary, id: me.id, name: `${primary.name}（${me.name}）`, role: `${primary.role}；本分身：${me.role}` };
      }
      return {
        id: me.id,
        name: me.name,
        role: me.role,
        instance: registry.instance?.name ?? registry.instance?.id ?? 'unknown',
        port: registry.instance?.port ?? this.cfg.port,
      };
    } catch {
      return fallback;
    }
  }

  /**
   * 把身份注入系统提示词（order 5，在宪法段 order 10 之前；身份不可进化、不随基因组变化）
   * 2026-08-21 用户修正：身份是双层的——角色身份（每个窗口相同）+ 窗口唯一编码（每个窗口不同）。
   * 窗口编码通过 {{window_id}} 变量按组装作用域解析（provider 收到 AssembleContext.agent），
   * 永不允许返回 undefined（否则 renderPrompt 抛异常，全站请求失败——A-3 教训）。
   */
  private registerIdentitySection(): void {
    const i = this.identity;

    // 窗口唯一编码：session-<uuid> → w-<前8位>；定时任务/续跑的 investor agent → "investor"；无作用域 → "global"
    (this.ctx as any).systemPrompt?.variable('window_id', (context: any) => {
      try {
        const raw = context?.agent?.id ?? context?.scope ?? 'global';
        const s = String(raw);
        if (s.startsWith('session-')) return `w-${s.slice(8, 16)}`;
        return s || 'global';
      } catch {
        return 'unknown';
      }
    });

    (this.ctx as any).systemPrompt?.section({
      name: 'agent:identity',
      order: 5,
      text: [
        `[agent:${i.id} | window:{{window_id}}]`,
        ``,
        `# 你是谁`,
        ``,
        `你是「${i.name}」（角色 ID: ${i.id}），${i.role}。`,
        `所属实例：${i.instance}（端口 ${i.port}）。`,
        `**本窗口唯一编码：{{window_id}}**——每个窗口（会话）都是独立个体，同角色不同窗口编码不同。`,
        `你的所有分析、交易决策、经验记录都带角色 ID + 窗口编码双署名；与其他窗口/分身协作或复盘归因时，用窗口编码精确区分"是谁说的"。`,
      ].join('\n'),
    });
  }

  /** 启动时检测 pending-resume.json，向发起重启的会话（或 investor agent）注入续跑消息 */
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
      this.ctx.logger.info(`lifecycle: resume message delivered to ${String(agent.id)} (${result?.status ?? 'ok'})`);
      return true;
    };
    // 兜底目标：investor 根 agent（旧行为），用于自主续跑或 origin 久未出现时的接管
    const pickDefault = (): Agent | undefined => {
      const roots: Agent[] = this.ctx.agents.roots();
      return roots.find((a) => String(a.id).startsWith(this.cfg.agentId)) ?? roots[0];
    };
    const originId = pending.origin_agent_id ?? null;
    if (originId) {
      // ① 优先回投发起会话：origin 已存活则立即投递
      if (deliver(this.ctx.agents.get(originId as any))) return;
      // ② origin 未存活（Web 会话等用户回来才恢复）：等 agent/created 精确匹配 origin，
      //    30 分钟窗口内不投兜底，避免消息再次错投后台会话；超时后才接管
      let timer: ReturnType<typeof setTimeout> | undefined;
      const dispose = this.ctx.on('agent/created', ({ agent }) => {
        if (String(agent.id) === originId && deliver(agent)) {
          clearTimeout(timer);
          dispose();
        }
      });
      timer = setTimeout(() => {
        dispose();
        deliver(pickDefault()); // 用户迟迟未回，兜底接管，pending 不空转
      }, 30 * 60_000);
      return;
    }
    // ③ 无 origin（旧 pending 文件）：立即投兜底，否则等 agent/created
    if (deliver(pickDefault())) return;
    const dispose = this.ctx.on('agent/created', ({ agent }) => {
      if (String(agent.id).startsWith(this.cfg.agentId) && deliver(agent)) dispose();
    });
    setTimeout(() => dispose(), 30 * 60_000);
  }

  private registerTools(): void {
    const { ctx } = this;

    ctx.tools.register(defineTool({
      name: 'self_restart',
      description: '重启 agent 自身。用途：①修改插件代码后重启生效；②添加/修改插件配置（cordis.patch.yml）后重启加载；③状态异常时冷启动恢复；④定期维护。重启前自动把未提交改动存入 wip 分支检查点；若新代码导致启动失败会自动回滚，不会变砖。重启后自动收到续跑消息。每小时最多 10 次。',
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
      execute: async (args: any, exec?: any) => {
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
          // 记录发起会话（agent.id === session id），重启后续跑消息优先回投这里。
          // 双通道捕获：exec.agent 由 agent loop 显式传递；currentInitiator() 是
          // 同进程因果归因（async 上下文边界），任一命中即可。
          let originAgentId: string | null = exec?.agent?.id != null ? String(exec.agent.id) : null;
          if (!originAgentId) {
            try {
              const init = (this.ctx.agents as any).currentInitiator?.();
              if (init?.id != null) originAgentId = String(init.id);
            } catch { /* 无 initiator 边界（如定时任务触发），保持 null 走兜底投递 */ }
          }
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
            origin_agent_id: originAgentId,
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
          // 注意：checkpoint_branch 无代码改动时为 null，但输出 schema 要求 string——
          // 直接返回 null 会让调用方收到 "must be a string" 错误，而重启器已经 spawn，
          // 造成"看似失败实则已重启"的循环中断（2026-08-20 两次实发）。归一化为空字符串。
          return {
            success: true,
            checkpoint_branch: branch ?? '',
            checkpoint_files: wip?.files ?? [],
            attempt,
            origin_agent_id: originAgentId,
            message: `重启已安排，数秒后执行，当前会话将被终止。检查点：${branch ?? '无代码改动'}${wip ? `（含 ${wip.files.length} 个文件，如有不属于本次修复的改动请留意：${wip.files.join(', ')}）` : ''}。续跑消息将回投会话：${originAgentId ?? '(未识别发起会话，兜底投 investor 根 Agent)'}。日志：${logPath}`,
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

    // ===== 自我认知工具（self-awareness）=====

    ctx.tools.register(defineTool({
      name: 'self_system_prompt',
      description: '获取自己的完整系统提示词：所有 section（含名称、order、内容）、注入变量、可见工具清单。适用于：①自我认知——确认自己的身份、行为准则、约束条件；②审计——检查 prompt 是否符合预期；③调试——理解模型行为偏差的来源。返回的 rendered_prompt 是变量插值后的最终文本，即模型实际看到的提示词。',
      parameters: {
        include_rendered: {
          type: 'boolean',
          description: '是否包含渲染后的完整提示词文本（可能较长），默认 true',
          default: true,
        },
        include_variables: {
          type: 'boolean',
          description: '是否包含注入变量的值，默认 true',
          default: true,
        },
        section_name: {
          type: 'string',
          description: '只看某个 section（按名称精确匹配），不传则返回全部',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            sections: { type: 'array', description: '提示词分节列表' },
            tool_names: { type: 'array', description: '可见工具名称列表' },
            tool_count: { type: 'integer', description: '可见工具总数' },
            variables: { type: 'object', description: '注入变量值', additionalProperties: true },
            rendered_prompt: { type: 'string', description: '渲染后的完整提示词' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 10000,
      execute: async (args: any, exec?: any) => {
        // 优先按发起 agent 的作用域组装（包含 agent 级 shadow section）；
        // 无法识别 agent 时退化为全局组装。
        let assembleContext: any = undefined;
        const agent: Agent | undefined = exec?.agent;
        if (agent) {
          try {
            assembleContext = assembleContextFor(agent);
          } catch { /* scope 组装失败则走全局 */ }
        }
        const assembly: any = await (this.ctx as any).systemPrompt.assemble(assembleContext);
        const sections = (assembly.sections ?? []).map((s: any) => ({
          name: s.name,
          order: s.order,
          complete: s.complete ?? false,
          text: s.text,
        }));
        const filtered = args.section_name
          ? sections.filter((s: any) => s.name === args.section_name)
          : sections;
        const result: any = {
          scope: agent ? String(agent.id) : 'global',
          sections: filtered,
          section_count: filtered.length,
          tool_names: (assembly.tools ?? []).map((t: any) => t.name).sort(),
          tool_count: (assembly.tools ?? []).length,
        };
        if (args.section_name && filtered.length === 0) {
          result.message = `未找到名为 "${args.section_name}" 的 section，可用名称：${sections.map((s: any) => s.name).join(', ')}`;
        }
        if (args.include_variables !== false) {
          result.variables = assembly.variables ?? {};
        }
        if (args.include_rendered !== false) {
          result.rendered_prompt = renderPrompt(assembly);
          result.rendered_chars = result.rendered_prompt.length;
        }
        
        // A-1 修复：清洗非 lossless JSON 值（undefined/function/循环引用）
        // 确保 tool 输出通过 lossless JSON 验证
        const sanitize = (obj: any): any => {
          if (obj === undefined || obj === null) return null;
          if (typeof obj === 'function') return null;
          if (typeof obj !== 'object') return obj;
          if (Array.isArray(obj)) return obj.map(sanitize).filter(v => v !== null);
          const clean: Record<string, any> = {};
          for (const [k, v] of Object.entries(obj)) {
            const sanitized = sanitize(v);
            if (sanitized !== null) clean[k] = sanitized;
          }
          return clean;
        };
        
        return sanitize(result) as any;
      },
    } as any));

    ctx.tools.register(defineTool({
      name: 'self_info',
      description: '获取自身完整信息快照：身份（profile/版本）、进程状态（pid/运行时长/内存）、git 状态、生命周期状态（重启计数/pending 任务）、工具清单统计、关键配置。适用于：①自我认知的起点——回答"我是谁、我在什么状态"；②诊断问题前确认运行环境；③自我学习时的上下文快照。比 self_status 更全面：self_status 聚焦生命周期/git，self_info 包含进程、工具、配置全景。',
      parameters: {
        include_tool_names: {
          type: 'boolean',
          description: '是否列出全部工具名称（可能较长），默认 false 只返回数量',
          default: false,
        },
      },
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        const now = Date.now();
        const mem = process.memoryUsage();

        // 读取自身 package.json 获取版本
        let pkgInfo: any = { name: '@pi-investment/lifecycle', version: 'unknown' };
        try {
          pkgInfo = JSON.parse(readFileSync(join(this.cfg.agentDhRoot, 'packages/lifecycle/package.json'), 'utf-8'));
        } catch { /* 读取失败用默认值 */ }

        // 通过 prompt 组装拿到当前可见工具清单
        let toolNames: string[] = [];
        try {
          const assembly: any = await (this.ctx as any).systemPrompt.assemble();
          toolNames = (assembly.tools ?? []).map((t: any) => t.name).sort();
        } catch { /* 组装失败则工具清单留空 */ }

        const result: any = {
          identity: {
            // 2026-08-21：身份来自 agents.json 注册表（唯一 id + 名字）
            id: this.identity.id,
            name: this.identity.name,
            role: this.identity.role,
            instance: this.identity.instance,
            port: this.identity.port,
            profile: 'investment',
            lifecycle_plugin_version: pkgInfo.version,
            agent_id: this.cfg.agentId,
          },
          process: {
            pid: process.pid,
            node_version: process.version,
            uptime_seconds: Math.round(process.uptime()),
            uptime_human: `${Math.floor(process.uptime() / 3600)}h ${Math.floor((process.uptime() % 3600) / 60)}m`,
            memory_mb: {
              rss: Math.round(mem.rss / 1024 / 1024),
              heap_used: Math.round(mem.heapUsed / 1024 / 1024),
              heap_total: Math.round(mem.heapTotal / 1024 / 1024),
            },
            cwd: process.cwd(),
          },
          git: {
            branch: this.repo.currentBranch(),
            head: this.repo.head(),
            has_uncommitted_changes: this.repo.hasChanges(['agent-dh/']),
            last_known_good: this.state.readLastKnownGood(),
          },
          lifecycle: {
            pending: this.state.readPending(),
            pending_done: this.state.readPendingDone(),
            last_restart_result: this.state.readRestartResult(),
            restarts_this_hour: this.state.checkRateLimit(this.cfg.maxRestartsPerHour, now).count,
            max_restarts_per_hour: this.cfg.maxRestartsPerHour,
          },
          tools: {
            visible_count: toolNames.length,
            ...(args.include_tool_names ? { names: toolNames } : {}),
          },
          config: {
            port: this.cfg.port,
            repo_root: this.cfg.repoRoot,
            agent_dh_root: this.cfg.agentDhRoot,
            profile_dir: this.cfg.profileDir,
          },
          timestamp: new Date(now).toISOString(),
        };
        return result as any;
      },
    } as any));

    // ===== 窗口注册表工具（2026-08-21，窗口随机开但要能点名调动） =====

    // window_list - 列出所有注册窗口
    ctx.tools.register(defineTool({
      name: 'window_list',
      description: '列出窗口注册表：所有已登记窗口（唯一编码、角色、当前任务、状态、最近活跃），每个窗口取最新一条记录。适用于：用户随机打开多个窗口后，查"哪个窗口在干什么"、按编码点名调动某个窗口。',
      parameters: {},
      output: {
        schema: {
          type: 'object',
          properties: {
            windows: { type: 'array', items: { type: 'object', additionalProperties: true } },
            total: { type: 'number' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async () => {
        const res: any = await this.aos.memory.search({ query: 'window', tag: 'system:windows', top_k: 100 });
        const items: any[] = res?.memories || res?.items || [];
        // 每个窗口取最新一条（append-only，updated_at 最大者）
        const byWindow = new Map<string, any>();
        for (const it of items) {
          let payload: any = null;
          try { payload = typeof it.content === 'string' ? JSON.parse(it.content) : it.content; } catch { continue; }
          if (!payload?.window) continue;
          const prev = byWindow.get(payload.window);
          if (!prev || String(payload.updated_at ?? it.created_at) > String(prev.updated_at)) {
            byWindow.set(payload.window, { ...payload, memory_id: it.id });
          }
        }
        const windows = [...byWindow.values()].sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
        return { windows, total: windows.length } as any;
      },
    } as any));

    // window_update - 更新本窗口的当前任务/状态（含技能自报）
    ctx.tools.register(defineTool({
      name: 'window_update',
      description: '更新当前窗口在注册表中的状态：正在做什么任务、技能标签、忙闲、进展备注。窗口自动识别（从调用上下文取 session id）。适用于：开始新任务时自报家门，让办公室（OS）能按技能和忙闲派单。',
      parameters: {
        task: { type: 'string', description: '当前任务描述，如 "M4 仓位映射表实施"' },
        status: { type: 'string', description: '状态：idle 空闲 / active 在干 / blocked 卡死 / done 完成', enum: ['idle', 'active', 'blocked', 'done'] },
        skills: { type: 'array', description: '技能标签（自报），如 ["市场感知","回测","插件开发"]。办公室派单依据之一', items: { type: 'string' } },
        note: { type: 'string', description: '进展备注' },
      },
      output: {
        schema: { type: 'object', properties: { window: { type: 'string' }, updated: { type: 'boolean' }, queued: { type: 'boolean' } }, additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async (args: any, exec?: any) => {
        const sessionId = String(exec?.agent?.id ?? '');
        if (!sessionId) throw new Error('无法识别当前窗口（exec.agent 缺失）');
        const window = this.windowCode(sessionId);

        // 继承上次的 skills/task（未传时保留，防止状态更新把档案字段抹空——2026-08-21 E2E 实证：
        // 新员工标记 done 时 skills 从 ['测试'] 被抹成 []）
        let prev: any = null;
        try {
          const memRes: any = await this.aos.memory.search({ query: window, tag: 'system:windows', top_k: 20 });
          const items: any[] = memRes?.memories || memRes?.items || [];
          for (const it of items) {
            try {
              const p = typeof it.content === 'string' ? JSON.parse(it.content) : it.content;
              if (p?.session_id === sessionId && (!prev || String(p.updated_at) > String(prev.updated_at))) prev = p;
            } catch { /* 跳过 */ }
          }
        } catch { /* 查不到则全部用本次输入 */ }

        const profile = {
          window,
          session_id: sessionId,
          agent_id: this.identity.id,
          role: this.identity.name,
          skills: args.skills ?? prev?.skills ?? [],
          task: args.task ?? prev?.task ?? null,
          note: args.note ?? null,
          status: args.status ?? 'active',
          started_at: prev?.started_at ?? new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };

        // 双轨写（outbox 防丢：OS 挂了进积压，恢复后自动重放）
        const w1 = await this.osWrite('memory_write', {
          title: `window ${window} ${profile.status}${profile.task ? `：${profile.task}` : ''}`,
          content: JSON.stringify(profile),
          namespace: 'data',
          tags: ['system:windows', 'window', window],
        });
        const w2 = await this.osWrite('skill_upsert', profile);

        return { window, updated: true, queued: w1.queued || w2.queued } as any;
      },
    } as any));

    // office_roster - 办公室花名册（Skills API 结构化档案）
    ctx.tools.register(defineTool({
      name: 'office_roster',
      description: '办公室花名册：所有窗口的结构化档案（编码、角色、技能、忙闲、当前任务、最近更新时间）。派单决策的数据源——先看谁在、谁会、谁有空。',
      parameters: {},
      output: {
        schema: { type: 'object', properties: { roster: { type: 'array', items: { type: 'object', additionalProperties: true } }, total: { type: 'number' } }, additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async () => {
        // 2026-08-21 E2E 修正：OS Skills 的 PUT 是"发新版本"，不更新档案顶层字段
        // （实测 availability 停在 busy）。因此动态状态（忙闲/任务/备注/技能）
        // 以记忆库事件流水（每窗口最新一条）为准；Skills API 作长期技能库存档。
        const memRes: any = await this.aos.memory.search({ query: 'window', tag: 'system:windows', top_k: 100 });
        const items: any[] = memRes?.memories || memRes?.items || [];
        const byWindow = new Map<string, any>();
        for (const it of items) {
          let p: any = null;
          try { p = typeof it.content === 'string' ? JSON.parse(it.content) : it.content; } catch { continue; }
          if (!p?.window) continue;
          const prev = byWindow.get(p.window);
          const ts = String(p.updated_at ?? it.created_at ?? '');
          if (!prev || ts > String(prev.updated_at ?? '')) {
            byWindow.set(p.window, { ...p, updated_at: ts });
          }
        }

        // Skills 库存档（标注入职时间/是否已被移除）
        const base = (this.cfg as any).agentOS?.baseURL || 'http://localhost:8080';
        let skillMap = new Map<string, any>();
        try {
          const res = await fetch(`${base}/api/v1/skills`);
          const data: any = await res.json();
          const skills: any[] = data?.skills ?? data ?? [];
          for (const s of skills) {
            if (s.category === 'window' && s.status !== 'inactive') {
              skillMap.set(s.metadata?.window ?? s.name, { skill_id: s.id, hired_at: s.created_at ?? null });
            }
          }
        } catch { /* Skills API 不可用不阻塞花名册 */ }

        const roster = [...byWindow.values()].map((p: any) => ({
          window: p.window,
          agent_id: p.agent_id ?? null,
          role: p.role ?? null,
          skills: p.skills ?? [],
          availability: p.status ?? 'unknown',
          task: p.task ?? null,
          note: p.note ?? null,
          updated_at: p.updated_at ?? null,
          session_id: p.session_id ?? null,
          skill_record: skillMap.get(p.window) ?? null,
        })).sort((a: any, b: any) => String(b.updated_at).localeCompare(String(a.updated_at)));
        return { roster, total: roster.length } as any;
      },
    } as any));

    // assign_task - 办公室派单：向指定窗口投递任务
    ctx.tools.register(defineTool({
      name: 'assign_task',
      description: '向指定窗口派发任务（followup 投递到该窗口的会话）。派单前建议先 office_roster 看谁有空谁会。目标窗口不在线会报错——可考虑 hire_window 招人。',
      parameters: {
        window: { type: 'string', description: '目标窗口编码，如 w-2c68a436', required: true },
        task: { type: 'string', description: '任务内容（完整描述，对方窗口按此执行）', required: true },
        note: { type: 'string', description: '备注（期限、约束、协作要求）' },
      },
      output: {
        schema: { type: 'object', properties: { assigned: { type: 'boolean' }, window: { type: 'string' } }, additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async (args: any, exec?: any) => {
        // 从花名册找目标窗口的 session_id
        const base = (this.cfg as any).agentOS?.baseURL || 'http://localhost:8080';
        const res = await fetch(`${base}/api/v1/skills`);
        const data: any = await res.json();
        const skills: any[] = data?.skills ?? data ?? [];
        const target = skills.find((s: any) => s.name === `window:${args.window}` || s.metadata?.window === args.window);
        if (!target) throw new Error(`窗口 ${args.window} 不在花名册（从未上线或已消亡）`);

        const sessionId = target.metadata?.session_id;
        const agent: any = (this.ctx as any).agents.get(sessionId);
        if (!agent) throw new Error(`窗口 ${args.window} 不在线（agent 未注册），任务未投递。可用 hire_window 招新人承接。`);

        const fromWindow = this.windowCode(String(exec?.agent?.id ?? 'unknown'));
        agent.followup(createUserMessage({
          content: [{ type: 'text', text: `【办公室派单】来自窗口 ${fromWindow}（${this.identity.name}）：\n\n任务：${args.task}\n${args.note ? `备注：${args.note}\n` : ''}\n完成后请 window_update 更新你的状态，并把结果写入 memory（namespace=decision）供溯源。` }],
          source: { kind: 'plugin', plugin: 'lifecycle' },
        }));

        // 更新目标窗口档案为 busy
        await this.osWrite('skill_upsert', {
          ...target.metadata,
          window: args.window,
          session_id: sessionId,
          agent_id: target.owner ?? 'investor',
          role: this.identity.name,
          status: 'busy',
          task: args.task,
        });

        return { assigned: true, window: args.window } as any;
      },
    } as any));

    // hire_window - 招人：创建新窗口（agent+session）并派初始任务
    ctx.tools.register(defineTool({
      name: 'hire_window',
      description: '招一个新窗口（创建新 agent 会话）、登记到办公室、派发初始任务。适用于：花名册没有合适人选时扩招。新窗口继承角色身份，获得独立窗口编码。',
      parameters: {
        task: { type: 'string', description: '初始任务（新窗口开工即执行）', required: true },
        skills: { type: 'array', description: '期望技能标签（写入档案）', items: { type: 'string' } },
        provider: { type: 'string', description: 'LLM 路由，默认 deepseek-official', default: 'deepseek-official' },
        model: { type: 'string', description: '模型，默认 deepseek-v4-flash', default: 'deepseek-v4-flash' },
      },
      output: {
        schema: { type: 'object', properties: { hired: { type: 'boolean' }, window: { type: 'string' }, session_id: { type: 'string' } }, additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        const sessionId = `session-${crypto.randomUUID()}`;
        const handle: any = await (this.ctx as any).agents.create({
          sessionId,
          agentOptions: {
            provider: args.provider || 'deepseek-official',
            model: args.model || 'deepseek-v4-flash',
          },
        });
        const window = this.windowCode(sessionId);

        // 登记档案（agent/created 也会触发 registerWindow，这里补全技能/任务信息）
        await this.osWrite('skill_upsert', {
          window,
          session_id: sessionId,
          agent_id: this.identity.id,
          role: this.identity.name,
          skills: args.skills ?? [],
          status: 'busy',
          task: args.task,
        });

        // 派初始任务
        const agent: any = handle?.agent ?? (this.ctx as any).agents.get(sessionId);
        if (agent?.followup) {
          agent.followup(createUserMessage({
            content: [{ type: 'text', text: `【入职任务】你被办公室招为新窗口 ${window}（角色：${this.identity.name}）。\n\n任务：${args.task}\n\n要求：遵守交易宪法（提示词中的 constitution 段）；开工前先 window_update 自报状态；完成后把结论写入 memory（namespace=decision）并 window_update 标记 done。` }],
            source: { kind: 'plugin', plugin: 'lifecycle' },
          }));
        }

        return { hired: true, window, session_id: sessionId } as any;
      },
    } as any));

    // ===== 办公室交流层（2026-08-21，用户批准）：点对点消息 + 公告板 =====
    // 职责切分：数据（信箱/公告板）在 OS 记忆库，动作（寻址/投递）在 DH 插件

    // window_message - 点对点消息（在线直投，离线进信箱，上线补投）
    ctx.tools.register(defineTool({
      name: 'window_message',
      description: '给指定窗口发消息：对方在线则直接投递到其会话，离线则写入 OS 信箱（上线时自动补投）。消息带回信地址（你的窗口编码），对方用 window_message 回复。适用于：窗口间讨论问题、协作确认、经验请教。',
      parameters: {
        window: { type: 'string', description: '目标窗口编码，如 w-2c68a436', required: true },
        message: { type: 'string', description: '消息内容', required: true },
      },
      output: {
        schema: { type: 'object', properties: { delivered: { type: 'boolean' }, queued_offline: { type: 'boolean' }, window: { type: 'string' } }, additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async (args: any, exec?: any) => {
        const fromSession = String(exec?.agent?.id ?? '');
        const fromWindow = this.windowCode(fromSession || 'unknown');

        // 寻址：从记忆库最新档案取目标 session_id
        const memRes: any = await this.aos.memory.search({ query: args.window, tag: 'system:windows', top_k: 20 });
        const items: any[] = memRes?.memories || memRes?.items || [];
        let targetSession: string | null = null;
        for (const it of items) {
          try {
            const p = typeof it.content === 'string' ? JSON.parse(it.content) : it.content;
            if (p?.window === args.window && p?.session_id) targetSession = p.session_id;
          } catch { /* 跳过 */ }
        }
        if (!targetSession) throw new Error(`窗口 ${args.window} 不在花名册（从未上线）`);

        const msgRecord = {
          from: fromWindow,
          from_session: fromSession,
          to: args.window,
          message: args.message,
          ts: new Date().toISOString(),
          delivered: false,
        };

        // 在线直投
        const agent: any = (this.ctx as any).agents.get(targetSession);
        if (agent?.followup) {
          agent.followup(createUserMessage({
            content: [{ type: 'text', text: `【窗口消息】来自 ${fromWindow}：\n\n${args.message}\n\n回信方式：window_message(window='${fromWindow}', message='...')` }],
            source: { kind: 'plugin', plugin: 'lifecycle' },
          }));
          msgRecord.delivered = true;
        }

        // 无论如何写信箱（别丢信息 + 可审计）
        await this.osWrite('memory_write', {
          title: `msg ${fromWindow}→${args.window}${msgRecord.delivered ? '' : '（离线）'}`,
          content: JSON.stringify(msgRecord),
          namespace: 'data',
          tags: ['office:msg', `office:inbox:${args.window}`, `office:outbox:${fromWindow}`],
        });

        return { delivered: msgRecord.delivered, queued_offline: !msgRecord.delivered, window: args.window } as any;
      },
    } as any));

    // board_post - 公告板发帖
    ctx.tools.register(defineTool({
      name: 'board_post',
      description: '在办公室公告板发帖：发现、疑问、复盘结论、协作倡议，全员可读。交流产生的"传闻"要变成"基因"仍需过验证门——公告板是讨论区不是真理区。',
      parameters: {
        title: { type: 'string', description: '标题（一句话）', required: true },
        content: { type: 'string', description: '内容', required: true },
        kind: { type: 'string', description: '类型：finding 发现 / question 疑问 / review 复盘 / proposal 倡议', enum: ['finding', 'question', 'review', 'proposal'], default: 'finding' },
      },
      output: {
        schema: { type: 'object', properties: { posted: { type: 'boolean' } }, additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async (args: any, exec?: any) => {
        const fromWindow = this.windowCode(String(exec?.agent?.id ?? 'unknown'));
        await this.osWrite('memory_write', {
          title: `[${args.kind ?? 'finding'}] ${args.title}`,
          content: JSON.stringify({
            marker: 'office-board-post',  // 检索锚点（OS 搜索按 title/content 文本匹配，tag 只做过滤——E2E 实测）
            kind: args.kind ?? 'finding',
            title: args.title,
            content: args.content,
            from: fromWindow,
            ts: new Date().toISOString(),
          }),
          namespace: 'data',
          tags: ['office:board', `kind:${args.kind ?? 'finding'}`],
        });
        return { posted: true } as any;
      },
    } as any));

    // board_read - 读公告板
    ctx.tools.register(defineTool({
      name: 'board_read',
      description: '读办公室公告板：最新帖子在前。适用于：空闲/例会时了解其他窗口的发现与疑问、找协作机会。',
      parameters: {
        limit: { type: 'number', description: '返回条数，默认 10', default: 10 },
        kind: { type: 'string', description: '按类型过滤：finding/question/review/proposal' },
      },
      output: {
        schema: { type: 'object', properties: { posts: { type: 'array', items: { type: 'object', additionalProperties: true } }, total: { type: 'number' } }, additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        const tag = args.kind ? `kind:${args.kind}` : 'office:board';
        // OS 搜索按 title/content 文本匹配（tag 只是过滤）：用内容里的锚点词作 query
        const res: any = await this.aos.memory.search({ query: args.kind ?? 'office-board-post', tag, top_k: args.limit ?? 10 });
        const items: any[] = res?.memories || res?.items || [];
        const posts = items.map((it: any) => {
          try { return { ...(typeof it.content === 'string' ? JSON.parse(it.content) : it.content), id: it.id }; }
          catch { return { title: it.title, id: it.id }; }
        });
        return { posts, total: posts.length } as any;
      },
    } as any));

    // inbox_check - 查自己的信箱
    ctx.tools.register(defineTool({
      name: 'inbox_check',
      description: '查本窗口的信箱（含离线期间收到的消息）。适用于：上线/空闲时收信；例会时统一处理来信。',
      parameters: {},
      output: {
        schema: { type: 'object', properties: { messages: { type: 'array', items: { type: 'object', additionalProperties: true } }, total: { type: 'number' } }, additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async (_args: any, exec?: any) => {
        const window = this.windowCode(String(exec?.agent?.id ?? ''));
        if (window === '') throw new Error('无法识别当前窗口');
        const res: any = await this.aos.memory.search({ query: 'msg', tag: `office:inbox:${window}`, top_k: 50 });
        const items: any[] = res?.memories || res?.items || [];
        const messages = items.map((it: any) => {
          try { return typeof it.content === 'string' ? JSON.parse(it.content) : it.content; }
          catch { return null; }
        }).filter(Boolean);
        return { messages, total: messages.length } as any;
      },
    } as any));

    // ===== OS 提醒体系管理工具（2026-08-25 用户决策：提醒走 OS，不走 dsh session-local）=====
    // 权威注册表 = Agent OS scheduler（postgres 持久）；投递 = bridge → OS 信箱 → 60s 轮询 followup

    // reminder_create - 创建 OS 级提醒（cron 周期任务）
    ctx.tools.register(defineTool({
      name: 'reminder_create',
      description: '创建 OS 级定时提醒（Agent OS scheduler，postgres 持久——重启/会话 fork 不丢，解决 dsh 提醒 session-local 缺陷）。cron 五段式（分 时 日 月 周），如每日15:30="30 15 * * *"、工作日盘后="30 15 * * 1-5"、周五16点="0 16 * * 5"。一次性提醒用日期限定 cron（如 "35 9 26 8 *"=8月26日09:35），用后记得 reminder_delete。',
      parameters: {
        name: { type: 'string', description: '任务名（唯一，如 post-market-routine）', required: true },
        cron: { type: 'string', description: 'cron 五段式表达式', required: true },
        prompt: { type: 'string', description: '到期注入会话的提醒内容', required: true },
        window: { type: 'string', description: '目标窗口编码，默认本窗口' },
      },
      output: {
        schema: { type: 'object', properties: { id: { type: 'string' }, name: { type: 'string' }, cron: { type: 'string' } }, additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async (args: any, exec?: any) => {
        const window = args.window || this.windowCode(String(exec?.agent?.id ?? '')) || this.windowCode(this.identity.id);
        const bridgeCmd = `/Users/yunpeng/pi-investment/agent-dh/scripts/os-remind-bridge.sh "${args.name}"`;
        const task = await this.aos.scheduler.registerTask({
          name: args.name,
          owner: this.identity.id,
          description: `OS 提醒（DH lifecycle 注册，窗口 ${window}）`,
          cron: args.cron,
          command: bridgeCmd,
          payload: { prompt: args.prompt, window },
          enabled: true,
        } as any);
        return { id: String((task as any)?.id ?? ''), name: args.name, cron: args.cron, window } as any;
      },
    } as any));

    // reminder_list - 列出 OS 级提醒
    ctx.tools.register(defineTool({
      name: 'reminder_list',
      description: '列出 OS 级定时提醒（Agent OS scheduler 任务）及其启用状态。供：检查提醒体系健康（若为空说明体系被清空，应重建）。',
      parameters: {},
      output: {
        schema: { type: 'object', properties: { tasks: { type: 'array', items: { type: 'object', additionalProperties: true } }, total: { type: 'number' } }, additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async () => {
        const tasks: any[] = await this.aos.scheduler.listTasks();
        const mine = tasks.filter((t: any) => String(t.command ?? '').includes('os-remind-bridge'));
        return {
          tasks: mine.map((t: any) => ({
            id: String(t.id), name: t.name, cron: t.cron ?? t.schedule, enabled: t.enabled,
            window: t.payload?.window ?? null,
          })),
          total: mine.length,
        } as any;
      },
    } as any));

    // reminder_delete - 删除 OS 级提醒
    ctx.tools.register(defineTool({
      name: 'reminder_delete',
      description: '删除 OS 级定时提醒（按任务 ID 或名称）。一次性提醒触发后应删除避免明年同日再响。',
      parameters: {
        id: { type: 'string', description: '任务 ID（优先）或任务名' },
      },
      output: {
        schema: { type: 'object', properties: { deleted: { type: 'boolean' } }, additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        let id = args.id;
        if (!id) throw new Error('需要任务 ID 或名称');
        if (!/^[0-9a-f-]{36}$/i.test(id)) {
          // 按名称查 ID
          const tasks: any[] = await this.aos.scheduler.listTasks();
          const hit = tasks.find((t: any) => t.name === id && String(t.command ?? '').includes('os-remind-bridge'));
          if (!hit) return { deleted: false, message: `未找到提醒任务: ${id}` } as any;
          id = String(hit.id);
        }
        await this.aos.scheduler.deleteTask(id);
        return { deleted: true, id } as any;
      },
    } as any));
  }
}
