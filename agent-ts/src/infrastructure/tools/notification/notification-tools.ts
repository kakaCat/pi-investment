/**
 * 通知工具 - 使用 Agent OS 通知系统
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { exec } from "child_process";
import { promisify } from "util";

const execAsync = promisify(exec);

export const notificationSendTool: ToolDefinition = {
  name: "notification_send",
  label: "发送通知",
  description: `通过 Agent OS 通知系统发送消息到指定渠道。

可用渠道：
- trading: 交易群（交易信号、执行确认、盘前/盘后报告）
- alerts: 告警群（风险预警、系统异常、紧急告警）
- reports: 报告群（日报、周报、月报）

使用场景：
- 盘前准备报告 → trading
- 交易信号触发 → alerts
- 每日总结报告 → reports
- 风险预警 → alerts

注意：
1. 内容使用 Markdown 格式
2. 根据重要程度选择合适的颜色
3. 标题简短有力（<50 字）
4. 内容清晰易读（<500 字为佳）`,

  parameters: Type.Object({
    channel: Type.Union([
      Type.Literal('trading'),
      Type.Literal('alerts'),
      Type.Literal('reports')
    ], { description: "渠道代码" }),

    title: Type.String({ description: "消息标题（简短有力）" }),

    content: Type.String({ description: "消息内容（支持 Markdown 格式）" }),

    color: Type.Optional(Type.Union([
      Type.Literal('blue'),
      Type.Literal('green'),
      Type.Literal('red'),
      Type.Literal('orange'),
      Type.Literal('grey'),
      Type.Literal('purple')
    ], { description: "卡片颜色（blue=信息，green=成功，red=告警，orange=警告）", default: 'blue' })),
  }),

  execute: async (_toolCallId, params: any) => {
    try {
      const { channel, title, content, color = 'blue' } = params;

      // Agent OS 二进制路径
      const agentOsBin = process.env.AGENT_OS_BIN || '../agent-os/agent-os';

      // 转义引号
      const escapedTitle = title.replace(/"/g, '\\"');
      const escapedContent = content.replace(/"/g, '\\"');

      // 构建命令
      const cmd = `${agentOsBin} notify send --channel ${channel} --title "${escapedTitle}" --content "${escapedContent}" --color ${color}`;

      // 执行命令
      const { stdout, stderr } = await execAsync(cmd, {
        env: {
          ...process.env,
          PGDATABASE: process.env.PGDATABASE || 'quant_investment'
        },
        cwd: process.cwd()
      });

      // 检查错误
      if (stderr && stderr.includes('Failed')) {
        return {
          content: [{ type: "text" as const, text: `❌ 发送失败: ${stderr}` }],
          details: { success: false, error: stderr }
        };
      }

      // 解析 log ID
      const logIdMatch = stdout.match(/Log ID: ([a-f0-9-]+)/);
      const logId = logIdMatch ? logIdMatch[1] : '';

      const message = `✅ 通知已发送到 ${channel} 群${logId ? `（日志ID: ${logId.substring(0, 8)}...）` : ''}`;

      return {
        content: [{ type: "text" as const, text: message }],
        details: { success: true, logId, channel }
      };
    } catch (error) {
      const err = error instanceof Error ? error.message : 'Unknown error';
      return {
        content: [{ type: "text" as const, text: `❌ 发送失败: ${err}` }],
        details: { success: false, error: err }
      };
    }
  }
};

export const notificationListChannelsTool: ToolDefinition = {
  name: "notification_list_channels",
  label: "查询通知渠道",
  description: "查询可用的通知渠道列表及其状态",

  parameters: Type.Object({}),

  execute: async (_toolCallId, _params: any) => {
    try {
      const agentOsBin = process.env.AGENT_OS_BIN || '../agent-os/agent-os';

      const { stdout } = await execAsync(`${agentOsBin} notify list`, {
        env: {
          ...process.env,
          PGDATABASE: process.env.PGDATABASE || 'quant_investment'
        },
        cwd: process.cwd()
      });

      return {
        content: [{ type: "text" as const, text: `可用通知渠道：\n\`\`\`\n${stdout}\n\`\`\`` }],
        details: { success: true }
      };
    } catch (error) {
      const err = error instanceof Error ? error.message : 'Unknown error';
      return {
        content: [{ type: "text" as const, text: `❌ 查询失败: ${err}` }],
        details: { success: false, error: err }
      };
    }
  }
};
