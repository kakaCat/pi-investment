import { describe, expect, it, vi } from 'vitest';
import { OpportunityScanTool } from '../src/tools/OpportunityScanTool/OpportunityScanTool';

function makeTool() {
  const client = {
    scanOpportunitiesDetailed: vi.fn(async () => ({
      scanned: 1, opportunities: [], watch_rules_created: [{ action: 'skipped' }],
    })),
  };
  return { tool: new OpportunityScanTool(client as any), client };
}

describe('opportunity_scan read/write boundary', () => {
  it('默认扫描显式 auto_create_rules=false，不产生隐式规则写入', async () => {
    const { tool, client } = makeTool();
    const result = await (tool as any).execute({ scan_type: 'accumulation' }, {});
    expect(client.scanOpportunitiesDetailed).toHaveBeenCalledWith(expect.objectContaining({
      auto_create_rules: false,
    }));
    expect(result.watch_rule_results).toEqual([{ action: 'skipped' }]);
  });

  it('自动建规必须显式给账户，不能猜默认账户', () => {
    const { tool, client } = makeTool();
    const result = (tool as any).validate({ auto_create_rules: true });
    expect(result.success).toBe(false);
    expect(result.field).toBe('account_name');
    expect(client.scanOpportunitiesDetailed).not.toHaveBeenCalled();
  });

  it('自动建规还必须携带并透传事前审计号', async () => {
    const { tool, client } = makeTool();
    const invalid = (tool as any).validate({ auto_create_rules: true, account_name: 'acct_A' });
    expect(invalid.success).toBe(false);
    expect(invalid.field).toBe('decision_audit_id');

    await (tool as any).execute({
      auto_create_rules: true, account_name: 'acct_A', decision_audit_id: 'DA-scan',
    }, {});
    expect(client.scanOpportunitiesDetailed).toHaveBeenCalledWith(expect.objectContaining({
      auto_create_rules: true, account_name: 'acct_A', decision_audit_id: 'DA-scan',
    }));
  });
});
