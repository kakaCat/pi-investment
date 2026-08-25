/**
 * RFC 009: 公告板生命周期管理工具
 * 
 * board_update - 更新公告板帖子状态（edit/claim/pause/blocked/complete/drop）
 * board_read (增强) - 读取公告板，支持状态过滤
 * board_post (增强) - 发帖，支持 needs_action 参数
 */

import { Context } from '@deepseek-ai/cordis';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { MemoryClient } from '@pi-investment/agent-os-client';

// 状态机定义（RFC 009 §3）
const STATE_MACHINE: Record<string, string[]> = {
  open: ['claim', 'drop'],
  claimed: ['pause', 'blocked', 'complete', 'drop'],
  paused: ['claim', 'drop'],
  blocked: ['claim', 'complete', 'drop'],
  done: [], // 终态
  dropped: [], // 终态
  archived: [], // 终态（GC 产生）
};

interface ModerationLogEntry {
  timestamp: string;
  action: string;
  actor: string;
  note?: string;
}

/**
 * 注册 board_update 工具
 */
export function registerBoardUpdate(ctx: Context, memoryClient: MemoryClient) {
  ctx.tools.register(defineTool({
    name: 'board_update',
    description: '更新公告板帖子状态（RFC 009）。支持：edit编辑、claim认领、pause暂停、blocked卡住、complete完成、drop删除。closed类动作（complete/drop）需填note。',
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
      const { post_id, action, note, content, expected_revision, notify } = args;
      // title 参数暂不使用（需要完整的 PUT 更新，这里简化为只更新 content）

      // 1. 读取帖子
      const response = await memoryClient.search({
        query: post_id,
        top_k: 1,
        includeClosed: true, // 允许操作已关闭的帖子（如补充 note）
      });

      if (!response.memories || response.memories.length === 0) {
        throw new Error(`帖子不存在: ${post_id}`);
      }

      const post = response.memories[0];
      const metadata = (post as any).metadata || {};
      const currentStatus = metadata.board_status || 'open';
      const currentRevision = metadata.revision || 1;
      const assignee = metadata.assignee || null;
      const author = metadata.author || null;

      // 2. Revision 校验
      if (expected_revision !== undefined && expected_revision !== currentRevision) {
        throw new Error(
          `revision 冲突：期望 ${expected_revision}，实际 ${currentRevision}。帖子已被修改，请刷新后重试`
        );
      }

      // 3. 权限检查（作者/认领人/管理员）
      const currentWindow = (ctx as any).agentId || 'unknown'; // 从 context 获取当前窗口 ID
      const isAuthor = author === currentWindow;
      const isAssignee = assignee === currentWindow;
      const isAdmin = false; // TODO: 管理员逻辑
      const hasPermission = isAuthor || isAssignee || isAdmin;

      if (!hasPermission && action !== 'claim') {
        throw new Error(
          `权限不足：只有作者/认领人/管理员可执行 ${action}。当前作者=${author}, 认领人=${assignee}`
        );
      }

      // 4. 状态迁移合法性校验
      const allowedActions = STATE_MACHINE[currentStatus] || [];
      if (!allowedActions.includes(action) && action !== 'edit') {
        throw new Error(
          `非法操作：当前状态 ${currentStatus} 不允许 ${action}。允许的操作：${allowedActions.join(', ')}`
        );
      }

      // 5. Closed 类动作必须填 note
      if ((action === 'complete' || action === 'drop') && (!note || note.trim() === '')) {
        throw new Error(`${action} 操作必须填写 note（关闭原因）`);
      }

      // 6. 构造 metadata patch
      let newStatus = currentStatus;
      const metadataPatch: Record<string, any> = {
        revision: currentRevision + 1,
      };

      // 追加 moderation_log
      const moderationLog: ModerationLogEntry[] = metadata.moderation_log || [];
      const logEntry: ModerationLogEntry = {
        timestamp: new Date().toISOString(),
        action,
        actor: currentWindow,
        note,
      };
      moderationLog.push(logEntry);
      metadataPatch.moderation_log = moderationLog;

      switch (action) {
        case 'edit':
          // 编辑内容/标题，不改变状态
          break;

        case 'claim':
          newStatus = 'claimed';
          metadataPatch.board_status = newStatus;
          metadataPatch.assignee = currentWindow;
          metadataPatch.claimed_at = new Date().toISOString();
          metadataPatch.claim_count = (metadata.claim_count || 0) + 1;
          break;

        case 'pause':
          newStatus = 'paused';
          metadataPatch.board_status = newStatus;
          metadataPatch.status_reason = note || '暂停';
          break;

        case 'blocked':
          newStatus = 'blocked';
          metadataPatch.board_status = newStatus;
          metadataPatch.status_reason = note || '卡住';
          break;

        case 'complete':
          newStatus = 'done';
          metadataPatch.board_status = newStatus;
          metadataPatch.status_reason = note;
          metadataPatch.closed_at = new Date().toISOString();
          break;

        case 'drop':
          newStatus = 'dropped';
          metadataPatch.board_status = newStatus;
          metadataPatch.drop_reason = note;
          metadataPatch.closed_at = new Date().toISOString();
          break;

        default:
          throw new Error(`未知操作：${action}`);
      }

      // 7. 调用 patchMemory
      const patchPayload: any = {
        metadataPatch,
        expectedRevision: currentRevision,
      };

      if (action === 'edit') {
        if (content) patchPayload.content = content;
        // title 更新需要用完整的 PUT，这里简化为只更新 content
      }

      await memoryClient.patchMemory(post_id, patchPayload);

      // 8. 通知窗口（如有）
      if (notify && Array.isArray(notify) && notify.length > 0) {
        // TODO: 调用 window_message 通知各窗口
        // 需要从 ctx 获取 window_message 工具或直接调用
      }

      return {
        success: true,
        new_status: newStatus,
        revision: currentRevision + 1,
        message: `已执行 ${action}，状态: ${currentStatus} → ${newStatus}`,
      };
    },
  } as any));
}

/**
 * 注册增强的 board_read 工具
 */
export function registerBoardRead(ctx: Context, memoryClient: MemoryClient) {
  ctx.tools.register(defineTool({
    name: 'board_read',
    description: '读取公告板帖子（RFC 009增强）。默认返回活跃帖（open/claimed/blocked），可按状态/认领人过滤。',
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

      const includeClosed = status === 'all' || status === 'done' || status === 'dropped';

      const response = await memoryClient.search({
        query: '', // 空查询返回全部
        tag: 'office:board',
        top_k: limit,
        includeClosed,
      });

      let posts = response.memories || [];

      // 过滤状态
      if (status === 'active') {
        posts = posts.filter((p: any) => {
          const s = p.metadata?.board_status || 'open';
          return ['open', 'claimed', 'blocked'].includes(s);
        });
      } else if (status === 'done') {
        posts = posts.filter((p: any) => p.metadata?.board_status === 'done');
      } else if (status === 'dropped') {
        posts = posts.filter((p: any) => p.metadata?.board_status === 'dropped');
      }

      // 过滤 kind
      if (kind) {
        posts = posts.filter((p: any) => p.metadata?.kind === kind);
      }

      // 过滤 assignee
      if (assignee) {
        posts = posts.filter((p: any) => p.metadata?.assignee === assignee);
      }

      // 计算派生字段
      posts = posts.map((p: any) => {
        const createdAt = new Date(p.created_at);
        const now = new Date();
        const ageHours = Math.floor((now.getTime() - createdAt.getTime()) / (1000 * 60 * 60));
        const claimedAt = p.metadata?.claimed_at ? new Date(p.metadata.claimed_at) : null;
        const stale = claimedAt
          ? Math.floor((now.getTime() - claimedAt.getTime()) / (1000 * 60 * 60)) > 48
          : ageHours > 72;

        return {
          ...p,
          status: p.metadata?.board_status || 'open',
          assignee: p.metadata?.assignee || null,
          revision: p.metadata?.revision || 1,
          claim_count: p.metadata?.claim_count || 0,
          age_hours: ageHours,
          stale,
        };
      });

      return {
        posts,
        total: posts.length,
      };
    },
  } as any));
}

/**
 * 注册增强的 board_post 工具
 */
export function registerBoardPost(ctx: Context, memoryClient: MemoryClient) {
  ctx.tools.register(defineTool({
    name: 'board_post',
    description: '发布公告板帖子（RFC 009增强）。needs_action=true进悬赏池（open状态），false纯记录（done状态）。',
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
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          success: { type: 'boolean', description: '是否成功' },
          post_id: { type: 'string', description: '帖子 ID' },
          status: { type: 'string', description: '初始状态' },
        },
        additionalProperties: false,
      },
      render: (_args: any, value: any) => [
        { type: 'text', text: JSON.stringify(value, null, 2) },
      ],
    },
    timeoutMs: 10000,
    execute: async (args: any) => {
      const { title, content, kind, needs_action = false } = args;

      const currentWindow = (ctx as any).agentId || 'unknown';
      const initialStatus = needs_action ? 'open' : 'done';

      const response = await memoryClient.write({
        title,
        content,
        namespace: 'knowledge',
        tags: ['office:board', `kind:${kind}`],
        // metadata 通过 metadataPatch 设置（但 write 不支持），需要后续 patch
      });

      const postId = (response as any).memory?.id;

      // 立即 patch metadata 设置初始状态
      if (postId) {
        await memoryClient.patchMemory(postId, {
          metadataPatch: {
            board_status: initialStatus,
            kind,
            author: currentWindow,
            revision: 1,
            moderation_log: [
              {
                timestamp: new Date().toISOString(),
                action: 'create',
                actor: currentWindow,
                note: needs_action ? '创建并进悬赏池' : '创建记录（已完成）',
              },
            ],
          },
        });
      }

      return {
        success: true,
        post_id: postId,
        status: initialStatus,
      };
    },
  } as any));
}
