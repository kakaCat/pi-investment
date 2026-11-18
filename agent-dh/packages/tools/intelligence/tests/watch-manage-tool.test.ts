import { describe, expect, it, vi } from 'vitest';
import { WatchManageTool } from '../src/tools/WatchManageTool/WatchManageTool';

function makeTool() {
  const client = {
    manageWatchRule: vi.fn(async (request: any) => ({ rule: { id: request.rule_id ?? 1 } })),
  };
  return { tool: new WatchManageTool(client as any), client };
}

describe('watch_manage audit contract', () => {
  it.each(['create', 'enable', 'disable', 'delete'])('%s 缺审计时在工具边界 fail-closed', (action) => {
    const { tool, client } = makeTool();
    const result = (tool as any).validate({
      action, rule_id: 1, name: 'n', symbol: '600000', condition: 'price>10', reason: '理由',
    });
    expect(result.success).toBe(false);
    expect(result.issue).toContain('decision_audit_id');
    expect(client.manageWatchRule).not.toHaveBeenCalled();
  });

  it('enable 保留 reason/audit/source 血缘并返回归档语义', async () => {
    const { tool, client } = makeTool();
    const params = {
      action: 'enable' as const, rule_id: 7, reason: '复核完成',
      decision_audit_id: 'DEC-1', source_trigger_id: 4786,
    };
    const result = await (tool as any).execute(params, {});
    expect(client.manageWatchRule).toHaveBeenCalledWith(params);
    expect(result).toMatchObject({ success: true, rule_id: 7, action: 'enable' });
  });

  it('delete 对用户显示软归档而不是物理删除', async () => {
    const { tool } = makeTool();
    const result = await (tool as any).execute({
      action: 'delete', rule_id: 8, reason: '退役', decision_audit_id: 'DEC-2',
    }, {});
    expect(result.message).toBe('规则已归档');
  });
});
