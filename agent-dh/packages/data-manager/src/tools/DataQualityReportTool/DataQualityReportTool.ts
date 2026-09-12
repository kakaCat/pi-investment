import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse, ErrorType } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { dataQualityReportPrompt, type DataQualityReportParams, type DataQualityReportResult } from './prompt';

export class DataQualityReportTool extends BaseTool<DataQualityReportParams, DataQualityReportResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'data_quality_report',
    category: 'data-manager',
    version: '1.0.0',
    timeoutMs: 60000, // 2026-09-11：语义探针需多次调用后端，20s 不够
  };

  protected readonly prompt = dataQualityReportPrompt;

  constructor(private quantsysClient: QuantsysV2Client) {
    super();
  }

  protected validate(params: DataQualityReportParams): ValidationResult {
    const errors: string[] = [];

    if (params.data_type) {
      const validTypes = ['quote', 'kline', 'financial', 'all'];
      if (!validTypes.includes(params.data_type)) {
        errors.push(`data_type 必须是 ${validTypes.join(', ')} 之一`);
      }
    }

    if (params.days !== undefined) {
      if (!Number.isInteger(params.days) || params.days < 1 || params.days > 30) {
        errors.push('days 必须是 1-30 之间的整数');
      }
    }

    if (errors.length > 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        issue: errors.join('; '),
      };
    }

    return { success: true };
  }

  protected async execute(
    params: DataQualityReportParams,
    context: ToolContext
  ): Promise<DataQualityReportResult> {
    const dataType = params.data_type || 'all';
    const days = params.days || 7;

    const response: any = await this.quantsysClient.getDataQualityReport({
      data_type: dataType,
      days,
    });

    // 2026-09-11 新增（REQ-342799 语义级校验）：
    // 后端 /api/data/quality-report 衡量的是『个股行情/K线数据质量』（评分/缺失/延迟），
    // 完全不覆盖『接口层语义失效』——实测同日 6 个工具静默返回 0/空，而该报告仍报 92.5 分 0 异常。
    // 故在工具层补一组契约探针，把接口级真实性并入同一份报告，供盘前/排障一键体检。
    const tool_health = await this.probeToolHealth();
    const failCount = tool_health.filter((p) => p.status === 'fail').length;
    const degradedCount = tool_health.filter((p) => p.status === 'degraded').length;

    const okCount = tool_health.length - failCount - degradedCount;
    const probeSummary =
      '接口语义探针 ' + tool_health.length + ' 项：ok ' + okCount + ' / degraded ' + degradedCount + ' / fail ' + failCount;
    // 双通道输出（2026-09-11 实测教训）：本工具 output.schema 为 additionalProperties:false，
    // 即便已在 prompt.ts 声明 tool_health，运行实例仍会把该字段丢掉（疑似框架按注册期 schema 收敛输出）。
    // 因此把探针结果**同时**写入已声明的 anomalies / summary —— 用户与 agent 默认就看这两处，
    // 结构化副本仍保留在 tool_health（schema 生效时可用）。
    const probeAnomalies = tool_health
      .filter((x) => x.status !== 'ok')
      .map((x) => ({ type: 'tool_health_probe', probe: x.probe, status: x.status, evidence: x.evidence }));
    const baseAnomalies: any[] = Array.isArray((response as any)?.anomalies) ? (response as any).anomalies : [];
    const baseSummary = String((response as any)?.summary ?? '');

    return {
      ...(response as any),
      anomalies: [...baseAnomalies, ...probeAnomalies],
      summary: (baseSummary ? baseSummary + '；' : '') + probeSummary,
      tool_health,
      tool_health_summary: probeSummary,
      scope_note:
        'overall_score/records 等字段来自后端个股数据质量记录；接口语义探针（tool_health，并镜像进 anomalies/summary）' +
        '为本工具层新增，二者口径不同不可相互替代——总分高不代表接口层没有静默失效。',
    } as DataQualityReportResult;
  }

  /**
   * 接口契约探针（2026-09-11，REQ-342799）：逐项判定 ok / degraded / fail，并给出证据。
   * 判定原则：拿不到有效数据=fail；拿得到但语义降级（窗口参数无效、字段全 0、空条件规则）=degraded。
   */
  private async probeToolHealth(): Promise<Array<{ probe: string; status: string; evidence: string }>> {
    const out: Array<{ probe: string; status: string; evidence: string }> = [];
    const push = (probe: string, status: string, evidence: string) => out.push({ probe, status, evidence });
    const q: any = this.quantsysClient as any;
    const rowsOf = (x: any) => (Array.isArray(x) ? x : (x?.data?.industries ?? x?.industries ?? []));

    // 1) 板块列表可用性 + 窗口参数是否生效（改用 5 vs 60，间隔更大，判据更严格）
    try {
      const a: any = await q.getSectorAnalysis({ days: 5 });
      const b: any = await q.getSectorAnalysis({ days: 60 });
      const ra = rowsOf(a);
      const rb = rowsOf(b);
      if (!ra.length) push('sector_analysis.rows', 'fail', '板块列表为空');
      else {
        // 加强判据：不仅比 length，还要比 top3 的实际涨跌幅（窗口不同，数值必然不同）
        const top3A = ra.slice(0, 3).map((x: any) => `${x.name}:${x.change_pct}`).join(',');
        const top3B = rb.slice(0, 3).map((x: any) => `${x.name}:${x.change_pct}`).join(',');
        const same = ra.length === rb.length && top3A === top3B;
        push('sector_analysis.window', same ? 'degraded' : 'ok',
          same
            ? `days=5 与 days=60 完全相同（${ra.length}行，top3=${top3A}）→ 窗口参数被忽略`
            : `窗口参数生效（${ra.length}行，5天top3≠60天top3）`);
      }
    } catch (e: any) { push('sector_analysis', 'fail', '调用失败：' + String(e?.message ?? e).slice(0, 120)); }

    // 2) 筹码指标（曾静默返回全 0）
    try {
      const c: any = await q.getChipDistribution('600519');
      const m = (c?.data ?? c)?.metrics;
      push('chip_distribution.metrics', m ? 'ok' : 'fail', m ? 'metrics 存在' : '响应缺少 metrics');
    } catch (e: any) { push('chip_distribution', 'fail', String(e?.message ?? e).slice(0, 120)); }

    // 3) 指数K线（基准数据可达性，业绩归因前提）
    try {
      const end = new Date().toISOString().slice(0, 10);
      const start = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
      const k: any = await q.getKlines('000300', start, end, 'daily');
      const rows = Array.isArray(k) ? k : (k?.klines ?? []);
      push('kline.index(000300)', rows.length ? 'ok' : 'fail', rows.length ? rows.length + ' 根' : '指数K线为空（基准数据不可达）');
    } catch (e: any) { push('kline.index(000300)', 'fail', String(e?.message ?? e).slice(0, 120)); }

    // 4) 盯盘规则可读性（空条件规则永不触发）
    try {
      const w: any = await q.listWatchRules();
      const rules: any[] = Array.isArray(w) ? w : (w?.rules ?? []);
      const empty = rules.filter((r: any) => !Array.isArray(r?.conditions) || r.conditions.length === 0).length;
      push('watch_list.conditions', rules.length === 0 ? 'fail' : (empty ? 'degraded' : 'ok'),
        rules.length + ' 条规则，其中 ' + empty + ' 条 conditions 为空（永不触发）');
    } catch (e: any) { push('watch_list', 'fail', String(e?.message ?? e).slice(0, 120)); }

    // 5) 分红源（曾返回 success=true 但全 0 行）
    try {
      const d: any = await q.getDividends('600519', 3);
      const rows: any[] = Array.isArray(d) ? d : (d?.data ?? []);
      const usable = rows.filter((r: any) => Number(r?.dividend_per_share) > 0).length;
      push('dividend(600519)', usable ? 'ok' : 'fail', rows.length + ' 行 / 有效 ' + usable + ' 行' + (usable ? '' : '（上游 akshare 分红源失效）'));
    } catch (e: any) { push('dividend', 'fail', String(e?.message ?? e).slice(0, 120)); }

    // 6) 板块资金流
    try {
      const f: any = await q.getSectorFlow();
      push('sector_flow', f?.success === false ? 'fail' : 'ok', f?.success === false ? String(f?.error ?? 'failed').slice(0, 100) : '可用');
    } catch (e: any) { push('sector_flow', 'fail', String(e?.message ?? e).slice(0, 120)); }

    // 7) 资金类因子静默全 0（2026-09-11，REQ-cf627b）
    //    实测：后端因子表 10 个资金因子全为 0.0 且 stale=false（新鲜的假数据），
    //    而 provider 资金流同标的显示主力净流入 6.84 亿 —— 数据层自相矛盾。
    //    factor_calculate 已加护栏（剔除 + degraded），本探针负责每日自动发现回归。
    try {
      const fr: any = await q.calculateFactors({ symbol: '600150' });
      const rows: any[] = Array.isArray(fr?.factors) ? fr.factors : [];
      const FUND = [
        'super_large_net', 'large_net', 'main_net_pct', 'super_large_pct', 'large_pct',
        'fund_inflow_pos_days_5', 'fund_inflow_pos_days_3', 'fund_inflow_3d_sum',
        'fund_inflow_5d_sum', 'main_net_inflow',
      ];
      const present = rows.filter((r: any) => FUND.includes(String(r?.factor_name)));
      const zeros = present.filter((r: any) => Number(r?.factor_value) === 0);
      const dead = present.length > 0 && zeros.length === present.length;
      push('factor.fund_group(600150)',
        present.length === 0 ? 'fail' : (dead ? 'degraded' : 'ok'),
        present.length === 0
          ? '因子表未返回任何资金类因子'
          : dead
            ? `${zeros.length}/${present.length} 个资金因子全为 0 且标记非过期 → 疑似静默假数据（factor_calculate 已剔除并与 provider 对账）`
            : `${present.length} 个资金因子，非零 ${present.length - zeros.length} 个`);
    } catch (e: any) { push('factor.fund_group', 'fail', String(e?.message ?? e).slice(0, 120)); }

    // 8) factor_calculate 资金因子字段（曾部分为 0 且 degraded=false 静默）
    try {
      const f: any = await q.calculateFactors({ symbol: '600150' });
      const factors = f?.factors ?? f?.data?.factors ?? {};
      const fundFields = ['super_large_net', 'large_net', 'main_net_pct', 'main_net_inflow', 'fund_inflow_5d_sum'];
      const zeroFields = fundFields.filter(k => factors[k] === 0);
      const nonZeroFields = fundFields.filter(k => typeof factors[k] === 'number' && factors[k] !== 0);
      if (zeroFields.length === fundFields.length) {
        push('factor_calculate.fund_fields', 'fail', `资金因子全部为 0（${fundFields.join(',')}）`);
      } else if (zeroFields.length > 0) {
        push('factor_calculate.fund_fields', 'degraded', `资金因子部分为 0：${zeroFields.join(',')}；非零：${nonZeroFields.join(',')}`);
      } else {
        push('factor_calculate.fund_fields', 'ok', `资金因子全部非零（${nonZeroFields.length}个）`);
      }
    } catch (e: any) { push('factor_calculate', 'fail', String(e?.message ?? e).slice(0, 120)); }

    // 9) dividend_yield（数据有流水但 yield 字段仍 null）
    try {
      const d: any = await q.getDividends('601398', 3);
      const rows = d?.data ?? d ?? [];
      if (!rows.length) push('dividend.history', 'fail', '分红历史为空');
      else {
        const hasYield = rows.some((r: any) => typeof r.dividend_yield === 'number');
        push('dividend.yield', hasYield ? 'ok' : 'degraded', 
          hasYield ? '股息率字段已计算' : `有 ${rows.length} 条分红流水，但 dividend_yield 全为 null`);
      }
    } catch (e: any) { push('dividend', 'fail', String(e?.message ?? e).slice(0, 120)); }

    // 10) barra 小样本可用性（账户只有 2 只持仓，横截面回归永久样本不足 → 需小样本路径）
    try {
      // 直接调用后端 API（client 未封装此方法）
      const baseUrl = (q as any).baseURL || 'http://localhost:5001';
      const resp = await fetch(`${baseUrl}/api/factor-models/barra/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols: ['300677', '600887'], start_date: '2026-08-01', end_date: '2026-09-11' })
      });
      const b: any = await resp.json();
      const hasRisk = b?.success && (typeof b?.data?.total_risk === 'number' || (b?.data?.factor_risks ?? []).length > 0);
      push('barra.small_sample', hasRisk ? 'ok' : 'degraded',
        hasRisk ? 'Barra 分解可用' : '样本不足（2只持仓）→ 横截面回归不可用，需小样本路径（单因子映射/收缩协方差）');
    } catch (e: any) { push('barra', 'fail', String(e?.message ?? e).slice(0, 120)); }

    return out;
  }
  protected wrap(data: DataQualityReportResult, context: ToolContext): ToolResponse<DataQualityReportResult> {
    // 2026-08-30 修复：后端实际返回 records 列表（无 missing_data/delayed_data/anomalies 顶层键），
    // 直接 .length 会 TypeError；且输出 schema 为 additionalProperties:false，必须映射为契约字段。
    const records: any[] = Array.isArray((data as any).records) ? (data as any).records : [];
    const scores = records
      .map((r: any) => r?.overall_score)
      .filter((n: any): n is number => typeof n === 'number');

    const data_type = (data as any).data_type ?? (context as any).data_type ?? 'all';
    const check_date = (data as any).check_date ?? records[0]?.check_date ?? '';
    const overall_score = typeof (data as any).overall_score === 'number'
      ? (data as any).overall_score
      : (scores.length > 0 ? Math.min(...scores) : 0);

    const missing_data = Array.isArray(data.missing_data)
      ? data.missing_data
      : records
          .filter((r: any) => (r?.removed_count ?? 0) > 0 || (r?.cleaned_count ?? 0) < (r?.original_count ?? 0))
          .map((r: any) => ({ symbol: r?.symbol ?? '', date: r?.check_date ?? '', type: r?.period ?? 'daily', removed_count: r?.removed_count ?? 0 }));
    const delayed_data = Array.isArray(data.delayed_data) ? data.delayed_data : [];
    const anomalies = Array.isArray(data.anomalies)
      ? data.anomalies
      : records
          .filter((r: any) => (r?.error_count ?? 0) > 0)
          .map((r: any) => ({ symbol: r?.symbol ?? '', date: r?.check_date ?? '', type: r?.period ?? 'daily', error_count: r?.error_count ?? 0 }));

    const mapped: DataQualityReportResult = {
      data_type,
      check_date,
      overall_score,
      missing_data,
      delayed_data,
      anomalies,
      summary: (data as any).summary ?? `数据质量报告（${data_type}）: ${records.length} 条检查记录, 综合评分 ${overall_score.toFixed(1)}`,
      // 2026-09-11 修复：保留 tool_health 探针结果（execute 里生成，wrap 里曾被静默丢弃）
      tool_health: (data as any).tool_health,
      tool_health_summary: (data as any).tool_health_summary,
      scope_note: (data as any).scope_note,
    };

    const score = typeof overall_score === 'number' ? overall_score : 0;
    let message = `数据质量报告（${data_type}）: 评分 ${score.toFixed(1)}`;
    if (missing_data.length > 0) message += `, ${missing_data.length} 处缺失`;
    if (delayed_data.length > 0) message += `, ${delayed_data.length} 处延迟`;
    if (anomalies.length > 0) message += `, ${anomalies.length} 处异常`;

    return {
      success: true,
      data: mapped,
      message,
      metadata: {
        data_type,
        overall_score,
        issues: missing_data.length + delayed_data.length + anomalies.length,
      },
    };
  }
}