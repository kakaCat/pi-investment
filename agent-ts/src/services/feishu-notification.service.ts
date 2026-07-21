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

    // 使用真实的数据字段（来自 portfolio_status 和其他工具）
    const totalAssets = data.total_assets !== undefined ? `¥${Number(data.total_assets).toFixed(2)}` : 'N/A';
    const cash = data.cash !== undefined ? `¥${Number(data.cash).toFixed(2)}` : 'N/A';
    const holdingsCount = data.holdings_count !== undefined ? `${data.holdings_count}只` : 'N/A';
    const totalPnl = data.total_pnl !== undefined ? `¥${Number(data.total_pnl).toFixed(2)}` : 'N/A';
    const totalPnlPct = data.total_pnl_pct !== undefined ? `${Number(data.total_pnl_pct).toFixed(2)}%` : 'N/A';

    const content = `**💰 持仓表现**
总资产: ${totalAssets}
可用资金: ${cash}
持仓数量: ${holdingsCount}
总盈亏: ${totalPnl} (${totalPnlPct})

**📊 交易情况**
${data.trades_today !== undefined ? `今日交易: ${data.trades_today}笔` : ''}
${data.buy_count !== undefined ? `买入: ${data.buy_count}笔` : ''}
${data.sell_count !== undefined ? `卖出: ${data.sell_count}笔` : ''}

**💡 关键发现**
${data.key_findings || '正常运行，无异常'}`;

    return this.sendCard({ title: `📊 每日投资报告 - ${date}`, content });
  }

  async sendWeeklyReport(data: Record<string, any>): Promise<boolean> {
    const week = data.week || new Date().toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' });

    const weeklyReturn = data.weekly_return !== undefined ? `${Number(data.weekly_return).toFixed(2)}%` : 'N/A';
    const winRate = data.win_rate !== undefined ? `${Number(data.win_rate).toFixed(2)}%` : 'N/A';
    const cumulativeReturn = data.total_pnl_pct !== undefined ? `${Number(data.total_pnl_pct).toFixed(2)}%` : 'N/A';
    const totalTrades = data.total_trades !== undefined ? data.total_trades : 'N/A';

    const content = `**📈 本周表现**
周收益: ${weeklyReturn}
交易次数: ${totalTrades}
胜率: ${winRate}
累计收益: ${cumulativeReturn}

**📊 持仓状况**
总资产: ${data.total_assets !== undefined ? `¥${Number(data.total_assets).toFixed(2)}` : 'N/A'}
持仓数: ${data.holdings_count || 0}只

**💡 本周总结**
${data.summary || '继续观察市场，保持策略纪律'}`;

    return this.sendCard({ title: `📊 投资周报 - ${week}`, content });
  }

  async sendAlert(opts: AlertOptions): Promise<boolean> {
    return this.sendCard(opts);
  }

  async sendPremarketReport(data: Record<string, any>): Promise<boolean> {
    const date = data.date || new Date().toISOString().split('T')[0];

    const opportunities = data.opportunities || [];
    const opportunitiesText = opportunities.length > 0
      ? opportunities.map((o: any) => `• ${o.symbol} ${o.name || ''}: ${o.reason || '待分析'}`).join('\n')
      : '暂无高质量信号';

    const alerts = data.alerts || [];
    const alertsText = alerts.length > 0
      ? alerts.map((a: any) => `⚠️ ${a.title}: ${a.message}`).join('\n')
      : '无预警';

    const content = `**✅ 数据检查**
数据完整性: ${data.data_integrity || '正常'}
股票池: ${data.pools_count || 0}个
最新更新: ${data.last_update || '未知'}

**💡 今日机会**
${opportunitiesText}

**⚠️ 风险提示**
${alertsText}

**📊 持仓状况**
可用资金: ${data.cash !== undefined ? `¥${Number(data.cash).toFixed(2)}` : 'N/A'}
持仓数: ${data.holdings_count || 0}只`;

    return this.sendCard({ title: `🌅 盘前准备 - ${date}`, content });
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
