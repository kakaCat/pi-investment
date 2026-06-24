/**
 * 飞书通知服务
 * 封装飞书 Webhook API，提供统一的消息推送接口
 */
import axios from 'axios';

interface FeishuConfig {
  webhookUrl?: string;
  botToken?: string;
}

interface CardAction {
  label: string;
  url?: string;
  action?: string;
}

interface SendCardOptions {
  title: string;
  content: string;
  urgency?: 'normal' | 'high' | 'critical';
  actions?: CardAction[];
}

interface SendAlertOptions {
  title: string;
  content: string;
  urgency?: 'normal' | 'high' | 'critical';
  actions?: CardAction[];
  mentionUser?: boolean;
}

export class FeishuNotificationService {
  private webhookUrl: string | null = null;
  private botToken: string | null = null;

  constructor(config?: FeishuConfig) {
    this.webhookUrl = config?.webhookUrl || process.env.FEISHU_WEBHOOK_URL || null;
    this.botToken = config?.botToken || process.env.FEISHU_BOT_TOKEN || null;

    if (!this.webhookUrl) {
      console.warn('[Feishu] Webhook URL not configured, notifications disabled');
    }
  }

  /**
   * 检查服务是否可用
   */
  isAvailable(): boolean {
    return this.webhookUrl !== null;
  }

  /**
   * 发送纯文本消息
   */
  async sendText(text: string, mentionAll: boolean = false): Promise<boolean> {
    if (!this.webhookUrl) {
      console.warn('[Feishu] Webhook not configured');
      return false;
    }

    let content = text;
    if (mentionAll) {
      content = `<at user_id="all">所有人</at> ${text}`;
    }

    const payload = {
      msg_type: 'text',
      content: {
        text: content
      }
    };

    return this.send(payload);
  }

  /**
   * 发送富文本卡片
   */
  async sendCard(options: SendCardOptions): Promise<boolean> {
    if (!this.webhookUrl) {
      console.warn('[Feishu] Webhook not configured');
      return false;
    }

    const colorMap = {
      normal: 'blue',
      high: 'orange',
      critical: 'red'
    };

    const color = colorMap[options.urgency || 'normal'];

    const elements: any[] = [
      {
        tag: 'div',
        text: {
          tag: 'lark_md',
          content: options.content
        }
      }
    ];

    // 添加操作按钮
    if (options.actions && options.actions.length > 0) {
      const actionButtons = options.actions.map(action => ({
        tag: 'button',
        text: {
          tag: 'plain_text',
          content: action.label
        },
        type: 'default',
        ...(action.url ? { url: action.url } : {}),
        ...(action.action ? { value: { action: action.action } } : {})
      }));

      elements.push({
        tag: 'action',
        actions: actionButtons
      });
    }

    const payload = {
      msg_type: 'interactive',
      card: {
        header: {
          title: {
            tag: 'plain_text',
            content: options.title
          },
          template: color
        },
        elements
      }
    };

    return this.send(payload);
  }

  /**
   * 发送每日报告
   */
  async sendDailyReport(data: Record<string, any>): Promise<boolean> {
    const date = data.date || new Date().toISOString().split('T')[0];

    const content = `**📈 市场表现**
上证指数: ${data.sh_index_change || 'N/A'}
深证成指: ${data.sz_index_change || 'N/A'}
北向资金: ${data.north_flow || 'N/A'}亿元

**💰 持仓表现**
今日收益: ${data.daily_pnl || 'N/A'}
总收益率: ${data.total_return || 'N/A'}
持仓股票: ${data.position_count || 0}只

**📊 交易信号**
新增信号: ${data.new_signals || 0}个
优质机会: ${data.opportunities || 0}个

${data.risk_alerts && data.risk_alerts.length > 0 ? `**⚠️ 风险提醒**\n${data.risk_alerts.join('\n')}` : ''}`;

    return this.sendCard({
      title: `📊 每日投资报告 - ${date}`,
      content,
      urgency: 'normal',
      actions: [
        { label: '查看详情', url: data.detail_url || '#' },
        { label: '查看信号', url: data.signals_url || '#' }
      ]
    });
  }

  /**
   * 发送每周报告
   */
  async sendWeeklyReport(data: Record<string, any>): Promise<boolean> {
    const week = data.week || 'N/A';

    const content = `**📈 本周表现**
周收益率: ${data.weekly_return || 'N/A'}
最大回撤: ${data.max_drawdown || 'N/A'}
交易胜率: ${data.win_rate || 'N/A'}
累计收益: ${data.cumulative_return || 'N/A'}

**🎯 策略表现**
${this.formatStrategyPerformance(data.strategies || [])}

**🔮 下周展望**
${this.formatOutlook(data.outlook || {})}`;

    return this.sendCard({
      title: `📊 投资周报 - 第${week}周`,
      content,
      urgency: 'normal',
      actions: [
        { label: '查看详情', url: data.detail_url || '#' },
        { label: '导出报告', url: data.export_url || '#' }
      ]
    });
  }

  /**
   * 发送告警通知
   */
  async sendAlert(options: SendAlertOptions): Promise<boolean> {
    return this.sendCard({
      title: options.title,
      content: options.content,
      urgency: options.urgency || 'high',
      actions: options.actions
    });
  }

  /**
   * 发送盘前准备报告
   */
  async sendPremarketReport(data: Record<string, any>): Promise<boolean> {
    const date = data.date || new Date().toISOString().split('T')[0];

    const content = `**✅ 数据检查**
数据完整性: ${data.data_integrity || '正常'}
股票池更新: ${data.pool_updated || '完成'}

**💡 今日机会 (${data.opportunities?.length || 0}个)**
${this.formatOpportunities(data.opportunities || [])}

**📋 今日关注**
${this.formatWatchlist(data.watchlist || [])}`;

    return this.sendCard({
      title: `📋 盘前准备报告 - ${date}`,
      content,
      urgency: 'normal',
      actions: [
        { label: '查看机会', url: data.opportunities_url || '#' },
        { label: '查看持仓', url: data.positions_url || '#' },
        { label: '开始盯盘', action: 'start_monitoring' }
      ]
    });
  }

  /**
   * 发送消息到飞书
   */
  private async send(payload: any): Promise<boolean> {
    if (!this.webhookUrl) {
      return false;
    }

    try {
      const response = await axios.post(this.webhookUrl, payload, {
        headers: { 'Content-Type': 'application/json' },
        timeout: 10000
      });

      const result = (response as any).data;

      if (result.code === 0 || result.StatusCode === 0) {
        console.log('[Feishu] Message sent successfully');
        return true;
      } else {
        console.error('[Feishu] Failed to send message:', result);
        return false;
      }
    } catch (error) {
      console.error('[Feishu] Error sending message:', error);
      return false;
    }
  }

  // 辅助格式化方法
  private formatStrategyPerformance(strategies: any[]): string {
    if (!strategies || strategies.length === 0) {
      return '暂无数据';
    }

    return strategies.slice(0, 3).map((s, i) =>
      `${i + 1}. ${s.name}: ${s.return || 'N/A'}`
    ).join('\n');
  }

  private formatOutlook(outlook: any): string {
    const lines = [];
    if (outlook.market_view) lines.push(`• 市场观点: ${outlook.market_view}`);
    if (outlook.recommendations) lines.push(`• 操作建议: ${outlook.recommendations}`);
    if (outlook.focus_sectors) lines.push(`• 关注板块: ${outlook.focus_sectors}`);
    return lines.length > 0 ? lines.join('\n') : '暂无展望';
  }

  private formatOpportunities(opportunities: any[]): string {
    if (!opportunities || opportunities.length === 0) {
      return '暂无机会';
    }

    return opportunities.slice(0, 5).map(opp =>
      `• ${opp.symbol}: ${opp.reason || 'N/A'}`
    ).join('\n');
  }

  private formatWatchlist(watchlist: string[]): string {
    if (!watchlist || watchlist.length === 0) {
      return '暂无关注';
    }

    return watchlist.slice(0, 10).join(', ');
  }
}

// 全局单例
let feishuServiceInstance: FeishuNotificationService | null = null;

export function getFeishuService(): FeishuNotificationService {
  if (!feishuServiceInstance) {
    feishuServiceInstance = new FeishuNotificationService();
  }
  return feishuServiceInstance;
}

export function initFeishuService(config?: FeishuConfig): FeishuNotificationService {
  feishuServiceInstance = new FeishuNotificationService(config);
  return feishuServiceInstance;
}
