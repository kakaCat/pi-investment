/**
 * MainlineScanTool - 市场主线扫描工具
 */

import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { mainlineScanPrompt, MainlineScanParams, MainlineScanResult } from './prompt';

interface OsMemoryStore {
  searchMemory(params: { q?: string; kind?: string; scope?: string; limit?: number }): Promise<{ items: any[] }>;
  createMemory(entry: { kind: string; scope: string; title: string; content: string; payload?: any; status?: string; confidence?: number; source?: string; provenance?: any }): Promise<{ id: string }>;
}

/**
 * 市场主线扫描工具类
 */
export class MainlineScanTool extends BaseTool<MainlineScanParams, MainlineScanResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'mainline_scan',
    category: 'market',
    version: '1.0.0',
    timeoutMs: 90000, // 板块接口冷启动 15s+，放宽到 90s
  };

  protected readonly prompt = mainlineScanPrompt;

  constructor(
    private qv2: QuantsysV2Client,
    private memoryClient: OsMemoryStore,
  ) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(_args: MainlineScanParams): ValidationResult {
    // days 是可选的，直接通过
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: MainlineScanParams, _context: ToolContext): Promise<MainlineScanResult> {
    const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });

    // 幂等检查：今日已落库则跳过
    const existing = await this.memoryClient.searchMemory({ q: `mainline ${today}`, scope: 'market:mainline', limit: 3 });
    const dup = (existing?.items || []).find((it: any) => it.payload?.date === today && it.status !== 'deprecated');
    if (dup) {
      return { date: today, mainlines: dup.payload?.mainlines, skipped: true };
    }

    const res: any = await this.qv2.getSectorAnalysis({ days: args.days ?? 5, limit: 10 });

    // 2026-09-01 修复：/api/market/sectors 返回 {data:{industries, concepts}}（行业/概念分组），
    // 原只解析 res.sectors/items/ranking 扁平数组 → 恒为空。兼容两种结构，行业优先。
    const industries: any[] = res?.industries ?? res?.data?.industries ?? [];
    const concepts: any[] = res?.concepts ?? res?.data?.concepts ?? [];
    const grouped: any[] = [
      ...(Array.isArray(industries) ? industries : []),
      ...(Array.isArray(concepts) ? concepts : []),
    ];
    const sectors: any[] = grouped.length > 0 ? grouped : (res?.sectors || res?.items || res?.ranking || []);
    const top3 = sectors.slice(0, 3).map((sec: any, i: number) => ({
      rank: i + 1,
      sector: sec['板块名称'] ?? sec.name ?? sec.sector ?? sec.industry ?? `未知板块${i + 1}`,
      code: sec['板块代码'] ?? sec.code ?? null,
      change_pct: sec['涨跌幅'] ?? sec.change_pct ?? sec.changePct ?? sec.pct ?? null,
      market_cap: sec['总市值'] ?? null,
      type: sec['类型'] ?? null,
      basis: `近${args.days ?? 5}日板块强度排名前${i + 1}（按板块涨跌幅）`,
    }));

    // 落库
    await this.memoryClient.createMemory({
      kind: 'episode',
      scope: 'market:mainline',
      title: `mainline ${today}: ${top3.map(t => t.sector).join('/')}`,
      content: `${today} 主线 Top3：${top3.map(t => `${t.rank}.${t.sector}(${t.change_pct ?? '?'}%)`).join('，')}。催化剂关联待盘后例程补充。`,
      payload: { date: today, mainlines: top3, catalyst: null, note: '催化剂由盘后例程 LLM 结合 web_search 补充' },
      status: 'testing',
      confidence: 0.6,
      source: 'mainline_scan',
      provenance: { channel: 'dsh', session_kind: 'agent' },
    });

    return { date: today, mainlines: top3, skipped: false };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: MainlineScanResult, _context: ToolContext): ToolResponse<MainlineScanResult> {
    return {
      success: true,
      data: result,
    };
  }
}
