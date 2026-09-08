/**
 * RFC 009 → RFC 014: 公告板生命周期管理工具
 *
 * 2026-09-08 RFC 014：公告板脱离 Agent OS memory 复用，切换到独立存储
 *（board_posts 表 + /api/v1/board/posts API）。状态机/权限/乐观锁全部移到
 * 服务端强制执行；本层只做参数透传与展示字段派生。
 *
 * board_post   - 发帖，needs_action=true 进悬赏池（open），false 纯记录（done）
 * board_read   - 读帖，支持状态/kind/认领人过滤
 * board_update - 状态流转（edit/claim/pause/blocked/complete/drop）
 */

import { Context } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import type { BoardClient } from '@pi-investment/agent-os-client';

/** 从 axios 错误里提取服务端返回的可读信息（409/403/400 的理由在 body.error/message） */
function extractServerMessage(error: any): string {
  const data = error?.response?.data;
  if (data && typeof data === 'object') {
    return data.error || data.message || JSON.stringify(data);
  }
  return error?.message || String(error);
}

/**
 * 注册 board_update 工具
 */
export function registerBoardUpdate(ctx: Context, boardClient: BoardClient, agentId: string) {
  ctx.tools.register(defineTool({
    name: 'board_update',
    description: '更新公告板帖子状态（RFC 009/014）。支持：edit编辑、claim认领、pause暂停、blocked卡住、complete完成、drop删除。closed类动作（complete/drop）需填note。',
    parameters: {
      post_id: {
        type: 'string',
        description: '帖子 ID（UUID）',
        required: true,
      },
      action: {
        type: 'string',
        description: 'edit=编辑内容, claim=认领, pause=暂停, blocked=卡住, complete=完成, drop=删除',
        required: true,
      },
      note: {
        type: 'string',
        description: '操作说明。complete/drop 必填，记录关闭原因；blocked 建议填写卡因',
      },
      title: {
        type: 'string',
        description: 'edit 时的新标题（可选）',
      },
      content: {
        type: 'string',
        description: 'edit 时的新内容（可选）',
      },
      expected_revision: {
        type: 'number',
        description: '乐观锁：期望的 revision 版本号，防止并发冲突',
      },
      notify: {
        type: 'array',
        description: '完成后通知的窗口列表（如 ["w-xxx"]）',
        items: { type: 'string' },
      },
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          success: { type: 'boolean', description: '是否成功' },
          new_status: { type: 'string', description: '新状态' },
          revision: { type: 'number', description: '新 revision' },
          message: { type: 'string', description: '结果消息' },
        },
        additionalProperties: false,
      },
      render: (_args: any, value: any) => [
        { type: 'text', text: JSON.stringify(value, null, 2) },
      ],
    },
    timeoutMs: 15000,
    execute: async (args: any) => {
      const { post_id, action, note, content, title, expected_revision, notify } = args;

      let result: any;
      try {
        result = await boardClient.updatePost(post_id, {
          action,
          note,
          title,
          content,
          expected_revision,
          actor: agentId,
        });
      } catch (error: any) {
        // 服务端 409/403/400 的理由原样抛出，保持旧工具的错误语义
        throw new Error(extractServerMessage(error));
      }

      // 通知窗口（如有）
      if (notify && Array.isArray(notify) && notify.length > 0) {
        const windowMessageTool = ctx.tools.get('window_message');
        if (windowMessageTool) {
          const notifyMessage = '公告板帖子更新：' + action + ' - ' + (result.post?.title || post_id);
          for (const windowId of notify) {
            try {
              await windowMessageTool.execute({ window: windowId, message: notifyMessage });
            } catch (err: any) {
              console.warn('通知窗口 ' + windowId + ' 失败:', err.message);
            }
          }
        }
      }

      return {
        success: true,
        new_status: result.new_status,
        revision: result.revision,
        message: result.message,
      };
    },
  } as any));
}

/**
 * 注册增强的 board_read 工具
 */
export function registerBoardRead(ctx: Context, boardClient: BoardClient, _agentId: string) {
  ctx.tools.register(defineTool({
    name: 'board_read',
    description: '读取公告板帖子（RFC 009/014）。默认返回活跃帖（open/claimed/blocked），可按状态/认领人过滤。',
    parameters: {
      kind: {
        type: 'string',
        description: '帖子类型过滤（finding/question/review/proposal），不传则全部',
      },
      status: {
        type: 'string',
        description: 'active=活跃（open/claimed/blocked），done=已完成，dropped=已删除，all=全部',
      },
      assignee: {
        type: 'string',
        description: '按认领人过滤（窗口编码如 w-xxx）',
      },
      limit: {
        type: 'number',
        description: '返回数量限制，默认 20',
      },
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          posts: {
            type: 'array',
            items: { type: 'object', additionalProperties: true },
          },
          total: { type: 'number', description: '总数' },
        },
        additionalProperties: false,
      },
      render: (_args: any, value: any) => [
        { type: 'text', text: JSON.stringify(value, null, 2) },
      ],
    },
    timeoutMs: 10000,
    execute: async (args: any) => {
      const { kind, status = 'active', assignee, limit = 20 } = args;

      const result = await boardClient.listPosts({
        status,
        kind: kind || undefined,
        assignee: assignee || undefined,
        limit,
      });

      // 派生字段（age_hours/stale），与旧实现口径一致
      const now = new Date();
      const posts = (result.posts || []).map((p: any) => {
        const createdAt = new Date(p.created_at);
        const ageHours = Math.floor((now.getTime() - createdAt.getTime()) / (1000 * 60 * 60));
        const claimedAt = p.claimed_at ? new Date(p.claimed_at) : null;
        const stale = claimedAt
          ? Math.floor((now.getTime() - claimedAt.getTime()) / (1000 * 60 * 60)) > 48
          : ageHours > 72;

        return {
          ...p,
          title: p.display_title || p.title,
          status: p.status,
          assignee: p.assignee || null,
          author: p.author || null,
          revision: p.revision || 1,
          claim_count: p.claim_count || 0,
          age_hours: ageHours,
          stale,
        };
      });

      return {
        posts,
        total: result.total ?? posts.length,
      };
    },
  } as any));
}

/**
 * 注册增强的 board_post 工具
 */
export function registerBoardPost(ctx: Context, boardClient: BoardClient, agentId: string) {
  ctx.tools.register(defineTool({
    name: 'board_post',
    description: '发布公告板帖子（RFC 009/014）。⚠️ 调用即向用户弹确认框，用户同意才真发——纯记录/复盘/交付说明请改用 memory_write 不要调本工具；公告板只承载悬赏/跨窗口协作/需他人行动的帖子。needs_action=true进悬赏池（open状态），false纯记录（done状态）。',
    parameters: {
      title: {
        type: 'string',
        description: '帖子标题（一句话）',
        required: true,
      },
      content: {
        type: 'string',
        description: '帖子内容',
        required: true,
      },
      kind: {
        type: 'string',
        description: 'finding=发现, question=疑问, review=复盘, proposal=倡议',
        required: true,
      },
      needs_action: {
        type: 'boolean',
        description: 'true=进悬赏池（open），false=纯记录（done）',
      },
      confirmed: {
        type: 'boolean',
        description: '是否已征得用户同意。false（默认）返回预览+提示，不真发；true 才执行发帖。',
      },
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          success: { type: 'boolean', description: '是否成功' },
          post_id: { type: 'string', description: '帖子 ID（confirmed=true 时返回）' },
          status: { type: 'string', description: '初始状态 或 needs_user_confirmation（未确认时）' },
          preview: { type: 'object', additionalProperties: true, description: '未确认时返回的帖子预览' },
          instruction: { type: 'string', description: '未确认时的操作指引' },
        },
        additionalProperties: false,
      },
      render: (_args: any, value: any) => [
        { type: 'text', text: JSON.stringify(value, null, 2) },
      ],
    },
    timeoutMs: 10000,
    execute: async (args: any) => {
      const { title, content, kind, needs_action = false, confirmed = false } = args;

      // R-014 工具级强制（2026-09-08 用户指令）：发帖前必须经用户确认。
      // 公告板只承载悬赏/跨窗口协作帖；纯记录应走 memory_write，不上板。
      if (!confirmed) {
        return {
          success: false,
          post_id: null,
          status: 'needs_user_confirmation',
          preview: {
            title,
            content: content.slice(0, 200) + (content.length > 200 ? '...' : ''),
            kind,
            needs_action,
          },
          instruction: '请向用户确认是否需要发此公告板帖子。纯记录/复盘/交付说明建议改用 memory_write 不上板；悬赏/跨窗口协作才上公告板。确认后重新调用 board_post 并设 confirmed=true。',
        } as any;
      }

      try {
        const result = await boardClient.createPost({
          title,
          content,
          kind,
          needs_action,
          author: agentId,
        });
        return {
          success: true,
          post_id: result.post?.id,
          status: result.post?.status,
        };
      } catch (error: any) {
        throw new Error('创建公告板帖子失败: ' + extractServerMessage(error));
      }
    },
  } as any));
}
