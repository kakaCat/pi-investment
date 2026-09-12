/**
 * FeishuNotificationAdapter - INotificationService 实现
 * 
 * 使用现有的 feishu_notify 工具发送通知
 */

import type { INotificationService, EvaluationReport } from '../services/DecisionTrackingApplicationService';

/**
 * Feishu Notifier 接口（假设存在）
 */
export interface IFeishuNotifier {
  notify(params: {
    title: string;
    content: string;
    urgency: 'low' | 'normal' | 'high';
    channel?: string;
  }): Promise<{ success: boolean }>;
}

export class FeishuNotificationAdapter implements INotificationService {
  constructor(private readonly feishuNotifier: IFeishuNotifier) {}
  
  async sendEvaluationReport(report: EvaluationReport): Promise<void> {
    try {
      // 构造飞书消息内容
      const content = this.formatReport(report);
      
      // 发送通知
      const result = await this.feishuNotifier.notify({
        title: report.title,
        content: content,
        urgency: 'normal',
        channel: 'reports',
      });
      
      if (!result.success) {
        throw new Error('发送通知失败');
      }
      
      console.log('📬 评估报告已发送');
    } catch (error: any) {
      console.error('发送通知失败:', error);
      throw error;
    }
  }
  
  /**
   * 格式化报告为 Markdown
   */
  private formatReport(report: EvaluationReport): string {
    const lines: string[] = [];
    
    // 摘要
    lines.push(`**摘要**: ${report.summary}`);
    lines.push('');
    
    // 统计
    lines.push('**统计**:');
    lines.push(`- 总评估: ${report.totalEvaluated} 条`);
    lines.push(`- 成功: ${report.successCount} 条`);
    lines.push(`- 失败: ${report.failureCount} 条`);
    lines.push(`- 平均分: ${report.averageScore.toFixed(1)}`);
    lines.push('');
    
    // 亮点
    if (report.highlights.length > 0) {
      lines.push('**亮点**:');
      report.highlights.forEach(h => lines.push(`- ${h}`));
      lines.push('');
    }
    
    // 建议
    if (report.recommendations.length > 0) {
      lines.push('**建议**:');
      report.recommendations.forEach(r => lines.push(`- ${r}`));
    }
    
    return lines.join('\n');
  }
}
