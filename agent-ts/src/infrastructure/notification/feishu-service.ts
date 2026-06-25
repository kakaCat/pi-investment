import axios from 'axios';

export interface DecisionNotification {
  action: string;
  symbol: string;
  reason: string;
  confidence: number;
}

export interface AlertNotification {
  level: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  message: string;
}

export interface DailyReport {
  date: string;
  decisions: number;
  pnl: number;
  pools: number;
  alerts: number;
}

export class FeishuNotificationService {
  private webhook: string;

  constructor(webhook: string) {
    this.webhook = webhook;
  }

  async sendDecisionNotification(decision: DecisionNotification): Promise<void> {
    const emoji = this.getActionEmoji(decision.action);
    await this.send({
      msg_type: 'text',
      content: {
        text: `${emoji} Agent 决策通知\n\n` +
              `动作: ${decision.action}\n` +
              `标的: ${decision.symbol}\n` +
              `理由: ${decision.reason}\n` +
              `置信度: ${decision.confidence}%\n` +
              `时间: ${new Date().toLocaleString('zh-CN')}`
      }
    });
  }

  async sendAlert(alert: AlertNotification): Promise<void> {
    const emoji = this.getAlertEmoji(alert.level);
    await this.send({
      msg_type: 'text',
      content: {
        text: `${emoji} ${alert.title}\n\n` +
              `级别: ${alert.level}\n` +
              `${alert.message}\n` +
              `时间: ${new Date().toLocaleString('zh-CN')}`
      }
    });
  }

  async sendDailyReport(report: DailyReport): Promise<void> {
    await this.send({
      msg_type: 'text',
      content: {
        text: `📊 Agent 每日报告\n\n` +
              `日期: ${report.date}\n` +
              `决策次数: ${report.decisions}\n` +
              `盈亏: ${report.pnl > 0 ? '+' : ''}${report.pnl}\n` +
              `池子数: ${report.pools}\n` +
              `预警: ${report.alerts}\n` +
              `时间: ${new Date().toLocaleString('zh-CN')}`
      }
    });
  }

  async sendError(error: Error): Promise<void> {
    await this.send({
      msg_type: 'text',
      content: {
        text: `❌ Agent 错误通知\n\n` +
              `错误: ${error.message}\n` +
              `堆栈: ${error.stack?.substring(0, 200)}...\n` +
              `时间: ${new Date().toLocaleString('zh-CN')}`
      }
    });
  }

  async sendCustomMessage(message: string): Promise<void> {
    await this.send({
      msg_type: 'text',
      content: {
        text: message
      }
    });
  }

  private async send(body: any): Promise<void> {
    try {
      await axios.post(this.webhook, body, {
        headers: {
          'Content-Type': 'application/json'
        }
      });
    } catch (error) {
      console.error('发送飞书通知失败:', error);
      // 不要抛出错误，避免通知失败影响主流程
    }
  }

  private getActionEmoji(action: string): string {
    const map: Record<string, string> = {
      'create_pool': '🆕',
      'close_pool': '❌',
      'adjust_pool': '⚙️',
      'stop_loss': '🛑',
      'take_profit': '💰'
    };
    return map[action] || '📝';
  }

  private getAlertEmoji(level: string): string {
    const map: Record<string, string> = {
      'critical': '🚨',
      'high': '⚠️',
      'medium': '⚡',
      'low': 'ℹ️'
    };
    return map[level] || '📢';
  }
}
