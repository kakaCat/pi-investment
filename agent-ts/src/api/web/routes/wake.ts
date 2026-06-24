/**
 * Wake API - V2 唤醒 Agent 推送通知
 *
 * 架构说明：
 * Wake API 是 Web Server 的独立 HTTP 端点，直接调用工具完成任务。
 * 不需要经过 Agent Session，因为 Web Server 本身就是独立服务。
 */
import { Router } from 'express';
import type { Request, Response } from 'express';

const router = Router();

interface WakeEvent {
  event: string;
  task_id?: number;
  task_name?: string;
  data: Record<string, any>;
  timestamp?: string;
}

/**
 * V2 唤醒 Agent 的主接口
 * POST /api/wake
 */
router.post('/wake', async (req: Request, res: Response) => {
  const { event, task_id, task_name, data }: WakeEvent = req.body;

  console.log(`[Wake] Received event: ${event} (task: ${task_name || task_id})`);

  try {
    // TODO: Fix feishu-notify-tool import issue
    console.warn('[Wake] Feishu notification temporarily disabled due to build issues');

    res.json({
      success: true,
      message: 'Event received but notification temporarily disabled',
      event,
      task_id,
      task_name
    });

  } catch (error) {
    console.error(`[Wake] Error handling event ${event}:`, error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * 构建市场异动消息内容
 */
function buildMarketAlertContent(data: Record<string, any>): string {
  const shChange = data.sh_change ? (data.sh_change * 100).toFixed(2) : 'N/A';
  const szChange = data.sz_change ? (data.sz_change * 100).toFixed(2) : 'N/A';

  return `**市场异动检测**
上证指数: ${shChange}%
深证成指: ${szChange}%
时间: ${data.timestamp || new Date().toISOString()}

${data.reason ? `**原因**: ${data.reason}` : ''}`;
}

/**
 * 构建持仓告警消息内容
 */
function buildPositionAlertContent(data: Record<string, any>): string {
  const pnlPct = data.pnl_pct ? (data.pnl_pct * 100).toFixed(2) : 'N/A';

  return `**持仓信息**
股票代码: ${data.symbol}
当前价格: ${data.current_price}
成本价格: ${data.cost_price}
盈亏: ${pnlPct}%

${data.reason ? `**原因**: ${data.reason}` : ''}`;
}

/**
 * 构建信号消息内容
 */
function buildSignalContent(data: Record<string, any>): string {
  return `**交易信号生成**
新增信号: ${data.signal_count || 0} 个

${data.signals ? data.signals.map((s: any) =>
  `• ${s.symbol}: ${s.type} (评分: ${s.score})`
).join('\n') : ''}`;
}

/**
 * 健康检查接口
 * GET /api/wake/health
 */
router.get('/wake/health', (req: Request, res: Response) => {
  res.json({
    status: 'ok',
    service: 'wake-api',
    architecture: 'Web Server Independent Endpoint',
    timestamp: new Date().toISOString()
  });
});

export { router as wakeRouter };
