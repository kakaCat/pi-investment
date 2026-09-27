/**
 * AgentTeamsPort 的唯一实现（FR-11 路线 A）：直接消费已加载的 `ctx.agentTeams`
 * （@deepseek-ai/dsh-experimental-agent-team 的 TeamService），不经过模型侧工具。
 *
 * 合同要点（对齐 TeamService 的真实类型，2026-09-27 读 lib/types/index.d.ts + types.d.ts 核实）：
 *  - 每个方法都要 `caller: Agent`（服务的 authority credential，live 句柄）——端口用 unknown 透传；
 *  - `spawnTeammate` 的 prompt 是 **ContentBlock[]**，不是裸字符串；provider 缺省 'spawn'（fresh）；
 *  - `spawnTeammate` / `sendMessage` 的 signal 是**必填**，缺省给一个永不中止的 signal；
 *  - 服务抛错一律原样上抛（调用方决定降级），不静默吞。
 *
 * @module dsh-pmboard/adapters/AgentTeamsAdapter
 */
import type {
  AgentTeamsPort,
  SpawnWorkerInput,
  TeamMemberViewLike,
  TeamTaskCreateInput,
  TeamTaskUpdateInput,
  TeamTaskViewLike,
} from '../application/ports.js'

/** 服务最小结构（不 import `@deepseek-ai/dsh-experimental-agent-team`，保持 adapter 只桥接形状）。 */
export interface TeamServiceLike {
  spawnTeammate(caller: unknown, request: unknown): Promise<{ member: TeamMemberViewLike }>
  listMembers(caller: unknown): TeamMemberViewLike[]
  createTask(caller: unknown, request: unknown): Promise<TeamTaskViewLike>
  listTasks(caller: unknown): TeamTaskViewLike[]
  getTask(caller: unknown, id: string): TeamTaskViewLike
  updateTask(caller: unknown, request: unknown): Promise<TeamTaskViewLike>
  waitForChange(caller: unknown, timeoutMs: number, signal: AbortSignal): Promise<{ timedOut: boolean }>
  interrupt(caller: unknown, targetName: string): { previousStatus: string }
  sendMessage(caller: unknown, request: unknown): Promise<{ messageId: unknown; status: unknown }>
}

/** 永不中止的 signal（服务把 signal 声明为必填，而端口侧是可选的）。 */
const NEVER_ABORT = new AbortController().signal

function unavailable(): Error {
  return Object.assign(new Error('agentTeams service 不可用（未装配或未启用）'), { code: 'DSH_TEAMS_UNAVAILABLE' })
}

export class AgentTeamsAdapter implements AgentTeamsPort {
  /** `service` 以 thunk 注入：服务工作区尚未就绪时返回 undefined → available()=false。 */
  constructor(private readonly service: () => TeamServiceLike | undefined) {}

  private svc(): TeamServiceLike {
    const s = this.service()
    if (s === undefined) throw unavailable()
    return s
  }

  available(): boolean {
    return this.service() !== undefined
  }

  async spawnWorker(caller: unknown, input: SpawnWorkerInput): Promise<TeamMemberViewLike> {
    const out = await this.svc().spawnTeammate(caller, {
      name: input.name,
      description: input.description,
      prompt: [{ type: 'text', text: input.prompt }],
      context: input.context ?? 'fresh',
      provider: input.context === 'fork' ? 'fork' : 'spawn',
      signal: input.signal ?? NEVER_ABORT,
    })
    return out.member
  }

  listMembers(caller: unknown): readonly TeamMemberViewLike[] {
    return this.svc().listMembers(caller)
  }

  async createTask(caller: unknown, input: TeamTaskCreateInput): Promise<TeamTaskViewLike> {
    return this.svc().createTask(caller, {
      subject: input.subject,
      description: input.description,
      ...(input.blockedBy !== undefined ? { blockedBy: input.blockedBy } : {}),
      ...(input.writeScopes !== undefined ? { writeScopes: input.writeScopes } : {}),
    })
  }

  listTasks(caller: unknown): readonly TeamTaskViewLike[] {
    return this.svc().listTasks(caller)
  }

  getTask(caller: unknown, taskId: string): TeamTaskViewLike {
    return this.svc().getTask(caller, taskId)
  }

  async updateTask(caller: unknown, input: TeamTaskUpdateInput): Promise<TeamTaskViewLike> {
    return this.svc().updateTask(caller, {
      taskId: input.taskId,
      expectedRevision: input.expectedRevision,
      action: input.action,
      ...(input.owner !== undefined ? { owner: input.owner } : {}),
    })
  }

  async waitForChange(caller: unknown, timeoutMs: number, signal?: AbortSignal): Promise<{ timedOut: boolean }> {
    return this.svc().waitForChange(caller, timeoutMs, signal ?? NEVER_ABORT)
  }

  interrupt(caller: unknown, targetName: string): { previousStatus: string } {
    return this.svc().interrupt(caller, targetName)
  }

  async sendMessage(caller: unknown, input: { target: string; content: string }): Promise<{ messageId: string; status: string }> {
    const out = await this.svc().sendMessage(caller, {
      target: input.target,
      content: [{ type: 'text', text: input.content }],
      signal: NEVER_ABORT,   // 服务把 signal 声明为必填
    })
    return { messageId: String(out.messageId), status: String(out.status) }
  }
}
