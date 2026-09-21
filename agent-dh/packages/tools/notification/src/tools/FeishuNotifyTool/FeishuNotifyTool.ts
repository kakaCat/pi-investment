import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse, ErrorType } from '@pi-investment/core-tool';
import { AgentOSClient } from '@pi-investment/agent-os-client';
import { feishuNotifyPrompt, type FeishuNotifyParams, type FeishuNotifyResult } from './prompt';

export class FeishuNotifyTool extends BaseTool<FeishuNotifyParams, FeishuNotifyResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'feishu_notify',
    category: 'notification',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = feishuNotifyPrompt;

  constructor(
    private aos: AgentOSClient,
    private agentSign: string,
    private feishuWebhooks: Record<string, string>,
    private aosBaseURL: string
  ) {
    super();
  }

  protected validate(params: FeishuNotifyParams): ValidationResult {
    const errors: string[] = [];

    if (!params.title || params.title.trim().length === 0) {
      errors.push('title 不能为空');
    }

    if (!params.content || params.content.trim().length === 0) {
      errors.push('content 不能为空');
    }

    if (params.urgency && !['low', 'normal', 'high'].includes(params.urgency)) {
      errors.push('urgency 必须是 low, normal 或 high');
    }

    if (errors.length > 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        issue: errors.join('; '),
      };
    }

    return { success: true };
  }

  protected async execute(
    params: FeishuNotifyParams,
    context: ToolContext
  ): Promise<FeishuNotifyResult> {
    // 渠道路由：显式 channel 优先，否则按 urgency 分流
    const urgency = params.urgency || 'normal';
    const channel = params.channel || (urgency === 'high' ? 'alerts' : 'reports');
    const content = this.sign(params.content);

    // 方案 C：主路径走 Agent OS API，失败时降级为直发飞书 webhook 兜底
    try {
      const result: any = await this.aos.notification.send({
        channel,
        title: params.title,
        content,
        urgency,
      });

      if (result?.success === false) {
        throw new Error(result?.error || 'Agent OS 返回 success=false');
      }

      return {
        ...result,
        channel,
        delivery: 'agent_os',
        success: true
      };
    } catch (e: any) {
      const fallback = await this.sendFeishuDirect(channel, params.title, content, urgency);
      return {
        ...fallback,
        degraded: true,
        fallback_reason: String(e?.message ?? e)
      };
    }
  }

  protected wrap(data: FeishuNotifyResult, context: ToolContext): ToolResponse<FeishuNotifyResult> {
    return {
      success: data.success,
      data,
    };
  }

  /**
   * 身份署名：所有外发通知带上 agent 名字+ID
   */
  private sign(content: string): string {
    return `${content}\n\n—— ${this.agentSign}`;
  }

  /**
   * 直发飞书（降级兜底路径）
   */
  private async sendFeishuDirect(
    channelCode: string,
    title: string,
    content: string,
    urgency: string
  ): Promise<FeishuNotifyResult> {
    // 1. 解析 webhook：配置优先，Agent OS API 回退
    let webhook = this.feishuWebhooks[channelCode] || this.feishuWebhooks['*'];
    let webhookSource = webhook ? 'config' : '';

    if (!webhook) {
      try {
        const res = await fetch(`${this.aosBaseURL}/api/v1/notifications/channels`);
        if (res.ok) {
          const data: any = await res.json();
          const channel = (data?.channels || []).find((c: any) => c.code === channelCode && c.enabled);
          webhook = channel?.config?.webhook;
          webhookSource = webhook ? 'agent_os_api' : '';
        }
      } catch {
        /* Agent OS 不可达，落到错误处理 */
      }
    }

    if (!webhook) {
      throw new Error(
        `渠道 ${channelCode} 无可用 webhook（配置与 Agent OS API 均无）。` +
        `请在 cordis.patch.yml 的 notification.feishuWebhooks 配置`
      );
    }

    // 2. 直发飞书自定义机器人（interactive 卡片支持 markdown）
    const template = urgency === 'high' ? 'red' : urgency === 'low' ? 'grey' : 'blue';
    const resp = await fetch(webhook, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        msg_type: 'interactive',
        card: {
          header: { title: { tag: 'plain_text', content: title }, template },
          elements: [{ tag: 'div', text: { tag: 'lark_md', content } }],
        },
      }),
    });

    const result: any = await resp.json().catch(() => ({}));

    if (!resp.ok || (result.code !== undefined && result.code !== 0)) {
      throw new Error(`飞书投递失败：HTTP ${resp.status} ${JSON.stringify(result).slice(0, 200)}`);
    }

    return {
      success: true,
      channel: channelCode,
      delivery: 'feishu_direct',
      webhook_source: webhookSource,
      feishu_code: result.code ?? 0,
      message: '已直发飞书（code=0 确认送达）',
    };
  }
}
