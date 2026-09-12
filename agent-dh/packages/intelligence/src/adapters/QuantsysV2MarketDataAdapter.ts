/**
 * QuantsysV2MarketDataAdapter - MarketDataProvider 实现
 * 
 * 适配器模式：将 QuantsysV2Client 适配为领域层的 MarketDataProvider 接口
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import type {
  MarketDataProvider,
  PriceData,
  TradeExecution,
  Position,
} from '../domain/evaluation/EvaluationStrategy';

export class QuantsysV2MarketDataAdapter implements MarketDataProvider {
  constructor(private readonly qv2Client: QuantsysV2Client) {}
  
  /**
   * 获取价格历史数据
   */
  async getPriceHistory(
    symbol: string,
    startDate: Date,
    days: number
  ): Promise<PriceData[]> {
    try {
      // 计算结束日期
      const endDate = new Date(startDate);
      endDate.setDate(endDate.getDate() + days);
      
      // 格式化日期为 YYYY-MM-DD
      const formatDate = (date: Date): string => {
        return date.toISOString().split('T')[0];
      };
      
      // 调用 quantsys-v2 API
      const response = await this.qv2Client.getKline({
        symbol: symbol,
        start_date: formatDate(startDate),
        end_date: formatDate(endDate),
        period: 'daily',
      });
      
      // 转换为领域模型
      const klines = response?.klines ?? response?.data?.klines ?? [];
      
      return klines.map((k: any) => ({
        date: k.date,
        open: k.open,
        high: k.high,
        low: k.low,
        close: k.close,
        volume: k.volume,
      }));
    } catch (error: any) {
      console.error(`获取价格历史失败: ${symbol}`, error);
      return [];
    }
  }
  
  /**
   * 获取交易执行记录
   */
  async getTradeExecution(
    symbol: string,
    orderId?: string
  ): Promise<TradeExecution | null> {
    try {
      // 如果有 orderId，查询特定订单
      if (orderId) {
        const response = await this.qv2Client.tradeMonitor({
          order_id: orderId,
        });
        
        const order = response?.orders?.[0];
        if (!order || order.status !== 'filled') {
          return null;
        }
        
        return {
          symbol: order.symbol,
          action: order.action,
          quantity: order.quantity,
          avgPrice: order.avg_price ?? order.price,
          fillTime: new Date(order.fill_time ?? order.created_at),
        };
      }
      
      // 否则查询该股票的最近成交
      const response = await this.qv2Client.tradeMonitor({
        account_name: 'agent_virtual',
      });
      
      const orders = response?.orders ?? [];
      const symbolOrders = orders.filter(
        (o: any) => o.symbol === symbol && o.status === 'filled'
      );
      
      if (symbolOrders.length === 0) {
        return null;
      }
      
      // 返回最近的一笔
      const latest = symbolOrders[0];
      return {
        symbol: latest.symbol,
        action: latest.action,
        quantity: latest.quantity,
        avgPrice: latest.avg_price ?? latest.price,
        fillTime: new Date(latest.fill_time ?? latest.created_at),
      };
    } catch (error: any) {
      console.error(`获取交易执行记录失败: ${symbol}`, error);
      return null;
    }
  }
  
  /**
   * 获取当前持仓
   */
  async getCurrentPosition(
    symbol: string,
    accountName: string = 'agent_virtual'
  ): Promise<Position | null> {
    try {
      const response = await this.qv2Client.getPositionList({
        account_name: accountName,
      });
      
      const positions = response?.positions ?? response ?? [];
      const position = positions.find((p: any) => p.symbol === symbol);
      
      if (!position) {
        return null;
      }
      
      return {
        symbol: position.symbol,
        quantity: position.quantity ?? position.shares,
        avgCost: position.avgCost ?? position.avg_cost ?? position.cost_price,
        currentPrice: position.currentPrice ?? position.current_price ?? position.price,
        pnl: position.profitLoss ?? position.pnl ?? position.profit_loss,
        pnlPct: position.profitLossPct ?? position.pnl_pct ?? position.profit_loss_pct,
      };
    } catch (error: any) {
      console.error(`获取持仓失败: ${symbol}`, error);
      return null;
    }
  }
}
