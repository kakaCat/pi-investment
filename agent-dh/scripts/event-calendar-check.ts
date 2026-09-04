#!/usr/bin/env tsx
/**
 * 事件日历检查脚本（免 agent 版，2026-09-05 w-4918ed49 改造）
 * 对应 Agent OS 任务：event-calendar-check（每日 16:45）
 *
 * 原 dsh-webhook → agent 消化链路的问题：依赖 LLM 窗口消化，投递不可观测、失败无痕。
 * 本脚本为确定性执行 + 规则直发飞书（与 data-quality-monitor 同模式）：
 *   1) GET /api/events/upcoming?days=2 —— 未来 2 天(含今天) pending+notified 事件
 *   2) 仅 status=pending 且 importance>=2 推送：importance>=3→alerts(高优)；==2→reports(普通)
 *   3) 推送成功后才 PATCH {status:'notified', meta:{notified_at}} —— notified 事件
 *      仍会出现在 upcoming 返回，但脚本跳过不重复推送（幂等去重）
 *   4) importance<2 事件不推送不改状态（留给 agent 盘前参考）
 * 发送失败不 PATCH → 下一轮自动重试；任一失败脚本 exit 1（Agent OS 记 failed）
 */

import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { AgentOSClient } from '@pi-investment/agent-os-client';

const qv2 = new QuantsysV2Client({
  baseURL: process.env.QUANTSYS_V2_URL || 'http://localhost:5001',
  timeout: 30000,
});

const aos = new AgentOSClient({
  baseURL: process.env.AGENT_OS_URL || 'http://localhost:8080',
  agentId: 'event-calendar-check',
});

const TYPE_LABEL: Record<string, string> = {
  cpi_ppi: 'CPI/PPI', pmi: 'PMI', nbs: '宏观数据', lpr: 'LPR 报价', fomc: 'FOMC',
  us_cpi: '美国CPI', nfp: '非农', earnings: '财报', futures_delivery: '交割日', policy: '政策', other: '事件',
};

function fmtEvent(ev: any): { title: string; content: string } {
  const dt = ev.event_date || '';
  const tm = ev.event_time ? ' ' + ev.event_time : '';
  const type = TYPE_LABEL[ev.event_type] || ev.event_type || '事件';
  const head = '📅 **' + type + '提醒：' + (ev.title || '') + '**（' + dt + tm + '）';
  const lines: string[] = [head, ''];
  if (ev.description) lines.push('- 内容：' + ev.description);
  lines.push('- 类型：' + (ev.event_type || '-') + '｜来源：' + (ev.source || '-'));
  if (ev.market) lines.push('- 市场：' + ev.market + '（影响板块参考）');
  if (ev.symbol) lines.push('- 关联标的：' + ev.symbol);
  lines.push('');
  lines.push('---');
  lines.push('_自动事件日历检查 · 每日 16:45 · 来源: event-calendar-check（免 agent）_');
  const prefix = ev.importance >= 3 ? '⚠️' : '📋';
  return { title: prefix + ' ' + type + ' ' + dt + tm, content: lines.join('\n') };
}

async function main() {
  console.log('[*] 事件日历检查开始...');
  const res: any = await qv2.getUpcomingEvents(2);
  const events: any[] = (res && res.events) || [];
  if (events.length === 0) {
    console.log('[✓] 未来2日无待处理事件');
    return;
  }
  console.log('[*] upcoming 返回 ' + events.length + ' 条');
  let sent = 0, skippedNotified = 0, lowPri = 0, failed = 0;
  for (const ev of events) {
    if (ev.status !== 'pending') { skippedNotified++; continue; }
    const imp = Number(ev.importance || 1);
    if (imp < 2) { lowPri++; continue; }
    const isHigh = imp >= 3;
    const f = fmtEvent(ev);
    try {
      // 推送成功才标记 notified（防通知失败却丢事件）
      await aos.notification.send({
        title: f.title,
        content: f.content,
        channel: isHigh ? 'alerts' : 'reports',
        urgency: isHigh ? 'high' : 'normal',
      });
      await qv2.updateEvent(ev.id, {
        status: 'notified',
        meta: { notified_at: new Date().toISOString(), notified_by: 'event-calendar-check' },
      });
      console.log('[✓] 已推送并标记 id=' + ev.id + ' ' + ev.title + '（' + (isHigh ? 'alerts/high' : 'reports') + '）');
      sent++;
    } catch (err: any) {
      console.error('[✗] id=' + ev.id + ' ' + (ev.title || '') + ' 通知失败，未标记，下轮重试: ' + err.message);
      failed++;
    }
  }
  console.log('[✓] 完成：推送 ' + sent + ' 条｜跳过(已通知) ' + skippedNotified + '｜低优忽略 ' + lowPri + '｜失败 ' + failed);
  if (failed > 0) process.exitCode = 1;
}

main().catch((error) => {
  console.error('[✗] 执行失败:', error);
  process.exit(1);
});
