/**
 * 盯盘待办客户端契约测试（2026-10-16）
 *
 * 可失败性：
 *   · 三个方法的 URL/查询参数/请求体必须与 v2 路由契约一致（对不上 = 静默 404/400）；
 *   · 列表要解开 {success, data:{items}} 包装（unwrap 的 Pattern 1）；
 *   · 认领返回 {data:{todo}} 要脱壳成 todo 本身（工具层直接用它的 flow_state/claimed_at）；
 *   · 服务端 success:false 必须抛错（隐式成功是最危险的失败模式）。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { QuantsysV2Client } from '../src/client';

const ok = (data: any) => ({ data: { success: true, data } });

describe('watch_todo 客户端契约', () => {
  let client: QuantsysV2Client;
  let get: any;
  let post: any;

  beforeEach(() => {
    client = new QuantsysV2Client({ baseURL: 'http://localhost:5001', timeout: 5000 });
    get = vi.spyOn((client as any).client, 'get');
    post = vi.spyOn((client as any).client, 'post');
  });

  it('listWatchTodos：查询参数按契约拼装，解开 items 包装', async () => {
    get.mockResolvedValue(ok({ items: [{ id: 91, symbol: '300253' }], total: 1 }));

    const todos = await client.listWatchTodos({ level: 'P1', flow_state: 'L3', limit: 20 });

    expect(get).toHaveBeenCalledWith('/api/watch/todos?level=P1&flow_state=L3&limit=20');
    expect(todos).toEqual([{ id: 91, symbol: '300253' }]);
  });

  it('listWatchTodos：无参数 = 未收敛队列（不带查询串）', async () => {
    get.mockResolvedValue(ok({ items: [], total: 0 }));
    expect(await client.listWatchTodos()).toEqual([]);
    expect(get).toHaveBeenCalledWith('/api/watch/todos');
  });

  it('listWatchTodos：兼容 data 直接是数组的旧形态', async () => {
    get.mockResolvedValue(ok([{ id: 1 }]));
    expect(await client.listWatchTodos()).toEqual([{ id: 1 }]);
  });

  it('claimWatchTodo：POST 到 claim 路由并带 owner_ref，脱壳 todo', async () => {
    post.mockResolvedValue(ok({ todo: { id: 91, flow_state: 'L2', claimed_at: 'T' } }));

    const todo = await client.claimWatchTodo(91, 'agent-dh');

    expect(post).toHaveBeenCalledWith('/api/watch/todos/91/claim', { owner_ref: 'agent-dh' });
    expect(todo).toMatchObject({ id: 91, flow_state: 'L2' });
  });

  it('closeWatchTodo：POST 到 close 路由并透传收敛请求', async () => {
    post.mockResolvedValue(ok({ todo: { id: 91, terminal: 'ignored' }, receipt: { kind: 'result' } }));

    const data = await client.closeWatchTodo(91, {
      terminal: 'ignored', next_condition: 'NEXT', close_reason: '不动',
    });

    expect(post).toHaveBeenCalledWith('/api/watch/todos/91/close', {
      terminal: 'ignored', next_condition: 'NEXT', close_reason: '不动',
    });
    expect(data.receipt).toEqual({ kind: 'result' });
  });

  it('success:false（HTTP 200 包裹错误）→ 抛错，不静默成功', async () => {
    post.mockResolvedValue({ data: { success: false, error: 'watch_todo_missing_audit' } });

    await expect(client.closeWatchTodo(91, { terminal: 'handled', action_kind: 'rule_change' }))
      .rejects.toThrow('watch_todo_missing_audit');
  });
});
