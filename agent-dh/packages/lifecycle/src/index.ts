import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { readFileSync, appendFileSync, writeFileSync, existsSync } from 'node:fs';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { assembleContextFor } from '@deepseek-ai/dsh-agent';
import { renderPrompt } from '@deepseek-ai/dsh-system-prompt';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { GitRepo } from './git.js';
import { PendingResume, RestartResult, StateStore } from './state.js';
import { registerBoardUpdate, registerBoardRead, registerBoardPost } from './board-tools.js';


// 导入 BaseTool 工具
import {
  SelfRestartTool,
  SelfFinalizeTool,
  SelfStatusTool,
} from './tools';
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
  // 触发链路：OS cron 任务 → os-remind-bridge.sh → OS 记忆库信箱 → 本轮询 → 投递
  // 用户补充设计（同日）：①提示词持久化（payload+信箱+执行记录三处全文保存）
  //   ②执行留痕进记忆（每次触发写执行记录，executor/方式/时间可溯）
  //   ③目标窗口不在线 → 创建新窗口代为执行（不等待上线，任务必须被执行）
  private reminderPollTimer: ReturnType<typeof setInterval> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null; // RFC 010: 心跳定时器
  private registeredWindows: Set<string> = new Set(); // RFC 010: 已注册窗口集合
  private registrationPoller: ReturnType<typeof setInterval> | null = null; // RFC 010: 轮询备份定时器

  private setupOsReminderPoller(): void {
    const poll = async () => {
      try {
        // 2026-08-27 修复：myWindow 必须从在线 session 推导（session-xxx → w-xxx），
        // 不能从 identity.id（'investor'）推导——后者与信箱 tag（office:reminder:w-xxx）永不匹配，
        // 导致提醒写入信箱后永远不被投递。
        const rootsEarly: any[] = this.ctx.agents.roots();
        const onlineRoot = rootsEarly.find((a) => String(a.id).startsWith(this.cfg.agentId)) ?? rootsEarly[0];
        const myWindow = onlineRoot ? this.windowCode(String(onlineRoot.id)) : this.windowCode(this.identity.id);
        const res: any = await this.aos.memory.search({ query: 'reminder', tag: `office:reminder:${myWindow}`, top_k: 50 });
        const items: any[] = res?.memories || res?.items || [];

        // 防重复投递（2026-08-25 验收发现）：原记录永远不会被改（append-only），
        // 仅凭记录的 delivered=false 会每分钟重复投递。先收集已投递标记的
        // 关联键（task|fired_at），命中即跳过。
        const execRes: any = await this.aos.memory.search({ query: 'delivered', tag: 'office:reminder:exec', top_k: 100 });
        const execItems: any[] = execRes?.memories || execRes?.items || [];
        const deliveredKeys = new Set<string>();
        for (const e of execItems) {
          try {
            const ep = typeof e.content === 'string' ? JSON.parse(e.content) : e.content;
            if (ep?.task && ep?.fired_at) deliveredKeys.add(`${ep.task}|${ep.fired_at}`);
          } catch { /* skip */ }
        }

        for (const it of items) {
          let p: any = null;
          try { p = typeof it.content === 'string' ? JSON.parse(it.content) : it.content; } catch { continue; }
          if (!p || p.delivered) continue;
          if (deliveredKeys.has(`${p.task}|${p.fired_at}`)) continue;  // 已投递过，跳过

          // ① 找在线目标窗口
          const roots: any[] = this.ctx.agents.roots();
          const online = roots.find((a) => String(a.id).startsWith(this.cfg.agentId)) ?? roots[0];
          let executor: any = null;

          if (online?.followup) {
            try {
              online.followup(createUserMessage({
                content: [{ type: 'text', text: `【OS 提醒】${p.task ?? ''}\n\n${p.prompt}\n\n（来源：Agent OS 定时任务 ${p.task_id ?? ''}，触发于 ${p.fired_at ?? ''}）` }],
                source: { kind: 'plugin', plugin: 'lifecycle' },
              }));
              executor = { mode: 'direct', session_id: String(online.id) };
            } catch { /* 投递失败走创建窗口 */ }
          }

          // ② 没有在线窗口 → 创建新窗口代为执行（用户决策：任务必须被执行，不等待上线）
          if (!executor) {
            try {
              const sessionId = `session-${crypto.randomUUID()}`;
              await (this.ctx as any).agents.create({
                sessionId,
                agentOptions: { provider: 'deepseek-official', model: 'deepseek-v4-flash' },
              });
              const newWindow = this.windowCode(sessionId);
              const newAgent: any = (this.ctx as any).agents.get(sessionId);
              newAgent?.followup?.(createUserMessage({
                content: [{ type: 'text', text: `【OS 提醒·代执行】目标窗口 ${p.window} 不在线，由你（新窗口 ${newWindow}）代为执行定时任务「${p.task ?? ''}」：\n\n${p.prompt}\n\n要求：遵守交易宪法（提示词 constitution 段）；完成后把结论写入 memory（namespace=decision）并 window_update 标记 done。` }],
                source: { kind: 'plugin', plugin: 'lifecycle' },
              }));
              // 登记新窗口进花名册
              await this.osWrite('skill_upsert', {
                window: newWindow,
                session_id: sessionId,
                agent_id: this.identity.id,
                role: this.identity.name,
                skills: ['提醒代执行'],
                status: 'busy',
                task: `代执行提醒 ${p.task ?? ''}`,
              });
              executor = { mode: 'spawned', session_id: sessionId, window: newWindow };
            } catch { continue; /* 创建失败留下轮重试，信箱记录仍在 */ }
          }

          // ③ 执行留痕（含完整提示词，可溯）
          await this.osWrite('memory_write', {
            title: `reminder ${p.task ?? ''} delivered`,
            content: JSON.stringify({
              ...p,  // 含完整 prompt（提示词持久化）
              delivered: true,
              delivered_at: new Date().toISOString(),
              executor,
            }),
            namespace: 'data',
            tags: ['office:delivered', 'office:reminder:exec', `office:reminder:${myWindow}`],
          });
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
    // RFC 010: 窗口创建时注册到 Agent OS Window Registry
    this.ctx.on('agent/created' as any, (agent: any) => {
      this.ctx.logger.info(`[RFC 010] agent/created event fired for agent: ${agent?.id}`);
      this.registerWindow(agent).catch(() => { /* 注册失败不影响 agent 创建 */ });
    });
    
    // RFC 010: 等待系统就绪后注册所有已存在的 root agents
    // （插件加载时 agent 可能尚未创建，或 agents 服务尚未就绪）
    this.ctx.on('ready', () => {
      this.ctx.logger.info('[RFC 010] System ready, checking for existing root agents...');
      
      try {
        const agentsService = this.ctx.agents;
        this.ctx.logger.info(`[RFC 010] agents service exists: ${!!agentsService}`);
        this.ctx.logger.info(`[RFC 010] agents.roots exists: ${typeof agentsService?.roots}`);
        
        if (!agentsService?.roots) {
          this.ctx.logger.warn('[RFC 010] agents.roots() not available, skipping initial registration');
          return;
        }
        
        const roots: any[] = agentsService.roots();
        this.ctx.logger.info(`[RFC 010] Found ${roots.length} existing root agents`);
        
        if (roots.length === 0) {
          this.ctx.logger.info('[RFC 010] No root agents at startup (normal - agents created on user interaction)');
        } else {
          for (const agent of roots) {
            this.ctx.logger.info(`[RFC 010] Registering existing agent: ${agent?.id}`);
            this.registerWindow(agent).catch((err) => {
              this.ctx.logger.warn(`[RFC 010] Failed to register existing agent ${agent?.id}: ${err?.message}`);
            });
          }
        }
        
        // 启动轮询备份机制（防御性编程：如果事件系统失效，轮询作为兜底）
        this.startRegistrationPoller();
      } catch (err: any) {
        this.ctx.logger.error(`[RFC 010] Failed to enumerate root agents: ${err?.message}`, err);
      }
    });
    
    // RFC 010: 启动心跳发送器（30s 间隔）
    this.startHeartbeat();
    
    // RFC 010: 进程退出时注销所有窗口
    this.ctx.on('dispose', () => {
      this.unregisterAllWindows().catch(() => {});
      if (this.heartbeatTimer) {
        clearInterval(this.heartbeatTimer);
        this.heartbeatTimer = null;
      }
      if (this.registrationPoller) {
        clearInterval(this.registrationPoller);
        this.registrationPoller = null;
      }
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
    
    // 提取窗口名称：尝试从第一条用户消息提取主题
    let windowName = this.identity.name; // 默认使用角色名
    try {
      const messages = agent?.messages || [];
      const firstUserMsg = messages.find((m: any) => m?.role === 'user');
      if (firstUserMsg?.content) {
        // 提取文本内容
        let text = '';
        if (typeof firstUserMsg.content === 'string') {
          text = firstUserMsg.content;
        } else if (Array.isArray(firstUserMsg.content)) {
          const textPart = firstUserMsg.content.find((c: any) => c?.type === 'text');
          text = textPart?.text || '';
        }
        // 截取前50字符作为窗口名称
        if (text.trim()) {
          windowName = text.trim().substring(0, 50);
          if (text.length > 50) windowName += '...';
        }
      }
    } catch (err) {
      // 提取失败，使用默认名称
      this.ctx.logger.debug(`[RFC 010] Failed to extract window name from messages: ${err}`);
    }
    
    // RFC 010: 调用 Agent OS Window Registry API 注册窗口
    try {
      await this.aos.post('/api/v1/registry/agents/register', {
        agent_id: window,
        type: this.identity.role,
        name: windowName,
        instance: this.identity.instance,
        session_id: sessionId,
        capabilities: ['trading', 'analysis', 'decision'], // TODO: 从配置或工具清单提取
        status: 'idle',
        host: '127.0.0.1',
        port: this.identity.port,
        pid: process.pid,
        metadata: {
          started_at: new Date().toISOString(),
          topic: windowName !== this.identity.name ? windowName : null, // 记录原始主题
        },
      });
      this.registeredWindows.add(window);
      this.ctx.logger.info(`[RFC 010] Window registered: ${window} (role=${this.identity.role})`);
    } catch (err: any) {
      this.ctx.logger.warn(`[RFC 010] Failed to register window ${window}: ${err?.message}`);
    }
    
    // 保留原有逻辑：写入 memory + skills API（向后兼容）
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

  // ===== RFC 010: Window Registry 心跳与注销 =====

  /** 启动心跳发送器（30s 间隔） */
  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      this.sendHeartbeats().catch((err) => {
        this.ctx.logger.warn(`[RFC 010] Heartbeat failed: ${err?.message}`);
      });
    }, 30000); // 30 秒
  }

  /** 向 Agent OS 发送所有已注册窗口的心跳 */
  private async sendHeartbeats(): Promise<void> {
    for (const window of this.registeredWindows) {
      try {
        await this.aos.post('/api/v1/registry/agents/heartbeat', {
          agent_id: window,
          status: 'idle', // TODO: 从实际状态推导（idle/active）
          metadata: {
            memory_mb: Math.round(process.memoryUsage().heapUsed / 1024 / 1024),
          },
        });
      } catch (err: any) {
        this.ctx.logger.warn(`[RFC 010] Heartbeat failed for ${window}: ${err?.message}`);
      }
    }
  }

  /** 注销所有窗口（进程退出时调用） */
  private async unregisterAllWindows(): Promise<void> {
    for (const window of this.registeredWindows) {
      try {
        await this.aos.post('/api/v1/registry/agents/unregister', {
          agent_id: window,
        });
        this.ctx.logger.info(`[RFC 010] Window unregistered: ${window}`);
      } catch (err: any) {
        this.ctx.logger.warn(`[RFC 010] Failed to unregister ${window}: ${err?.message}`);
      }
    }
    this.registeredWindows.clear();
  }

  /** 
   * RFC 010: 轮询备份机制 - 防御性编程
   * 每60秒检查一次是否有新的 agent 需要注册
   * 如果 agent/created 事件失效，轮询作为兜底
   */
  private startRegistrationPoller(): void {
    this.registrationPoller = setInterval(() => {
      this.pollAndRegisterNewAgents().catch((err) => {
        this.ctx.logger.warn(`[RFC 010] Registration poller failed: ${err?.message}`);
      });
    }, 60000); // 60 秒检查一次
    
    this.ctx.logger.info('[RFC 010] Registration poller started (60s interval)');
  }

  /** 轮询并注册新 agent */
  private async pollAndRegisterNewAgents(): Promise<void> {
    try {
      const agentsService = this.ctx.agents;
      if (!agentsService?.roots) {
        return;
      }

      const roots: any[] = agentsService.roots();
      let newCount = 0;

      for (const agent of roots) {
        const window = this.windowCode(agent.id);
        
        // 如果窗口尚未注册，则注册
        if (!this.registeredWindows.has(window)) {
          this.ctx.logger.info(`[RFC 010] Poller found new agent: ${window}`);
          await this.registerWindow(agent);
          newCount++;
        }
      }

      if (newCount > 0) {
        this.ctx.logger.info(`[RFC 010] Poller registered ${newCount} new agent(s)`);
      }
    } catch (err: any) {
      this.ctx.logger.error(`[RFC 010] Poller error: ${err?.message}`);
    }
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

  // ===== 工具回调方法 =====

  /**
   * 调度重启
   */
  private async scheduleRestart(reason: string, preserveContext: boolean): Promise<void> {
    // 实现重启逻辑
    // TODO: 完整实现需要保存状态、创建 checkpoint 分支等
    this.ctx.logger('lifecycle').info(`Restart scheduled: ${reason}, preserveContext=${preserveContext}`);

    // 保存 pending resume 状态
    this.state.writePending({
      reason,
      base_branch: this.repo.currentBranch(),
      checkpoint_branch: null,
      resume_task: preserveContext ? 'continue previous task' : null,
      attempt: 0,
    });

    // 触发重启（通过退出进程，让外部脚本重启）
    setTimeout(() => process.exit(0), 1000);
  }

  /**
   * 调度终止
   */
  private async scheduleFinalize(reason: string, saveState: boolean): Promise<void> {
    // 实现终止逻辑
    this.ctx.logger('lifecycle').info(`Finalize scheduled: ${reason}, saveState=${saveState}`);

    if (saveState) {
      // 保存状态到 Agent OS
      await this.osWrite('lifecycle:finalize', { reason, timestamp: new Date().toISOString() });
    }

    // 清理 pending 状态
    this.state.clearPending();

    // 优雅退出
    setTimeout(() => process.exit(0), 1000);
  }

  /**
   * 获取状态
   */
  private async getStatus(detailed: boolean): Promise<any> {
    const uptime = process.uptime();
    const pending = this.state.readPending();

    const status = {
      status: 'running',
      uptime,
      health: {
        repo_clean: this.repo.isClean(),
        current_branch: this.repo.currentBranch(),
        pending_restart: pending !== null,
      },
    };

    if (detailed && pending) {
      (status as any).pending_details = pending;
    }

    return status;
  }

  private registerTools(): void {
    const { ctx } = this;

    // 1. 重启工具（重构为 BaseTool）
    const restartTool = new SelfRestartTool(
      this.scheduleRestart.bind(this)
    );
    ctx.tools.register(restartTool.toDSHToolDefinition());

    // 2. 终止工具（重构为 BaseTool）
    const finalizeTool = new SelfFinalizeTool(
      this.scheduleFinalize.bind(this)
    );
    ctx.tools.register(finalizeTool.toDSHToolDefinition());

    // 3. 状态查询工具（重构为 BaseTool）
    const statusTool = new SelfStatusTool(
      this.getStatus.bind(this)
    );
    ctx.tools.register(statusTool.toDSHToolDefinition());

    // RFC 009: 注册公告板生命周期管理工具
    registerBoardUpdate(this.ctx, this.aos.memory, this.cfg.agentId);
    registerBoardRead(this.ctx, this.aos.memory, this.cfg.agentId);
    registerBoardPost(this.ctx, this.aos.memory, this.cfg.agentId);
  }
}
