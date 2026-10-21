import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type {
  ToolMetadata,
  ToolContext,
  ToolResponse,
  ValidationResult,
} from '@pi-investment/core-tool';
import type { QuantsysV2Client, WatchTodo } from '@pi-investment/quantsys-v2-client';
import { watchTodoPrompt, type WatchTodoParams } from './prompt';

/**
 * 本实例在 v2 待办台账里的接手方标识（owner_ref）。
 *
 * 为什么需要：claim 会把它写进 watch_todos.owner_ref（"谁在做"），也是
 * ReceiptService 判断"升级去向"的依据（owner_kind=agent 的待办升级给 agent，不打扰用户）。
 * agent-ts 复用同一工具时用 DSH_AGENT_REF=agent-ts 覆盖即可，不必改代码。
 */
export const AGENT_REF = ((): string => {
  try {
    const env = typeof process !== 'undefined' ? process.env?.DSH_AGENT_REF : undefined;
    return (env && String(env).trim()) || 'agent-dh';
  } catch {
    return 'agent-dh';
  }
})();

/** 列表投影：只回 agent 决策需要的字段（避免把整表塞进上下文） */
function project(todo: WatchTodo): Record<string, any> {
  return {
    id: todo.id,
    symbol: todo.symbol,
    level: todo.level,
    flow_state: todo.flow_state,
    action_kind: todo.action_kind ?? null,
    rule_id: todo.rule_id ?? null,
    account: todo.account ?? null,
    owner_kind: todo.owner_kind ?? null,
    owner_ref: todo.owner_ref ?? null,
    due_at: todo.due_at ?? null,
    escalate_count: todo.escalate_count ?? 0,
    claimed_at: todo.claimed_at ?? null,
    created_at: todo.created_at ?? null,
  };
}

export class WatchTodoTool extends BaseTool<WatchTodoParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'watch_todo',
    category: 'intelligence',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = watchTodoPrompt;

  constructor(private qv2Client: QuantsysV2Client) {
    super();
  }

  protected validate(params: WatchTodoParams): ValidationResult {
    const { action, todo_id, terminal, next_condition, action_kind, decision_audit_id } = params;

    if (!action || !['list', 'claim', 'close'].includes(action)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'action',
        issue: 'action 必须是 list / claim / close。示例: action=list',
        expected: ['list', 'claim', 'close'],
        received: action,
      };
    }

    if ((action === 'claim' || action === 'close') && !todo_id) {
      return {
        success: false,
        errorType: ErrorType.INPUT_EMPTY,
        field: 'todo_id',
        issue: `watch_todo ${action} 缺少 todo_id（来自 wake 载荷的 todo_id，或 list 返回的 id）`,
      };
    }

    if (action === 'close') {
      if (!terminal || !['handled', 'ignored', 'expired'].includes(terminal)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'terminal',
          issue: 'close 必须给 terminal ∈ handled|ignored|expired（handled=已处置；ignored=不动，须给 next_condition）',
          expected: ['handled', 'ignored', 'expired'],
          received: terminal,
        };
      }
      // 服务端硬约束，前端先拦一次：错误信息比 400 更可操作
      if (terminal === 'ignored' && !next_condition) {
        return {
          success: false,
          errorType: ErrorType.INPUT_EMPTY,
          field: 'next_condition',
          issue: 'terminal=ignored 必须给 next_condition：下次什么条件下才动（否则服务端 400 watch_todo_missing_next_condition）',
        };
      }
      if (action_kind && ['trade', 'rule_change'].includes(action_kind) && !decision_audit_id) {
        return {
          success: false,
          errorType: ErrorType.INPUT_EMPTY,
          field: 'decision_audit_id',
          issue:
            'L3 待办以 trade/rule_change 关闭必须带 decision_audit_id（否则服务端 400 watch_todo_missing_audit）：' +
            '先用 decision_audit 工具落审计，再把返回的 ID 传进来；判不动就用 terminal=ignored + next_condition',
        };
      }
    }

    return { success: true };
  }

  protected async execute(params: WatchTodoParams, _context: ToolContext): Promise<any> {
    if (params.action === 'list') {
      const todos = await this.qv2Client.listWatchTodos({
        level: params.level,
        flow_state: params.flow_state,
        account: params.account,
        limit: params.limit ?? 30,
      });
      const items = (todos ?? []).map(project);
      return {
        success: true,
        action: 'list',
        count: items.length,
        todos: items,
        message: items.length
          ? `未收敛待办 ${items.length} 条（最高级别 ${items[0]?.level ?? '-'}）`
          : '当前没有未收敛待办',
      };
    }

    if (params.action === 'claim') {
      const ownerRef = params.owner_ref || AGENT_REF;
      const todo = await this.qv2Client.claimWatchTodo(params.todo_id as number, ownerRef);
      return sanitizeLossless({
        success: true,
        action: 'claim',
        todo_id: params.todo_id,
        owner_ref: ownerRef,
        flow_state: todo?.flow_state ?? null,
        claimed_at: todo?.claimed_at ?? null,
        symbol: todo?.symbol ?? null,
        action_kind: todo?.action_kind ?? null,
        rule_id: todo?.rule_id ?? null,
        message: `待办 #${params.todo_id} 已认领（${ownerRef}）——处置完成后必须 close`,
      });
    }

    // close：只传有值的字段（undefined 会被服务端当缺参）
    const request: Record<string, any> = {
      terminal: params.terminal,
      action_kind: params.action_kind,
      decision_audit_id: params.decision_audit_id,
      close_reason: params.close_reason,
      next_condition: params.next_condition,
    };
    for (const key of Object.keys(request)) {
      if (request[key] === undefined) delete request[key];
    }
    const data = await this.qv2Client.closeWatchTodo(params.todo_id as number, request as any);
    const todo = data?.todo ?? {};
    return sanitizeLossless({
      success: true,
      action: 'close',
      todo_id: params.todo_id,
      terminal: todo?.terminal ?? params.terminal,
      closed_at: todo?.closed_at ?? null,
      close_reason: todo?.close_reason ?? params.close_reason ?? null,
      next_condition: todo?.next_condition ?? params.next_condition ?? null,
      receipt: data?.receipt ?? null,
      message: `待办 #${params.todo_id} 已收敛（${params.terminal}），处置结论回执已发出`,
    });
  }

  protected wrap(data: any, _context: ToolContext): ToolResponse<any> {
    return {
      success: true,
      data,
      message: data?.message,
      metadata: { action: data?.action, todo_id: data?.todo_id ?? null },
    };
  }
}
