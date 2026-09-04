#!/usr/bin/env tsx
/**
 * 数据质量监控脚本（替代后端主动告警）
 * 
 * 功能：定期调用 data_quality_report，检测到陈旧数据时飞书告警
 * 触发：通过 reminder_create 设置为每日 16:05 执行（盘后例程前）
 * 
 * 使用：
 *   1. 手动执行：tsx scripts/data-quality-monitor.ts
 *   2. 定时执行：通过 investor 窗口调用 reminder_create 注册
 */

import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { AgentOSClient } from '@pi-investment/agent-os-client';

const qv2 = new QuantsysV2Client({
  baseURL: process.env.QUANTSYS_V2_URL || 'http://localhost:5001',
  timeout: 30000,
});

const aos = new AgentOSClient({
  baseURL: process.env.AGENT_OS_URL || 'http://localhost:8080',
  agentId: 'data-quality-monitor',
});

interface QualityIssue {
  data_type: string;
  issue: string;
  severity: 'high' | 'medium' | 'low';
}

async function checkDataQuality(): Promise<QualityIssue[]> {
  const issues: QualityIssue[] = [];
  
  try {
    // 检查因子数据新鲜度
    const factorReport: any = await qv2.getDataQualityReport({
      data_type: 'factor',
      days: 3,
    });
    
    const factorScore = factorReport?.overall_score ?? 100;
    const staleFactors = factorReport?.stale_data ?? [];
    
    if (factorScore < 70) {
      issues.push({
        data_type: 'factor',
        issue: `因子数据质量评分 ${factorScore}/100，低于 70 阈值`,
        severity: 'high',
      });
    }
    
    if (staleFactors.length > 0) {
      const staleDays = Math.max(...staleFactors.map((f: any) => f.stale_days || 0));
      issues.push({
        data_type: 'factor',
        issue: `${staleFactors.length} 个因子数据陈旧（最长 ${staleDays} 天）：${staleFactors.map((f: any) => f.factor_name).slice(0, 5).join(', ')}`,
        severity: staleDays > 7 ? 'high' : staleDays > 3 ? 'medium' : 'low',
      });
    }
    
    // 检查行情数据新鲜度
    const quoteReport: any = await qv2.getDataQualityReport({
      data_type: 'quote',
      days: 1,
    });
    
    const quoteScore = quoteReport?.overall_score ?? 100;
    if (quoteScore < 80) {
      issues.push({
        data_type: 'quote',
        issue: `行情数据质量评分 ${quoteScore}/100，低于 80 阈值`,
        severity: 'high',
      });
    }
    
    // 检查财务数据新鲜度（季度更新，较宽松）
    const financialReport: any = await qv2.getDataQualityReport({
      data_type: 'financial',
      days: 30,
    });
    
    const financialScore = financialReport?.overall_score ?? 100;
    if (financialScore < 60) {
      issues.push({
        data_type: 'financial',
        issue: `财务数据质量评分 ${financialScore}/100，低于 60 阈值`,
        severity: 'medium',
      });
    }
    
  } catch (error: any) {
    issues.push({
      data_type: 'system',
      issue: `数据质量检查失败: ${error.message}`,
      severity: 'high',
    });
  }
  
  return issues;
}

async function sendAlert(issues: QualityIssue[]) {
  const highIssues = issues.filter(i => i.severity === 'high');
  const mediumIssues = issues.filter(i => i.severity === 'medium');
  
  if (highIssues.length === 0 && mediumIssues.length === 0) {
    console.log('[✓] 数据质量正常，无需告警');
    return;
  }
  
  const urgency = highIssues.length > 0 ? 'high' : 'normal';
  const title = highIssues.length > 0 
    ? `⚠️ 数据质量告警（${highIssues.length} 项高危）`
    : `⚡ 数据质量提醒（${mediumIssues.length} 项中危）`;
  
  const content = `## 数据质量监控报告

**时间**: ${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}

### 高危问题（${highIssues.length}）
${highIssues.map(i => `- **[${i.data_type}]** ${i.issue}`).join('\n') || '_无_'}

### 中危问题（${mediumIssues.length}）
${mediumIssues.map(i => `- **[${i.data_type}]** ${i.issue}`).join('\n') || '_无_'}

### 建议行动
${highIssues.some(i => i.data_type === 'factor') ? '- 立即排查因子计算管道（Agent OS scheduler / quantsys-v2）\n- 考虑手动补录缺失日期数据\n' : ''}
${highIssues.some(i => i.data_type === 'quote') ? '- 检查行情数据源连接状态\n- 验证数据采集任务是否正常\n' : ''}
- 完整质量报告：调用 \`data_quality_report(data_type='all', days=7)\`

---
_自动监控脚本 · 每日 16:05 · 来源: data-quality-monitor_`;
  
  try {
    // 2026-09-05 免 agent 改造：告警直发飞书渠道（alerts=高危/reports=中危），
    // 不再写 memory(kind=alert)——memory POST 只落库不触发任何通知，旧设计从未闭环
    await aos.notification.send({
      title,
      content,
      channel: urgency === 'high' ? 'alerts' : 'reports',
    });
    
    console.log(`[✓] 已发送${urgency === 'high' ? '高优' : '普通'}告警到飞书`);
  } catch (error: any) {
    console.error('[✗] 告警发送失败:', error.message);
    throw error;
  }
}

async function main() {
  console.log('[*] 开始数据质量检查...');
  const issues = await checkDataQuality();
  
  console.log(`[*] 发现 ${issues.length} 个问题`);
  issues.forEach(i => {
    console.log(`  [${i.severity}] [${i.data_type}] ${i.issue}`);
  });
  
  await sendAlert(issues);
  console.log('[*] 检查完成');
}

main().catch((error) => {
  console.error('[✗] 执行失败:', error);
  process.exit(1);
});
