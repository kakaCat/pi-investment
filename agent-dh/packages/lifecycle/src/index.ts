import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Context, Service } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import z from '@deepseek-ai/schemastery';
import { readFileSync, appendFileSync, writeFileSync, existsSync } from 'node:fs';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import type { Agent } from '@deepseek-ai/dsh-agent';
import { assembleContextFor } from '@deepseek-ai/dsh-agent';
import { renderPrompt } from '@deepseek-ai/dsh-system-prompt';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { GitRepo } from './git.js';
import { PendingResume, RestartResult, StateStore } from './state.js';
import { NativeReminderScheduler, type NativeTask } from './native-scheduler.js';
import { registerBoardUpdate, registerBoardRead, registerBoardPost } from './board-tools.js';
import { registerWakeWebhook } from './wake-webhook.js';
import { registerAgentOsTrigger } from './agent-os-trigger.js';
import { planAndScheduleRestart, type RestartPlannerDeps } from './restart-planner.js';
import { onBoot } from './boot-hook.js';
import { exitFinalize, describeExitFinalize } from './exit-finalize.js';


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
  /** 自我重启拉起的启动脚本绝对路径；'' = 缺省 profileDir/start.sh（2026-09-12, w-f9c9a5c1） */
  startScript?: string;
  port?: number;
  agentId?: string;
  maxRestartsPerHour?: number;
  /** v2 → dh /wake 唤醒鉴权 token（可选；与 v2 .env 的 AGENT_API_TOKEN 同值才校验） */
  wakeToken?: string;
}

function renderResumeMessage(pending: PendingResume, result: RestartResult | null): string {
  const head = '【自修复续跑】此消息由 lifecycle 插件自动注入，不是用户消息。';
  // 注入重启前最后一条用户消息内容（参考 dsh-schedule 的 framing：JSON 转义，防格式污染/提示词注入）
  const lastMsg = pending.last_user_message
    ? `\n【上次消息内容】（重启前会话记录，供接续任务参考）\nlast_user_message_json: ${JSON.stringify(pending.last_user_message)}`
    : '';
  if (result?.status === 'rolled_back') {
    const stopHint = pending.attempt >= 2
      ? '这是同一任务的第 2 次失败，已回滚且【不再允许自动重启重试】。请人工介入或仔细修复后再试。'
      : '请用 git diff 复盘失败分支，修复后可再次 self_restart。';
    return `${head}${lastMsg}
你上次因「${pending.reason}」的修改导致启动失败，已自动回滚到 ${pending.base_branch}。
失败分支 ${result.failed_branch ?? '(无)'} 已保留，崩溃日志：${result.log_path ?? '(无)'}。
${stopHint}`;
  }
  if (result?.status === 'dead') {
    return `${head}${lastMsg}
上次修改导致启动失败，且回滚后也未能启动（status=dead）。服务可能处于人工恢复状态。
失败分支 ${result.failed_branch ?? '(无)'}，日志：${result.log_path ?? '(无)'}。请只做诊断，不要 self_restart。`;
  }
  return `${head}${lastMsg}
重启成功。你之前因「${pending.reason}」重启，检查点分支：${pending.checkpoint_branch ?? '(无代码改动)'}。
请继续执行验证任务：${pending.resume_task || '(无，纯维护重启，无需续跑)'}
验证通过后调用 self_finalize(action=merge) 合并回 ${pending.base_branch}；
验证失败则修复后再次 self_restart，或 self_finalize(action=rollback) 放弃修改。`;
}

export default class LifecyclePlugin extends Service {
  static inject = ['tools', 'agents', 'systemPrompt', 'webServer'];
  static Config = z.object({
    repoRoot: z.string(),
    agentDhRoot: z.string(),
    profileDir: z.string(),
    startScript: z.string().default(''),  // '' = 缺省 profileDir/start.sh（保持历史行为）
    port: z.number().default(13080),
    agentId: z.string().default('investor'),
    maxRestartsPerHour: z.number().default(10),
    agentOS: z.object({
      baseURL: z.string().default('http://localhost:8080'),  // 窗口注册表落 Agent OS（核心层）
    }).default({} as any),
    wakeToken: z.string().default(''),  // v2 → dh /wake 鉴权 token（空=不校验）
    // 代执行窗口组成（无在线窗口时 spawn 的代理 agent，2026-09-05 起）
    // agentPreset：显式 preset id；''（缺省）自动继承（在线 investor 同款 → 框架 defaultId）
    // provider/model：默认与 agent-loop agents[0]（investor）定义一致
    spawnAgent: z.object({
      agentPreset: z.string().default(''),  // schemastery 无 .optional()，'' = 未显式指定（自动继承）
      provider: z.string().default('deepseek-official'),
      model: z.string().default('deepseek-v4-flash'),
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
    // 2026-09（REQ-370b24）：boot 时刻确定性修复——滞留 agent-self 自动回干线、陈旧锁清理。
    // 语义见 boot-recovery.ts 不变量 I1-I5，审计落 boot-recovery-audit.jsonl；异常吞掉不阻断 boot。
    this.runBootRecovery();
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
    this.setupStrandedWipWatchdog(); // 改动4（2026-09-06, w-856b64ef）：滞留 wip 启动提醒，防静默链式滞留
    this.setupOsReminderPoller();  // OS 提醒体系：60s 轮询信箱并投递（2026-08-25，dsh-schedule 会话级提醒 fork 即死的替代）
    // 2026-09-04 迁移：Agent OS 定时任务改 webhook 驱动（webhook_url → POST /agent-os-trigger）。
    // setupNativeScheduler 退役——原来 DH 轮询采纳 payload.executor='dsh-native' 任务直投，
    // 与 Agent OS 侧 /bin/true 失败执行形成双轨；现在 Agent OS 每任务设 webhook_url，
    // 由本进程接收投递（14 任务 executor 已从 'dsh-native' 摘除，native scheduler 自然空转不再采纳）。
    this.setupWakeWebhook();       // v2 → dh /wake 唤醒桥（2026-09-02 死链修复，路 2 自写路由）
    this.setupAgentOsTrigger();    // Agent OS → dh 定时任务 webhook 驱动（2026-09-04）
    // Dashboard 路由现在由 @pi-investment/dashboard-execution 页面插件自己注册（2026-09-03，纯页面插件零工具）
  }

  // ===== v2 → dh /wake 唤醒桥（2026-09-02 死链修复，路 2 自写路由）=====
  // 断链：v2 AgentNotificationService POST {AGENT_API_URL}/wake，2026-09-01 起
  // AGENT_API_URL 指 dh 13080，但 dh 侧无 /wake 路由 → 404（watch 唤醒/定时提醒静默丢失）。
  // 修复：在 webServer 注册 exact /wake（wake-webhook.ts HTTP 面）→ deliverWake 投递
  // （复用 deliverReminder 三态：①在线 followup ②离线建窗代执行 ③OS 留痕）。
  private setupWakeWebhook(): void {
    registerWakeWebhook(this.ctx, {
      token: (this.cfg as any).wakeToken,
      deliver: async (event, data, timestamp) => {
        await this.deliverWake(event, data, timestamp);
      },
    });
  }

  /** 把 v2 唤醒事件投递给主 investor 窗口（或代执行窗口），并 OS 留痕 */
  private async deliverWake(event: string, data: unknown, timestamp?: string): Promise<void> {
    const firedAt = timestamp ?? new Date().toISOString();
    const prompt = `【v2 事件·${event}】由 quantsys-v2 后端唤醒推送（不是定时任务，是事件驱动）。
事件数据（JSON）：
v2_event_json: ${JSON.stringify(data)}

处理要求：理解事件内容并采取相应动作（如 watch 触发的 AI 分析版=分析该股信号并组织飞书通知；daily_report=做当日复盘；agent_reminder=执行对应提醒任务）。遵守交易宪法；完成后把结论写入 memory（namespace=decision）。`;
    await this.deliverReminder(`v2:${event}`, `wake-${event}`, prompt, undefined, firedAt);
  }

  // ===== Agent OS → dh 定时任务 webhook 驱动（2026-09-04，替代 native scheduler 直投）=====
  // 触发链路：Agent OS cron → POST {webhook_url}/agent-os-trigger（WP-15 契约）
  //          → deliverAgentOsTask → deliverReminder（①在线 followup ②离线建窗代执行 ③OS 留痕）。
  // 任务 DB 中 14 个 dsh-native 任务已设 webhook_url=http://127.0.0.1:13080/agent-os-trigger，
  // payload.executor 已从 'dsh-native' 摘除 → NativeReminderScheduler（下方保留定义作回退参考）
  // 不再采纳任何任务（filter executor==='dsh-native' 永不命中），双轨僵尸消除。
  private setupAgentOsTrigger(): void {
    registerAgentOsTrigger(this.ctx, {
      deliver: async (job) => {
        // prompt 为空的任务无法驱动 agent，直接跳过投递（记日志不阻塞 Agent OS 2xx）
        if (!job.prompt || job.prompt.trim() === '') {
          this.ctx.logger.warn(`[agent-os-trigger] job ${job.jobName} has no prompt, skip delivery`);
          return;
        }
        const taskId = job.jobId ?? `aos-${job.jobName}`;
        const firedAt = job.triggerTime ?? new Date().toISOString();
        await this.deliverReminder(job.jobName, taskId, job.prompt, job.window, firedAt);
      },
    });
  }

  // ===== DSH 原生提醒调度器（2026-09-01，2026-09-04 起退役：webhook 驱动替代）=====
  // 保留定义供回退/参考——不再在 constructor 调用。若需恢复：把 Agent OS 任务
  // payload.executor 改回 'dsh-native' 并在此 setupAgentOsTrigger 旁补 setupNativeScheduler() 即可。
  // ===== DSH 原生提醒调度器（2026-09-01）=====
  // 正规化目标：替代「Agent OS cron → os-remind-bridge.sh → OS 信箱 → 轮询」链路。
  // 任务注册表仍在 Agent OS（scheduler_manage 管理面不变），以 payload.executor='dsh-native'
  // 标记由本进程调度执行；cron 解析/触发/防重/misfire 补偿由 NativeReminderScheduler 负责。
  private nativeScheduler: NativeReminderScheduler | null = null;

  private setupNativeScheduler(): void {
    this.nativeScheduler = new NativeReminderScheduler({
      baseURL: (this.cfg as any).agentOS?.baseURL || 'http://localhost:8080',
      state: this.state,
      deliver: async (task: NativeTask, firedAt: Date) => {
        await this.deliverReminder(task.name, task.id, task.prompt, task.window, firedAt.toISOString());
      },
    });
    this.nativeScheduler.start();
    this.ctx.on('dispose' as any, () => {
      this.nativeScheduler?.stop();
      this.nativeScheduler = null;
    });
  }

  /**
   * 统一提醒投递（信箱轮询与原生调度共用）：
   * ① 目标窗口在线 → followup 直投
   * ② 不在线 → 创建新窗口代执行（用户决策：任务必须被执行，不等待上线）
   * ③ 执行留痕写 OS memory（office:reminder:exec，含完整 prompt 可溯）
   */
  /**
   * 无在线窗口时的代执行窗口配置（2026-09-05 修复：原实现硬编码 provider/model
   * 且不带 preset → 新窗口落在空 global 层，无系统提示词/技能目录/工具装载）。
   * preset（模式）继承顺序：cfg.spawnAgent.agentPreset 显式 → 在线 investor 同款
   * composedPreset → 框架 agentPresets.defaultId（与新建根 agent 同源）。
   * provider/model：cfg.spawnAgent 配置，默认与 agent-loop agents[0](investor) 一致。
   */
  private resolveSpawnProfile(): { meta: Record<string, unknown>; agentOptions: { provider: string; model: string }; presetId: string | undefined } {
    const spawn = (this.cfg as any).spawnAgent ?? {};
    const agentOptions = {
      provider: (spawn.provider as string) ?? 'deepseek-official',
      model: (spawn.model as string) ?? 'deepseek-v4-flash',
    };
    let presetId: string | undefined = spawn.agentPreset as string | undefined;
    if (!presetId) {
      try {
        const roots: any[] = this.ctx.agents.roots();
        const online = roots.find((a) => String(a.id).startsWith(this.cfg.agentId)) ?? roots[0];
        presetId = online?.ctx?.get?.('agentPresets')?.composedPreset?.(online.ctx)
          ?? (this.ctx as any).get?.('agentPresets')?.defaultId;
      } catch { /* 框架缺 agentPresets 服务时保持无 preset（原行为） */ }
    }
    return { meta: presetId ? { agentPreset: presetId } : {}, agentOptions, presetId };
  }

  /**
   * 创建代执行窗口（任务必须被执行，不等待上线）。
   * 返回 {session_id, window}；失败返回 null（不吞内部细节，由调用方决定重试语义）。
   */
  private async spawnProxyWindow(taskName: string, prompt: string, targetWindow: string | undefined): Promise<{ session_id: string; window: string } | null> {
    try {
      const sessionId = `session-${crypto.randomUUID()}`;
      const { meta, agentOptions, presetId } = this.resolveSpawnProfile();
      await (this.ctx as any).agents.create({
        sessionId,
        meta: Object.keys(meta).length ? meta : undefined,
        agentOptions,
        // preset 的 join 发生在 agent 工厂 setup 期（光传 meta.agentPreset 只留痕不装载）；
        // 根级新窗口用 mount()（参照 web 建根 agent / dsh-agent-presets AgentPresets.mount）。
        setup: async (agentCtx: any) => {
          try {
            const presets = agentCtx?.get?.('agentPresets');
            if (presets?.mount && presetId) await presets.mount(agentCtx, presetId);
          } catch (err: any) {
            this.ctx.logger.warn(`lifecycle: mount preset ${String(presetId)} for proxy window failed: ${err?.message ?? err}（窗口仍按空层创建）`);
          }
        },
      });
      const newWindow = this.windowCode(sessionId);
      const newAgent: any = (this.ctx as any).agents.get(sessionId);
      newAgent?.followup?.(createUserMessage({
        content: [{ type: 'text', text: `【OS 提醒·代执行】目标窗口 ${targetWindow ?? '未知'} 不在线，由你（新窗口 ${newWindow}）代为执行定时任务「${taskName}」：\n\n${prompt}\n\n要求：遵守交易宪法（提示词 constitution 段）；完成后把结论写入 memory（namespace=decision）并 window_update 标记 done。` }],
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
        task: `代执行提醒 ${taskName}`,
      });
      return { session_id: sessionId, window: newWindow };
    } catch (err: any) {
      this.ctx.logger.warn(`lifecycle: spawn proxy window failed: ${err?.message ?? err}`);
      return null;
    }
  }

  private async deliverReminder(taskName: string, taskId: string, prompt: string, window: string | undefined, firedAt: string): Promise<void> {
    // ① 找在线目标窗口
    const roots: any[] = this.ctx.agents.roots();
    const online = roots.find((a) => String(a.id).startsWith(this.cfg.agentId)) ?? roots[0];
    let executor: any = null;

    if (online?.followup) {
      try {
        online.followup(createUserMessage({
          content: [{ type: 'text', text: `【OS 提醒】${taskName}\n\n${prompt}\n\n（来源：定时任务 ${taskId}，触发于 ${firedAt}）` }],
          source: { kind: 'plugin', plugin: 'lifecycle' },
        }));
        executor = { mode: 'direct', session_id: String(online.id) };
      } catch { /* 投递失败走创建窗口 */ }
    }

    // ② 没有在线窗口 → 创建新窗口代为执行（任务必须被执行；spawn 失败向上抛，Agent OS 侧会重试）
    if (!executor) {
      const spawned = await this.spawnProxyWindow(taskName, prompt, window);
      if (!spawned) throw new Error(`spawn proxy window failed for ${taskName}`);
      executor = { mode: 'spawned', session_id: spawned.session_id, window: spawned.window };
    }

    // ③ 执行留痕（含完整提示词，可溯）
    const rootsEarly: any[] = this.ctx.agents.roots();
    const onlineRoot = rootsEarly.find((a) => String(a.id).startsWith(this.cfg.agentId)) ?? rootsEarly[0];
    const myWindow = onlineRoot ? this.windowCode(String(onlineRoot.id)) : this.windowCode(this.identity.id);
    await this.osWrite('memory_write', {
      title: `reminder ${taskName} delivered`,
      content: JSON.stringify({
        task: taskName,
        task_id: taskId,
        prompt,
        window,
        fired_at: firedAt,
        delivered: true,
        delivered_at: new Date().toISOString(),
        executor,
      }),
      namespace: 'data',
      tags: ['office:delivered', 'office:reminder:exec', `office:reminder:${myWindow}`],
    });
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
            const spawned = await this.spawnProxyWindow(p.task ?? '', p.prompt ?? '', p.window);
            if (!spawned) continue;  // 创建失败留下轮重试，信箱记录仍在
            executor = { mode: 'spawned', session_id: spawned.session_id, window: spawned.window };
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

  /**
   * 改动1/改动2 共用（w-856b64ef）：溯源 agent-self/* wip 的"链根干线"。
   * 优先级：① pending(.done) 记录里非 agent-self 前缀的 base_branch（改动1后 restart 恒写干线）；
   *          ② git 溯源（resolveChainBase 沿 first-parent 找链根）；③ 主干候选 main/master 兜底。
   * 溯源失败抛错（宁可不重启/不收尾，也不链式滞留）。
   */
  private resolveTrunkBase(wipBranch: string): string {
    // ① 状态记录：restart 时写入的 base_branch 若已是干线则直接用（新代码恒为干线；旧记录可能链式）
    for (const p of [this.state.readPending(), this.state.readPendingDone()]) {
      const b = p?.base_branch ?? null;
      if (b && !b.startsWith('agent-self/') && this.repo.branchExists(b)) return b;
    }
    // ② git 溯源链根
    const gitBase = this.repo.resolveChainBase(wipBranch);
    if (gitBase && this.repo.branchExists(gitBase)) return gitBase;
    // ③ 主干兜底
    for (const trunk of ['main', 'master']) {
      if (this.repo.branchExists(trunk)) return trunk;
    }
    throw new Error(`无法溯源 ${wipBranch} 的链根干线（无状态记录、git 溯源失败且无 main/master），请人工 checkout 干线后处理`);
  }

  /**
   * 调度重启（2026-09, REQ-370b24 重构为纯模块 planAndScheduleRestart）：
   * 限流 → 互斥锁 → wip 检查点 → pending 持久化 → spawn 包内重启器（detached）。
   * 本方法仅剩：组装依赖 + 调用 planner + 打日志；行为与原实现逐行一致（等价迁移）。
   */
  private async scheduleRestart(reason: string, preserveContext: boolean, originAgentId?: string | null): Promise<void> {
    const deps: RestartPlannerDeps = {
      repo: this.repo,
      state: this.state,
      resolveBase: (b) => this.resolveTrunkBase(b),
      resolveRestarterPath: () => this.resolveRestarterPath(),
      profileDir: this.cfg.profileDir,
      // '' → 落到 planner 的缺省 profileDir/start.sh；显式配置即指向仓库内启动器
      startScript: (this.cfg as any).startScript || join(this.cfg.profileDir, 'start.sh'),
      agentDhRoot: this.cfg.agentDhRoot,
      repoRoot: this.cfg.repoRoot,
      port: this.cfg.port,
      processPid: process.pid,
      captureLastUserMessage: (id) => this.captureLastUserMessage(id),
      spawnRestarter: (cmd, args, opts) => {
        const child = spawn(cmd, args, opts);
        child.unref();
      },
    };
    const plan = planAndScheduleRestart(deps, {
      reason,
      preserveContext,
      originAgentId: originAgentId ?? null,
      maxRestartsPerHour: this.cfg.maxRestartsPerHour,
      now: Date.now(),
    });
    this.ctx.logger.info(
      `lifecycle: Restart scheduled: ${plan.reason} → checkpoint=${plan.checkpointBranch ?? '(无改动)'} log=${plan.logPath} restarter=${plan.restarter}`,
    );
  }

  /**
   * 改动4（w-856b64ef）：滞留 wip 看门狗。启动时若 HEAD 停在 agent-self/* 且无任何 pending 记录
   * （restarter 成功路径未把 HEAD 交还干线 + 收尾未执行就再次启动/人工重启 → wip 滞留无人管），
   * 向主 agent 注入提示：请先 self_finalize 收尾，勿在 wip 上再造链。只提示不代执行。
   */
  private runBootRecovery(): void {
    try {
      const stateDir = join(this.cfg.profileDir, 'state');
      const report = onBoot({
        repo: this.repo,
        state: this.state,
        readLockTs: () => {
          try { return Number(readFileSync(join(stateDir, 'restarting.lock'), 'utf8')); } catch { return null; }
        },
        releaseLock: () => this.state.releaseLock(),
        resolveBase: () =>
          this.repo.branchExists('main') ? 'main' : this.repo.branchExists('master') ? 'master' : null,
        now: Date.now(),
        auditPath: join(stateDir, 'boot-recovery-audit.jsonl'),
      });
      if (report.actions.length > 0 || report.issues.length > 0) {
        this.ctx.logger.info(
          `lifecycle: boot-recovery ${JSON.stringify({ actions: report.actions, issues: report.issues })}`,
        );
      }
      // P1（2026-09-10）：救援归档必须主动播报——I3 已把 HEAD 切回干线，看门狗会短路，
      // 不主动说就没人知道"工作区里消失的文件被归档到了哪个分支"（这正是本 bug 静默的一半）。
      const rescues = report.actions.filter(
        (a): a is { kind: 'rescueWip'; from: string; ref: string } => a.kind === 'rescueWip',
      );
      if (rescues.length > 0) this.announceWipRescue(rescues);
    } catch (e) {
      // fail-safe：修复逻辑任何失败都不得阻断 boot（滞留态下次 boot 仍会再试 + 看门狗兜底）
      this.ctx.logger.warn(`lifecycle: boot-recovery skipped: ${String(e)}`);
    }
  }

  /**
   * 播报 boot 救援归档（P1，2026-09-10）：把"文件从磁盘消失了"变成"文件在某具名分支，可一键取回"。
   * 投递模式与 stranded watchdog 一致：优先在线根 agent，未就绪则等 agent/created（30 分钟窗口）。
   */
  private announceWipRescue(rescues: Array<{ from: string; ref: string }>): void {
    const text = [
      '【lifecycle boot 救援】上次进程退出时 HEAD 滞留在 wip 分支且无续跑记录，已自动切回干线。',
      '为避免这些分支上的独有内容随 checkout 从磁盘消失，已先归档为具名分支：',
      ...rescues.map((r) => `- ${r.from} → ${r.ref}`),
      '取回单个文件到工作区（保持未提交改动形态）：git checkout <归档分支> -- <路径>',
      '注意：归档分支内容尚未并入干线，是否合并由内容 owner 判断，不要盲目 merge。',
    ].join('\n');
    const deliver = (agent: Agent | undefined): boolean => {
      if (!agent) return false;
      try {
        agent.followup(createUserMessage({
          content: [{ type: 'text', text }],
          source: { kind: 'plugin', plugin: 'lifecycle' },
        } as any));
        this.ctx.logger.info(`lifecycle: wip-rescue notice delivered to ${String(agent.id)}`);
        return true;
      } catch (e) {
        this.ctx.logger.warn(`lifecycle: wip-rescue notice failed: ${String(e)}`);
        return false;
      }
    };
    try {
      const roots: Agent[] = this.ctx.agents.roots();
      const target = roots.find((a) => String(a.id).startsWith(this.cfg.agentId)) ?? roots[0];
      if (deliver(target)) return;
      const dispose = this.ctx.on('agent/created', ({ agent }) => {
        if (String(agent.id).startsWith(this.cfg.agentId) && deliver(agent)) dispose();
      });
      setTimeout(() => dispose(), 30 * 60_000);
    } catch (e) {
      this.ctx.logger.warn(`lifecycle: wip-rescue notice skipped: ${String(e)}`);
    }
  }

  private setupStrandedWipWatchdog(): void {
    try {
      const branch = this.repo.currentBranch();
      if (!branch.startsWith('agent-self/')) return; // 干线启动，无滞留
      if (this.state.readPending() || this.state.readPendingDone()) return; // 有续跑/收尾记录，setupResume 处理
      const text = [
        '【lifecycle 收尾提醒】当前 HEAD 停留在未收尾的 wip 分支 ' + branch + '，且无 pending 收尾记录。',
        '这表明上次 self_restart 已成功但收尾（self_finalize）未执行，改动仍留在 wip 上未合回干线。',
        '请处理：验证通过 → 调 self_finalize(action=merge) 合回干线；需放弃 → self_finalize(action=rollback)。',
        '请勿在 wip 分支上继续重启或重复收尾，以免造成链式滞留。',
      ].join('\n');
      const deliver = (agent: Agent | undefined): boolean => {
        if (!agent) return false;
        try {
          agent.followup(createUserMessage({
            content: [{ type: 'text', text }],
            source: { kind: 'plugin', plugin: 'lifecycle' },
          }));
        } catch (e) {
          this.ctx.logger.warn(`lifecycle: watchdog followup failed: ${String(e)}`);
          return false;
        }
        this.ctx.logger.info(`lifecycle: stranded-wip watchdog delivered to ${String(agent.id)} on ${branch}`);
        return true;
      };
      const roots: Agent[] = this.ctx.agents.roots();
      const target = roots.find((a) => String(a.id).startsWith(this.cfg.agentId)) ?? roots[0];
      if (deliver(target)) return;
      // 主 agent 未就绪：等 agent/created
      const dispose = this.ctx.on('agent/created', ({ agent }) => {
        if (String(agent.id).startsWith(this.cfg.agentId) && deliver(agent)) dispose();
      });
      setTimeout(() => dispose(), 30 * 60_000);
    } catch (e) {
      this.ctx.logger.warn(`lifecycle: stranded-wip watchdog skipped: ${String(e)}`);
    }
  }

  // ===== 工具回调方法 =====

  /**
   * 调度重启：限流 → 互斥锁 → wip 检查点 → pending 持久化 → spawn 包内重启器（detached）。
   * 重启器独立于本进程与外部脚本，负责 kill 旧进程、start.sh 拉起、健康检查、失败回滚。
   */


  /** 捕获发起会话的最后一条用户消息文本，重启后随续跑消息注入（参考 dsh-schedule 从 session.events 读取） */
  private captureLastUserMessage(agentId: string | null | undefined): string | null {
    if (!agentId) return null;
    try {
      const agent = this.ctx.agents.get(agentId as any);
      const events: any[] = (agent as any)?.session?.events ?? [];
      for (let i = events.length - 1; i >= 0; i--) {
        const ev = events[i];
        if (ev?.type !== 'user/message') continue;
        const content: any[] = ev?.data?.content;
        if (!Array.isArray(content)) return null;
        const text = content
          .filter((b: any) => b?.type === 'text' && typeof b.text === 'string')
          .map((b: any) => (b.text as string).trim())
          // 过滤 dsh 注入的系统块（system-reminder 等以 <xxx> 开头的文本），只保留用户真实消息
          .filter((t: string) => t.length > 0 && !/^<[a-z-]+>/i.test(t))
          .join('\n')
          .trim();
        return text.length > 0 ? text.slice(0, 2000) : null;
      }
    } catch { /* 取不到就不注入 */ }
    return null;
  }

  /** 定位包内重启器：优先 dist 构建产物（tsdown 多入口输出在 dist/restarter/restarter.mjs），其次源码（开发模式 tsx 直跑） */
  private resolveRestarterPath(): string {
    const distCandidates = [
      new URL('./restarter/restarter.mjs', import.meta.url), // tsdown 多入口实际输出
      new URL('./restarter.mjs', import.meta.url),           // 扁平化输出（兼容）
    ];
    for (const u of distCandidates) {
      try {
        const p = fileURLToPath(u);
        if (existsSync(p)) return p;
      } catch { /* try next */ }
    }
    const src = join(this.cfg.agentDhRoot, 'packages', 'lifecycle', 'src', 'restarter', 'restarter.ts');
    if (existsSync(src)) return src;
    throw new Error('lifecycle 重启器产物缺失：请先运行 pnpm --filter @pi-investment/lifecycle build');
  }

  /**
   * 调度终止/收尾（RFC 002 自修复闭环收尾端）。
   * action=merge：验证通过 → 把 self_restart 的 wip 检查点分支快进合并回基线分支，
   *   更新 last-known-good 为该合并后 HEAD，清理 pending 与 wip 分支。基线分支继续运行（不退出进程）。
   * action=rollback：验证失败 → 放弃 wip 检查点分支改动，回基线分支并硬重置到 last-known-good，
   *   清理 pending 与 wip 分支。基线分支继续运行（不退出进程）。
   * action=exit：退出前显式收尾（2026-09-10 修复 P0：wip 独有内容归档到 wip/rescued-* + 取回工作区
   *   → 回干线 → 删除已归档的检查点分支），随后清理 pending 并优雅退出。
   *   原实现"清 pending 但不回干线"与 boot-recovery I3 判定互相矛盾：设计性退出会被下次启动
   *   误判为崩溃滞留，静默切回干线，并把只存在于 wip 上的文件从磁盘抹掉且无人告知。
   *   详见 exit-finalize.ts。
   * 无 pending 检查点分支（如直接提交在基线的场景）时，merge/rollback 自动降级为仅确认/保存状态。
   */
  private async scheduleFinalize(reason: string, action: 'merge' | 'rollback' | 'exit', saveState: boolean): Promise<{ action: string; merged_hash?: string; note?: string }> {
    this.ctx.logger('lifecycle').info(`Finalize scheduled: ${reason}, action=${action}, saveState=${saveState}`);

    if (saveState) {
      // 保存状态到 Agent OS
      await this.osWrite('lifecycle:finalize', { reason, action, timestamp: new Date().toISOString() });
    }

    // resume 投递成功后 markPendingDone() 会把 pending-resume.json rename 为 .done.json，
    // 若只 readPending() 会拿到 null → checkpoint 丢失 → merge/rollback 静默降级不执行 git（2026-09-04 实测）。
    // 修复：pending 已被消费（存在 .done.json）时回退读取，finalize 仍能拿到检查点分支。
    const pending = this.state.readPending() ?? this.state.readPendingDone();
    const checkpoint = pending?.checkpoint_branch ?? null;
    // 改动2（w-856b64ef）：base 溯源兜底——pending.base_branch 若被旧版链式写入成 agent-self/*，
    // 不得作为收尾基线（wip 合进 wip 会永不入干线），须溯源到链根干线再执行 merge/rollback
    const rawBase = pending?.base_branch ?? this.repo.currentBranch();
    const base = rawBase.startsWith('agent-self/')
      ? this.resolveTrunkBase(checkpoint ?? rawBase)
      : rawBase;

    if (action === 'merge' && checkpoint) {
      // 验证通过：wip 检查点 → 策略化合并回干线（改动2，w-856b64ef：mergeFfOnly 太脆重构为 finalizeMerge）
      try {
        this.ctx.logger('lifecycle').info(`Finalize merge: ${checkpoint} → ${base}`);
        this.repo.checkout(base);
        const res = this.repo.finalizeMerge(base, checkpoint, `merge(wip ${checkpoint}): lifecycle 收尾`);
        // outcome 驱动删除语义：already-cherried=等价并入但非祖先（hash 不同）→ 须 -D；其余已合入/已并入 → -d
        if (this.repo.branchExists(checkpoint)) {
          this.repo.deleteBranch(checkpoint, res.outcome === 'already-cherried');
        }
        // 改动3（w-856b64ef）：整链清理——同一 agent-self 前缀下内容已并入 base 的历史遗留分支一并收掉
        // （旧版多次 wip-on-wip 重启可能残留多条链分支；cleanupWipChain 绝不删内容未并入的分支）
        const cleaned = this.repo.cleanupWipChain('agent-self', base);
        const hash = res.merged_hash;
        this.state.writeLastKnownGood(hash);
        this.ctx.logger('lifecycle').info(
          `Finalize merge done: outcome=${res.outcome} ${base} @ ${hash}` +
          (cleaned.length ? `；链清理=${cleaned.join(',')}` : ''),
        );
        // 清理 pending（merge 成功后无未决重启）
        this.state.clearPending();
        this.state.clearAttempt();
        return { action: 'merge', merged_hash: hash };
      } catch (e: any) {
        this.ctx.logger('lifecycle').error(`Finalize merge failed: ${e?.message ?? e}`);
        throw new Error(`merge 失败：${e?.message ?? e}（wip=${checkpoint} 保留未删，请人工处理）`);
      }
    }

    if (action === 'rollback' && checkpoint) {
      // 验证失败：放弃 wip 改动，回基线 + 硬重置到 last-known-good
      try {
        const lkg = this.state.readLastKnownGood() ?? pending?.last_known_good;
        this.ctx.logger('lifecycle').info(`Finalize rollback: 放弃 ${checkpoint}，回 ${base} @ ${lkg ?? 'HEAD'}`);
        this.repo.checkout(base);
        if (lkg) this.repo.resetHard(lkg);
        this.repo.deleteBranch(checkpoint, true); // wip 未合并即删除（-D），rollback 语义
        this.state.clearPending();
        this.state.clearAttempt();
        return { action: 'rollback' };
      } catch (e: any) {
        this.ctx.logger('lifecycle').error(`Finalize rollback failed: ${e?.message ?? e}`);
        throw new Error(`rollback 失败：${e?.message ?? e}（wip=${checkpoint} 保留未删，请人工处理）`);
      }
    }

    // 无 checkpoint（或 action=exit）：无 git 收尾操作，仅清理 pending 状态
    if (pending) {
      this.state.clearPending();
      this.state.clearAttempt();
    }

    if (action !== 'exit') {
      // merge/rollback 但无 wip 检查点（改动已直接在基线）→ 视为纯确认，不退出进程
      this.ctx.logger('lifecycle').info(`Finalize ${action}: 无 wip 检查点分支，仅确认/清理（基线 ${base}）`);
      return { action };
    }

    // exit：先做退出前收尾（P0 修复，2026-09-10），再清理 pending 状态并优雅退出
    const exitRes = exitFinalize(this.repo, { checkpoint, base });
    const exitNote = describeExitFinalize(exitRes);
    if (exitNote) this.ctx.logger('lifecycle').info(`Finalize exit pre-cleanup: ${exitNote}`);
    if (saveState && (exitRes.archived || exitRes.error)) {
      // 归档/失败是"别人工作是否会从磁盘消失"的关键动作，必须留审计（写失败不阻塞退出）
      try {
        await this.osWrite('lifecycle:finalize', {
          reason, action, exitFinalize: exitRes, timestamp: new Date().toISOString(),
        });
      } catch { /* 忽略 */ }
    }
    this.state.clearPending();
    this.state.clearPendingDone();
    this.state.clearAttempt();
    setTimeout(() => process.exit(0), 1000);
    return { action: 'exit', note: exitNote || undefined };
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
    ctx.tools.register(defineTool(restartTool.toDSHToolDefinition()));

    // 2. 终止工具（重构为 BaseTool）
    const finalizeTool = new SelfFinalizeTool(
      this.scheduleFinalize.bind(this)
    );
    ctx.tools.register(defineTool(finalizeTool.toDSHToolDefinition()));

    // 3. 状态查询工具（重构为 BaseTool）
    const statusTool = new SelfStatusTool(
      this.getStatus.bind(this)
    );
    ctx.tools.register(defineTool(statusTool.toDSHToolDefinition()));

    // RFC 009: 注册公告板生命周期管理工具
    // RFC 014：公告板切换到独立存储 API（脱离 memory 复用）
    registerBoardUpdate(this.ctx, this.aos.board, this.cfg.agentId);
    registerBoardRead(this.ctx, this.aos.board, this.cfg.agentId);
    registerBoardPost(this.ctx, this.aos.board, this.cfg.agentId);
  }
}
