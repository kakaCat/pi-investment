/**
 * 飞书通知服务
 */
import axios from 'axios';

interface FeishuConfig {
  webhookUrl?: string;
}

interface CardOptions {
  title: string;
  content: string;
  urgency?: string;
  actions?: any[];
}

interface AlertOptions extends CardOptions {
  mentionUser?: boolean;
}

export class FeishuNotificationService {
  private webhookUrl: string | null;

  constructor(config?: FeishuConfig) {
    this.webhookUrl = config?.webhookUrl || process.env.FEISHU_WEBHOOK_URL || null;
  }

  isAvailable(): boolean {
    return !!this.webhookUrl;
  }

  async sendText(text: string, mentionAll = false): Promise<boolean> {
    if (!this.webhookUrl) return false;
    const content = mentionAll ? `<at user_id="all">所有人</at> ${text}` : text;
    return this.send({ msg_type: 'text', content: { text: content } });
  }

  async sendCard(opts: CardOptions): Promise<boolean> {
    if (!this.webhookUrl) return false;
    const colors: Record<string, string> = { normal: 'blue', high: 'orange', critical: 'red' };
    const color = colors[opts.urgency || 'normal'] || 'blue';

    const elements: any[] = [{
      tag: 'div',
      text: { tag: 'lark_md', content: opts.content }
    }];

    if (opts.actions?.length) {
      elements.push({
        tag: 'action',
        actions: opts.actions.map(a => ({
          tag: 'button',
          text: { tag: 'plain_text', content: a.label },
          type: 'default',
          ...(a.url ? { url: a.url } : {}),
        }))
      });
    }

    return this.send({
      msg_type: 'interactive',
      card: {
        header: { title: { tag: 'plain_text', content: opts.title }, template: color },
        elements
      }
    });
  }

  async sendDailyReport(data: Record<string, any>): Promise<boolean> {
    const date = data.date || new Date().toISOString().split('T')[0];
    const content = `**📈 市场表现**
上证指数: ${data.sh_index_change || 'N/A'}
深证成指: ${data.sz_index_change || 'N/A'}
北向资金: ${data.north_flow || 'N/A'}

**💰 持仓表现**
今日收益: ${data.daily_pnl || 'N/A'}
总收益率: ${data.total_return || 'N/A'}
新增信号: ${data.new_signals || 0}个`;
    return this.sendCard({ title: `📊 每日投资报告 - ${date}`, content });
  }

  async sendWeeklyReport(data: Record<string, any>): Promise<boolean> {
    const week = data.week || 'N/A';
    const content = `**📈 本周表现**
周收益: ${data.weekly_return || 'N/A'}
胜率: ${data.win_rate || 'N/A'}
累计: ${data.cumulative_return || 'N/A'}`;
    return this.sendCard({ title: `📊 投资周报 - 第${week}周`, content });
  }

  async sendAlert(opts: AlertOptions): Promise<boolean> {
    return this.sendCard(opts);
  }

  async sendPremarketReport(data: Record<string, any>): Promise<boolean> {
    const date = data.date || new Date().toISOString().split('T')[0];
    const content = `**✅ 数据检查**
数据完整性: ${data.data_integrity || '正常'}
股票池: ${data.pool_updated || '已更新'}

**💡 今日机会**
${(data.opportunities || []).map((o: any) => `• ${o.symbol}: ${o.reason}`).join('\n') || '暂无'}`;
    return this.sendCard({ title: `📋 盘前准备 - ${date}`, content });
  }

  private async send(payload: any): Promise<boolean> {
    if (!this.webhookUrl) {
      console.log('[Feishu] Webhook 未配置，跳过发送');
      return false;
    }
    try {
      console.log(`[Feishu] 发送中... (${payload.msg_type})`);
      const r = await axios.post(this.webhookUrl, payload, {
        headers: { 'Content-Type': 'application/json' },
        timeout: 10000,
      });
      const ok = r.data?.code === 0 || r.data?.StatusCode === 0;
      console.log(`[Feishu] 结果: ${ok ? '✅ 成功' : '❌ 失败'} (code=${r.data?.code ?? r.data?.StatusCode})`);
      return ok;
    } catch (e: any) {
      console.log(`[Feishu] ❌ 异常: ${e.message}`);
      return false;
    }
  }
}

let instance: FeishuNotificationService | null = null;

export function getFeishuService(): FeishuNotificationService {
  if (!instance) {
    instance = new FeishuNotificationService();
  }
  return instance;
}
