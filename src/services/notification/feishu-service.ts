/**
 * FeishuService - 飞书通知服务
 * 通过飞书 WebSocket 发送交易信号
 */

export interface TradeSignal {
  action: 'buy' | 'sell';
  symbol: string;
  name: string;
  price: number;
  reason: string;
  confidence: number;
  position_pct?: number;
}

export class FeishuService {
  private chatId: string;

  constructor(chatId?: string) {
    this.chatId = chatId || process.env.FEISHU_CHAT_ID || '';
    if (!this.chatId) {
      console.warn('[Feishu] FEISHU_CHAT_ID not configured');
    }
  }

  async sendTradeAlert(signal: TradeSignal): Promise<void> {
    if (!this.chatId) {
      console.log('[Feishu] 跳过通知（未配置 chatId）:', signal);
      return;
    }

    const message = this.formatSignal(signal);

    // TODO: 通过飞书 WebSocket 发送消息
    // 这里需要调用你现有的飞书发送接口
    console.log(`[Feishu] 发送信号到 ${this.chatId}:`, message);
  }

  private formatSignal(signal: TradeSignal): string {
    const emoji = signal.action === 'buy' ? '🟢' : '🔴';
    const action = signal.action === 'buy' ? '买入' : '卖出';

    let msg = `${emoji} **${action}信号**\n\n`;
    msg += `**${signal.name}** (${signal.symbol})\n`;
    msg += `当前价: ¥${signal.price}\n`;
    msg += `置信度: ${(signal.confidence * 100).toFixed(0)}%\n\n`;
    msg += `**分析理由**\n${signal.reason}`;

    if (signal.position_pct) {
      msg += `\n\n建议仓位: ${signal.position_pct}%`;
    }

    return msg;
  }
}
