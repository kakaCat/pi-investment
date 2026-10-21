/**
 * WatchTodoTool 单测（2026-10-16）
 *
 * 可失败性（每条对应一个真实缺口）：
 *   · list/claim/close 三个动作必须真的打到 v2 新方法（此前 agent 无任何工单工具）；
 *   · claim 必须带接手方标识（owner_ref，默认本实例）——否则"谁在做"不可见；
 *   · close 必须先过前端硬约束（ignored 缺 NEXT / rule_change 缺审计 ID 直接拦下），
 *     错误信息要可操作（服务端 400 的码写进 issue，便于 agent 自我纠正）；
 *   · close 只传有值字段（undefined 会被服务端当缺参 → 400）。
 */
import { describe, it, expect, vi } from 'vitest';
import { WatchTodoTool, AGENT_REF } from '../src/tools/WatchTodoTool/WatchTodoTool';

function fakeClient(overrides: Record<string, any> = {}) {
  return {
    listWatchTodos: vi.fn().mockResolvedValue([]),
    claimWatchTodo: vi.fn().mockResolvedValue({ flow_state: 'L2', claimed_at: 'T', symbol: '300253' }),
    closeWatchTodo: vi.fn().mockResolvedValue({ todo: { terminal: 'handled', closed_at: 'T' }, receipt: { kind: 'result' } }),
    ...overrides,
  } as any;
}

const tool = (client: any) => new WatchTodoTool(client);

describe('watch_todo 参数校验', () => {
  it('action 缺失/非法 → 拦下并给示例', async () => {
    const res = await tool(fakeClient()).call({} as any);
    expect(res.success).toBe(false);
    expect((res.error as any).issue).toContain('list / claim / close');
  });

  it('claim/close 缺 todo_id → 拦下', async () => {
    const res = await tool(fakeClient()).call({ action: 'claim' } as any);
    expect(res.success).toBe(false);
    expect((res.error as any).field).toBe('todo_id');
  });

  it('close 缺 terminal → 拦下（列出三个终态）', async () => {
    const res = await tool(fakeClient()).call({ action: 'close', todo_id: 1 } as any);
    expect(res.success).toBe(false);
    expect((res.error as any).issue).toContain('handled|ignored|expired');
  });

  it('ignored 缺 next_condition → 拦下（并写明服务端错误码）', async () => {
    const res = await tool(fakeClient()).call({ action: 'close', todo_id: 1, terminal: 'ignored' } as any);
    expect(res.success).toBe(false);
    expect((res.error as any).field).toBe('next_condition');
    expect((res.error as any).issue).toContain('watch_todo_missing_next_condition');
  });

  it('rule_change 缺 decision_audit_id → 拦下（指向 decision_audit 工具）', async () => {
    const res = await tool(fakeClient()).call({
      action: 'close', todo_id: 1, terminal: 'handled', action_kind: 'rule_change',
    } as any);
    expect(res.success).toBe(false);
    expect((res.error as any).field).toBe('decision_audit_id');
    expect((res.error as any).issue).toContain('decision_audit');
  });
});

describe('watch_todo 动作', () => {
  it('list：投影出决策字段并给计数', async () => {
    const client = fakeClient({
      listWatchTodos: vi.fn().mockResolvedValue([
        { id: 91, symbol: '300253', level: 'P1', flow_state: 'L3', action_kind: 'rule_change',
          rule_id: 255, account: null, owner_kind: 'agent', owner_ref: 'agent-dh',
          due_at: 'D', escalate_count: 7, claimed_at: null, created_at: 'C', trigger_id: null,
          terminal: null, close_reason: null, next_condition: null, decision_audit_id: null,
          autonomy: 'remind_only', sla_seconds: 1800, closed_at: null },
      ]),
    });
    const res = await tool(client).call({ action: 'list', limit: 10 } as any);

    expect(client.listWatchTodos).toHaveBeenCalledWith({
      level: undefined, flow_state: undefined, account: undefined, limit: 10,
    });
    expect(res.success).toBe(true);
    expect((res.data as any).count).toBe(1);
    expect((res.data as any).todos[0]).toMatchObject({
      id: 91, symbol: '300253', level: 'P1', action_kind: 'rule_change', escalate_count: 7,
    });
    // 不把整行原样塞进上下文（trigger_id/autonomy 等与决策无关）
    expect((res.data as any).todos[0].autonomy).toBeUndefined();
  });

  it('list 默认 limit=30', async () => {
    const client = fakeClient();
    await tool(client).call({ action: 'list' } as any);
    expect(client.listWatchTodos).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 30 }));
  });

  it('claim：默认用本实例标识并回执接手人/流转态', async () => {
    const client = fakeClient();
    const res = await tool(client).call({ action: 'claim', todo_id: 91 } as any);

    expect(client.claimWatchTodo).toHaveBeenCalledWith(91, AGENT_REF);
    expect(res.success).toBe(true);
    expect((res.data as any).owner_ref).toBe(AGENT_REF);
    expect((res.data as any).message).toContain('必须 close');
  });

  it('claim：显式 owner_ref 覆盖默认（agent-ts 复用同一工具）', async () => {
    const client = fakeClient();
    await tool(client).call({ action: 'claim', todo_id: 91, owner_ref: 'agent-ts' } as any);
    expect(client.claimWatchTodo).toHaveBeenCalledWith(91, 'agent-ts');
  });

  it('close：只传有值字段（undefined 不当缺参发出去）', async () => {
    const client = fakeClient();
    const res = await tool(client).call({
      action: 'close', todo_id: 91, terminal: 'handled', action_kind: 'rule_change',
      decision_audit_id: 'dec-1', close_reason: '已修规则#255',
    } as any);

    const [id, body] = client.closeWatchTodo.mock.calls[0];
    expect(id).toBe(91);
    expect(body).toEqual({
      terminal: 'handled', action_kind: 'rule_change',
      decision_audit_id: 'dec-1', close_reason: '已修规则#255',
    });
    expect('next_condition' in body).toBe(false);
    expect(res.success).toBe(true);
    expect((res.data as any).terminal).toBe('handled');
    expect((res.data as any).message).toContain('回执已发出');
  });

  it('后端拒绝（已收敛 409）→ 如实返回失败与原因', async () => {
    const client = fakeClient({
      claimWatchTodo: vi.fn().mockRejectedValue(new Error('[quantsys-v2] POST ... 409: watch_todo_already_closed')),
    });
    const res = await tool(client).call({ action: 'claim', todo_id: 5 } as any);

    expect(res.success).toBe(false);
    expect((res.error as any).issue).toContain('watch_todo_already_closed');
  });
});

describe('watch_todo DSH 定义冒烟（可注册性）', () => {
  it('产出 name/parameters/timeout/render/execute 齐备的工具定义', () => {
    const def: any = new WatchTodoTool(fakeClient()).toDSHToolDefinition();

    expect(def.name).toBe('watch_todo');
    expect(def.timeoutMs).toBe(15000);
    expect(def.parameters.action.enum).toEqual(['list', 'claim', 'close']);
    expect(def.parameters.terminal.enum).toEqual(['handled', 'ignored', 'expired']);
    expect(def.parameters.action_kind.enum).toEqual(['trade', 'rule_change']);
    expect(def.parameters.action.required).toBe(true);
    expect(typeof def.output.render).toBe('function');
    expect(typeof def.execute).toBe('function');
    // 描述必须写清 close 的硬约束，否则 agent 会盲试 400
    expect(def.description).toContain('next_condition');
    expect(def.description).toContain('decision_audit_id');
  });
});
