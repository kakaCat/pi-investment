/**
 * Wake Channel - quantsys-v2 推送通知渠道
 *
 * 架构：
 * quantsys-v2 HTTP 推送 → wake-channel.ts → ChannelSessionManager → Agent Session → 执行工具
 *
 * 与飞书渠道对等，都通过 ChannelSessionManager 统一管理 Agent Session
 */
import express from 'express';
import cors from 'cors';
import { join } from 'path';
import { existsSync, mkdirSync } from 'fs';
import { ChannelSessionManager, type ChannelAgentSession } from './channel-session-manager.js';
import { SessionManager, type Skill, loadSkills } from "../sdk-facade.js";
import { createTrackedSession } from "../infrastructure/session/session-factory.js";
import { allCustomTools, initMemoryTools } from "../infrastructure/tools/index.js";
import type { ToolDefinition } from "../infrastructure/tools/index.js";
import { setPlanToolContext } from "../infrastructure/tools/agent/plan-tool.js";
import { createModel, paths } from "../config/config.js";
import {
  autoRecall,
  buildAgentSystemPrompt,
  readDailyMemory,
} from "../core/agent/system-prompt.js";
import { setSessionDataDir } from "../infrastructure/tools/shared/session-utils.js";
import {
  setSystemPrompt,
  getMessages,
  getMessageCount,
  hasState,
} from "../core/agent/session-adapter.js";
import * as logger from "../infrastructure/logging/observable-logger.js";

const WAKE_SESSIONS_DIR = join(paths.piDir, "wake-sessions");

function ensureWakeDir(): void {
  if (!existsSync(WAKE_SESSIONS_DIR)) {
    mkdirSync(WAKE_SESSIONS_DIR, { recursive: true });
  }
}

function loadProjectSkills(): Skill[] {
  try {
    // @ts-ignore - Type mismatch from SDK update
    const result = loadSkills({
      cwd: paths.root,
      skillPaths: [paths.skillsDir],
      agentDir: paths.root,
      includeDefaults: true
    });
    return result.skills;
  } catch (error) {
    console.warn("⚠️ Skills 加载失败:", error instanceof Error ? error.message : String(error));
    return [];
  }
}

/**
 * 创建 Wake Channel 的 HTTP Server
 */
export function startWakeChannel(port: number = 3001): { shutdown: () => void } {
  ensureWakeDir();

  const skills = loadProjectSkills();
  const wakeTools: ToolDefinition[] = [...allCustomTools] as ToolDefinition[];
  console.log(`[Wake] 已加载 ${wakeTools.length} 个工具, feishu_notify: ${wakeTools.some(t => t.name === 'feishu_notify') ? '✅' : '❌'}`);
  initMemoryTools(paths.piDir);
  setPlanToolContext(wakeTools);

  // 创建 Channel Session Manager
  const channelManager = new ChannelSessionManager({
    channelName: "Wake",
    sessionsRootDir: WAKE_SESSIONS_DIR,
    createSession: async (sessionId: string, sessionDir: string) => {
      console.log(`📋 [Wake] 创建会话: ${sessionId}`);

      const trackedSession = await createTrackedSession({
        agentType: "subagent",
        createOptions: {
          cwd: paths.root,
          sessionManager: SessionManager.continueRecent(paths.root, sessionDir),
          model: createModel(),
          systemPrompt: () => buildAgentSystemPrompt({
            memoryContext: "",
            dailyMemory: "",
            tools: wakeTools,
            workspaceDir: paths.root,
          }),
          customTools: wakeTools,
          skills,
        },
      });

      return trackedSession as unknown as ChannelAgentSession;
    },
    beforePrompt: async (session, sessionId, text, sessionDir) => {
      if (sessionDir) setSessionDataDir(sessionDir);

      const memoryContext = autoRecall(text);
      const dailyMemory = readDailyMemory(paths.piDir);
      const systemPrompt = buildAgentSystemPrompt({
        memoryContext,
        dailyMemory,
        tools: wakeTools,
        workspaceDir: paths.root,
      });

      if (hasState(session)) {
        setSystemPrompt(session, systemPrompt);
        logger.logSystemPrompt(systemPrompt, getMessageCount(session));
      }
    },
  });

  // 创建 Express App
  const app = express();
  app.use(cors({ origin: process.env.CORS_ORIGIN || '*' }));
  app.use(express.json());

  // 请求日志
  app.use((req, res, next) => {
    console.log(`[Wake] ${req.method} ${req.path}`);
    next();
  });

  /**
   * POST /wake
   * quantsys-v2 推送通知的入口
   */
  app.post('/wake', async (req, res) => {
    const { event, task_id, task_name, data, session_id } = req.body;

    if (!event || !data) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: event, data'
      });
    }

    // 使用 session_id 或默认为 "default"
    const sessionId = session_id || 'default';
    const messageId = `wake-${event}-${Date.now()}`;

    console.log(`📬 [Wake] 收到事件: ${event} (task: ${task_name || task_id}, session: ${sessionId})`);

    try {
      // 构造 Agent 提示词
      const promptText = buildPromptFromEvent(event, task_id, task_name, data);

      // 通过 ChannelSessionManager 处理消息，Agent 会调用 feishu_notify 工具
      const reply = await channelManager.processMessage(sessionId, messageId, promptText);

      console.log(`✅ [Wake] 事件处理完成: ${event}`);
      res.json({
        success: true,
        event,
        session_id: sessionId,
        reply: reply.substring(0, 500) // 限制返回长度
      });

    } catch (error) {
      console.error(`❌ [Wake] 事件处理失败:`, error);
      res.status(500).json({
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  });

  /**
   * POST /wake/abort
   * 中断某个会话的处理
   */
  app.post('/wake/abort', async (req, res) => {
    const { session_id } = req.body;
    const sessionId = session_id || 'default';

    try {
      const aborted = await channelManager.abort(sessionId);
      res.json({
        success: true,
        aborted,
        message: aborted ? '已中断当前任务' : '当前没有运行中的任务'
      });
    } catch (error) {
      res.status(500).json({
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  });

  /**
   * GET /wake/health
   * 健康检查
   */
  app.get('/wake/health', (req, res) => {
    res.json({
      status: 'ok',
      channel: 'wake',
      timestamp: new Date().toISOString()
    });
  });

  // 启动服务器
  const server = app.listen(port, () => {
    console.log(`🔔 Wake Channel 启动: http://127.0.0.1:${port}`);
    console.log(`📬 接收推送: POST http://127.0.0.1:${port}/wake`);
    console.log(`🛑 中断任务: POST http://127.0.0.1:${port}/wake/abort`);
    console.log(`💚 健康检查: GET http://127.0.0.1:${port}/wake/health`);
  });

  return {
    shutdown: () => {
      console.log("🛑 [Wake] 关闭服务器...");
      server.close();
    }
  };
}

/**
 * 直接发送飞书通知（不依赖 Agent 调用工具）
 */
/**
 * 根据事件类型构造 Agent 提示词
 */
function buildPromptFromEvent(
  event: string,
  task_id?: number,
  task_name?: string,
  data?: Record<string, any>
): string {
  const taskInfo = task_name || task_id || 'unknown';

  switch (event) {
    case 'strategy_rotation':
      return `【策略轮动决策】V2 检测到策略轮动需求。

市场风格: ${data?.market_style || 'N/A'}，置信度: ${data?.confidence || 'N/A'}
触发原因: ${data?.trigger || 'N/A'}

请按以下决策链操作（每步都要看返回结果再决定下一步）：

1. 调用 rotation_proposal 获取轮动方案
   → 看市场风格是否可信、策略表现数据

2. 如需独立验证，调用 market_style_detect 交叉确认
   → 对比 V2 的风格判断和你自己的分析

3. 调用 rotation_simulate 模拟执行
   → 检查模拟交易是否合理、风险变化是否可接受

4. 基于以上信息做决策：
   - 同意 → 调用 rotation_execute (decision="approve")
   - 部分同意 → 修改 actions 后执行
   - 否决 → 调用 rotation_execute (decision="reject", reason="...")

5. 调用 decision_record 记录你的决策原因和预期

6. 通过 feishu_notify 通知用户轮动结果

注意：不要跳过步骤直接执行。每一步的返回数据都是你决策的依据。`;

    case 'daily_review':
      return `【盘后复盘】今日交易已结束（${data?.trade_date || '今日'}）。

今日绩效: ${JSON.stringify(data?.performance || {})}

请按以下步骤复盘：

1. 调用 portfolio_status({ action: 'list' }) 查看各账户，再 get 查看今日持仓和盈亏
2. 调用 performance_analyzer 分析今日绩效
3. 调用 rotation_verify 检查近期轮动效果
4. 调用 decision_history 回顾今日决策
5. 综合分析：
   - 哪些决策正确？为什么？
   - 哪些决策失误？如何改进？
   - 明日操作方向建议
6. 调用 experience_write 写入经验
7. 通过 feishu_notify 发送复盘报告`;

    case 'market_alert':
      return `【市场异动】上证 ${data?.sh_change || 'N/A'}，深证 ${data?.sz_change || 'N/A'}，${data?.reason || ''}

请按以下工具链操作：

1. 调用 portfolio_status({ action: 'list' }) 查看各账户持仓受影响情况
2. 调用 market_style_detect 判断市场风格是否变化
3. 调用 data_fetch_market_sentiment 查看市场情绪
4. 综合判断：
   - 如果是大跌且风格转空 → 考虑调用 portfolio_trade（须指定 account）减仓
   - 如果是超跌且风格未变 → 调用 opportunity_scan 扫描机会
5. 调用 decision_record 记录你的判断
6. 通过 feishu_notify 发送分析报告（包含：发生了什么、原因、情绪、机会、建议）

不要只报告数据，要做真正的投资分析。`;

    case 'daily_report':
      return `生成每日投资报告（任务：${taskInfo}）。请使用 daily_report 工具生成报告，然后通过 feishu_notify 推送。`;

    case 'weekly_report':
      return `生成每周投资报告（任务：${taskInfo}）。请汇总本周数据并通过 feishu_notify 推送报告。`;

    case 'position_alert':
      return `持仓告警：${data?.symbol || '股票'}触发${data?.alert_type === 'stop_loss' ? '止损' : '止盈'}。当前价格：${data?.current_price}，成本价：${data?.cost_price}。请使用 feishu_notify 推送告警。`;

    case 'signal_generated':
      return `新交易信号生成（任务：${taskInfo}）。生成了 ${data?.signal_count || 0} 个新信号。请使用 feishu_notify 推送信号通知。`;

    case 'premarket_report':
      return `生成盘前准备报告（任务：${taskInfo}）。请分析今日市场预期并通过 feishu_notify 推送。`;

    default:
      return `收到 quantsys-v2 推送事件：${event}（任务：${taskInfo}）。数据：${JSON.stringify(data || {}, null, 2)}。请根据事件类型执行相应操作。`;
  }
}
