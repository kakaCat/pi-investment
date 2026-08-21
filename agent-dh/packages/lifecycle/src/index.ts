import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { readFileSync } from 'node:fs';
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
  }

  /** 窗口编码：session-<uuid> → w-<前8位>；其他 agent id 原样返回 */
  private windowCode(agentId: string): string {
    return agentId.startsWith('session-') ? `w-${agentId.slice(8, 16)}` : agentId;
  }

  /**
   * 窗口注册表：监听 agent/created（新窗口=新会话 agent），自动登记到
   * Agent OS 记忆库（tag=system:windows）。用户在 GUI 随机开窗口，但每个窗口都可被点名调动。
   * OS 是核心（用户裁决 2026-08-21）：注册表落 OS，不落 v2。
   */
  private setupWindowRegistry(): void {
    this.ctx.on('agent/created' as any, (agent: any) => {
      this.registerWindow(agent).catch(() => { /* 注册失败不影响 agent 创建 */ });
    });
  }

  private async registerWindow(agent: any): Promise<void> {
    const sessionId = String(agent?.id ?? '');
    if (!sessionId) return;
    const window = this.windowCode(sessionId);
    await this.aos.memory.write({
      title: `window ${window} 上线`,
      content: JSON.stringify({
        window,
        session_id: sessionId,
        agent_id: this.identity.id,
        role: this.identity.name,
        task: null,
        status: 'active',
        started_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }),
      namespace: 'data',
      tags: ['system:windows', 'window', window],
    });
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

    // window_update - 更新本窗口的当前任务/状态
    ctx.tools.register(defineTool({
      name: 'window_update',
      description: '更新当前窗口在注册表中的状态：正在做什么任务、进展备注。窗口自动识别（从调用上下文取 session id）。适用于：开始新任务时自报家门，让其他窗口/用户能查到"这个窗口在干什么"。',
      parameters: {
        task: { type: 'string', description: '当前任务描述，如 "M4 仓位映射表实施"' },
        status: { type: 'string', description: '状态：active / blocked / done', enum: ['active', 'blocked', 'done'] },
        note: { type: 'string', description: '进展备注' },
      },
      output: {
        schema: { type: 'object', properties: { window: { type: 'string' }, updated: { type: 'boolean' } }, additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async (args: any, exec?: any) => {
        const sessionId = String(exec?.agent?.id ?? '');
        if (!sessionId) throw new Error('无法识别当前窗口（exec.agent 缺失）');
        const window = this.windowCode(sessionId);

        // 找本窗口最新记录，保留 started_at
        const res: any = await this.aos.memory.search({ query: window, tag: 'system:windows', top_k: 20 });
        const items: any[] = res?.memories || res?.items || [];
        let startedAt: string | null = null;
        for (const it of items) {
          try {
            const p = typeof it.content === 'string' ? JSON.parse(it.content) : it.content;
            if (p?.session_id === sessionId) {
              if (!startedAt || String(p.updated_at) > String(startedAt)) startedAt = p.started_at ?? startedAt;
            }
          } catch { /* 跳过 */ }
        }

        await this.aos.memory.write({
          title: `window ${window} ${args.status ?? 'active'}${args.task ? `：${args.task}` : ''}`,
          content: JSON.stringify({
            window,
            session_id: sessionId,
            agent_id: this.identity.id,
            role: this.identity.name,
            task: args.task ?? null,
            note: args.note ?? null,
            status: args.status ?? 'active',
            started_at: startedAt ?? new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }),
          namespace: 'data',
          tags: ['system:windows', 'window', window],
        });

        return { window, updated: true } as any;
      },
    } as any));
  }
}
