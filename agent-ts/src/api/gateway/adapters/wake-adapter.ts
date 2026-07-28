/**
 * WakeAdapter — quantsys-v2 HTTP 推送通道
 * POST /wake (X-Wake-Token 鉴权) → InboundEvent → Gateway.dispatch
 */
import express, { type Express } from "express";
import cors from "cors";
import type { Server } from "http";
import type { ChannelAdapter, GatewayHandlers, InboundEvent } from "../types.js";

export interface WakeAdapterOptions {
  port?: number;    // 默认 3002
  token?: string;   // WAKE_TOKEN；未配置时放行 + 警告（dev 模式）
}

export class WakeAdapter implements ChannelAdapter {
  readonly name = "wake";
  private server: Server | null = null;
  private readonly port: number;
  private readonly token?: string;

  constructor(options: WakeAdapterOptions = {}) {
    this.port = options.port ?? (process.env.WAKE_CHANNEL_PORT ? parseInt(process.env.WAKE_CHANNEL_PORT) : 3002);
    this.token = options.token ?? process.env.WAKE_TOKEN;
  }

  start(handlers: GatewayHandlers): void {
    const app: Express = express();
    app.use(cors({ origin: process.env.CORS_ORIGIN || "*" }));
    app.use(express.json());

    // token 鉴权中间件（/wake/health 公开）
    app.use((req, res, next) => {
      if (req.path === "/wake/health") return next();
      if (!this.token) return next();
      if (req.headers["x-wake-token"] === this.token) return next();
      res.status(401).json({ success: false, error: "Unauthorized: invalid or missing X-Wake-Token" });
    });

    app.post("/wake", async (req, res) => {
      const { event, task_id, task_name, data, session_id } = req.body;
      if (!event || !data) {
        return res.status(400).json({ success: false, error: "Missing required fields: event, data" });
      }

      const inbound: InboundEvent = {
        channel: "wake",
        peerId: session_id || "default",
        messageId: `wake-${event}-${Date.now()}`,
        text: buildPromptFromEvent(event, task_id, task_name, data),
        event,
        data,
      };

      console.log(`📬 [Wake] 收到事件: ${event} (task: ${task_name || task_id})`);
      try {
        const reply = await handlers.dispatch(inbound);
        res.json({ success: true, event, session_id: inbound.peerId, reply: reply.substring(0, 500) });
      } catch (error) {
        console.error(`❌ [Wake] 事件处理失败:`, error);
        res.status(500).json({ success: false, error: error instanceof Error ? error.message : "Unknown error" });
      }
    });

    app.post("/wake/abort", async (req, res) => {
      const sessionId = req.body?.session_id || "default";
      const aborted = await handlers.abort(`agent:main:wake:${sessionId}`);
      res.json({ success: true, aborted, message: aborted ? "已中断当前任务" : "当前没有运行中的任务" });
    });

    app.get("/wake/health", (_req, res) => {
      res.json({ status: "ok", channel: "wake", timestamp: new Date().toISOString() });
    });

    this.server = app.listen(this.port, () => {
      console.log(`🔔 Wake Channel 启动: http://127.0.0.1:${this.port}`);
      if (!this.token) {
        console.warn(`⚠️ [Wake] WAKE_TOKEN 未配置，/wake 无鉴权（仅建议开发环境）`);
      }
    });
  }

  shutdown(): void {
    this.server?.close();
    this.server = null;
  }
}

/** 根据事件类型构造 Agent 提示词（规范化逻辑，adapter 内部职责） */
export function buildPromptFromEvent(
  event: string,
  task_id?: number,
  task_name?: string,
  data?: Record<string, any>,
): string {
  const taskInfo = task_name || task_id || "unknown";

  switch (event) {
    case "market_alert":
      return `【任务】请按以下步骤处理市场异动：

1. 分析当前市场数据：上证 ${data?.sh_change || "N/A"}，深证 ${data?.sz_change || "N/A"}，${data?.reason || ""}。
2. 用 market_sentiment 工具查看市场情绪。
3. 如果是大跌，用 opportunity_scan 扫描超跌机会。
4. 综合以上信息，用 feishu_notify 工具给用户发送一份完整的分析报告，内容包括：
   - 市场发生了什么
   - 原因分析
   - 情绪面判断
   - 发现的投资机会
   - 操作建议

不要只报告数据，要做真正的投资分析，所有分析结果必须通过飞书发送给用户。`;

    case "daily_report":
      return `生成每日投资报告（任务：${taskInfo}）。请使用 daily_report 工具生成报告，然后通过 feishu_notify 推送。`;

    case "weekly_report":
      return `生成每周投资报告（任务：${taskInfo}）。请汇总本周数据并通过 feishu_notify 推送报告。`;

    case "position_alert":
      return `持仓告警：${data?.symbol || "股票"}触发${data?.alert_type === "stop_loss" ? "止损" : "止盈"}。当前价格：${data?.current_price}，成本价：${data?.cost_price}。请使用 feishu_notify 推送告警。`;

    case "signals_ready": {
      const signalList: any[] = data?.signals || [];
      const signalLines = signalList.length > 0
        ? signalList.map((s: any, i: number) =>
            `${i + 1}. [ID:${s.id ?? "N/A"}] ${s.symbol || "N/A"} ${s.signal_type || ""} 强度:${s.strength ?? "N/A"} 策略:${s.strategy_name || s.strategy || "N/A"}`
          ).join("\n")
        : "（今日无信号）";
      return `【今日信号就绪】${data?.trade_date || "今日"} V2 已生成 ${data?.signal_count ?? signalList.length} 个待处理信号。

信号列表:
${signalLines}

你操作的唯一账本是 agent_virtual。请按以下决策链操作（每步都要看返回结果再决定下一步）：

1. 调用 decision_history 检查今日是否已处理过这些信号
   → 按信号 ID 判重：已决策过的信号直接跳过（本事件可能因兜底机制重推）
2. 调用 portfolio_status({ action: 'get', account: 'agent_virtual' }) 查看持仓与可用资金
3. 逐信号评估：是否已持仓？与现有持仓是否同板块重复？信号强度是否 ≥70？
4. 决定买入的信号：调用 portfolio_trade({ account: 'agent_virtual', action: 'buy', symbol, amount, reason })
   → reason 必须 ≥10 字，引用信号 ID 和理由
   → 服务端硬护栏：单股≤30%、最多3只、总仓≤80%、单日买入≤5笔、单日买入≤总资产50%
   → 交易时段：A股只有 9:30-11:30 / 13:00-15:00 能成交；当前若未到 9:30，
     先完成评估并 decision_record 记录"待开盘执行"，等开盘后再下单，不要反复重试
   → 被护栏拒绝时：decision_record 记录原因，降仓位最多重试一次，不要反复重试
5. 放弃的信号：调用 decision_record 记录放弃理由（这也是学习数据）
6. 全部处理完：调用 experience_write 写今日信号处理摘要，feishu_notify 通知用户（处理了几条、买了什么、放弃了什么）

注意：不要因为信号多就全买。没有把握就全部放弃并记录理由——空仓也是合法决策。`;
    }

    case "signal_generated":
      return `新交易信号生成（任务：${taskInfo}）。生成了 ${data?.signal_count || 0} 个新信号。请使用 feishu_notify 推送信号通知。`;

    case "premarket_report":
      return `生成盘前准备报告（任务：${taskInfo}）。请分析今日市场预期并通过 feishu_notify 推送。`;

    case "watch_triggered":
      return `【盯盘触发】${data?.name || ""}(${data?.symbol || "N/A"}) ${data?.message || "监视条件触发"}

当前价格: ${data?.price ?? "N/A"}，涨跌幅: ${data?.change_pct ?? "N/A"}%${data?.pnl_pct != null ? `，持仓盈亏: ${data.pnl_pct}%` : ""}
触发条件: ${JSON.stringify(data?.condition || {})}
你当时的监视理由: ${data?.context || "（未填写）"}

请按以下决策链操作（每步都要看返回结果再决定下一步）：

1. 回顾你的监视理由（上面的 context），判断这次触发意味着什么
2. 调用 portfolio_status({ action: 'list' }) 确认是否持有该股票及仓位
3. 如需最新行情细节，调用 data_fetch_quote 补充
4. 做出决策：
   - 止损/止盈卖出 → 调用 portfolio_trade（须指定 account）
   - 继续持有观察 → 调用 watch_manage({ action: 'update', rule_id: ${data?.rule_id ?? "<rule_id>"}, ... }) 调整阈值或条件
   - 监视目的已达成 → 调用 watch_manage({ action: 'remove', rule_id: ${data?.rule_id ?? "<rule_id>"} }) 删除规则；若仍想继续监视则保留（同一条件有冷却期，不会立刻重复触发）
5. 调用 decision_record 记录决策原因
6. 通过 feishu_notify 通知用户（触发原因 + 你的决策）

注意：不要无视触发。即使决定不操作，也要明确记录"为什么不操作"。`;

    case "agent_reminder":
      return `【提醒】${data?.message || "你有一个提醒"}。请按提醒内容执行相应操作，必要时通过 feishu_notify 告知用户。`;

    default:
      return `收到 quantsys-v2 推送事件：${event}（任务：${taskInfo}）。数据：${JSON.stringify(data || {}, null, 2)}。请根据事件类型执行相应操作。`;
  }
}
