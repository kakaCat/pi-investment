import { AxiosInstance } from 'axios';
import { createHttpClient } from './http.js';
import type { RegistryClientConfig } from './types.js';

/**
 * BoardClient — Agent OS 公告板 API（RFC 014 独立存储）。
 *
 * Server contract:
 *   GET   /api/v1/board/posts?status=&kind=&assignee=&limit=
 *   POST  /api/v1/board/posts            {title, content, kind, needs_action, author}
 *   GET   /api/v1/board/posts/{id}
 *   PATCH /api/v1/board/posts/{id}       {action, note, title, content, expected_revision, actor}
 *
 * 状态机/权限/乐观锁均在服务端强制执行（409=revision 冲突，403=权限不足，400=非法流转/缺 note）。
 */

export interface BoardPost {
  id: string;
  title: string;
  content: string;
  display_title?: string;
  kind: string;
  status: string;
  author?: string | null;
  assignee?: string | null;
  revision: number;
  claim_count: number;
  claimed_at?: string | null;
  closed_at?: string | null;
  status_reason?: string | null;
  drop_reason?: string | null;
  moderation_log: { timestamp: string; action: string; actor: string; note?: string }[];
  created_at: string;
  updated_at: string;
}

export interface BoardListParams {
  status?: 'active' | 'done' | 'dropped' | 'all' | string;
  kind?: string;
  assignee?: string;
  limit?: number;
}

export interface BoardCreateParams {
  title: string;
  content: string;
  kind: string;
  needs_action?: boolean;
  author?: string;
}

export interface BoardUpdateParams {
  action: 'edit' | 'claim' | 'pause' | 'blocked' | 'complete' | 'drop';
  note?: string;
  title?: string;
  content?: string;
  expected_revision?: number;
  actor: string;
}

export class BoardClient {
  private client: AxiosInstance;

  constructor(config: RegistryClientConfig) {
    this.client = createHttpClient(config);
  }

  async listPosts(params: BoardListParams): Promise<{ posts: BoardPost[]; total: number }> {
    const response = await this.client.get('/api/v1/board/posts', {
      params: {
        status: params.status || undefined,
        kind: params.kind || undefined,
        assignee: params.assignee || undefined,
        limit: params.limit && params.limit > 0 ? params.limit : undefined,
      },
    });
    return response.data;
  }

  async getPost(id: string): Promise<BoardPost> {
    if (!id) throw new Error('id is required');
    const response = await this.client.get('/api/v1/board/posts/' + id);
    return response.data;
  }

  async createPost(params: BoardCreateParams): Promise<{ success: boolean; post: BoardPost }> {
    if (!params.title?.trim()) throw new Error('title is required');
    if (!params.content?.trim()) throw new Error('content is required');
    const response = await this.client.post('/api/v1/board/posts', {
      title: params.title,
      content: params.content,
      kind: params.kind,
      needs_action: params.needs_action ?? false,
      author: params.author,
    });
    return response.data;
  }

  async updatePost(
    id: string,
    params: BoardUpdateParams,
  ): Promise<{ success: boolean; post: BoardPost; new_status: string; revision: number; message: string }> {
    if (!id) throw new Error('id is required');
    const response = await this.client.patch('/api/v1/board/posts/' + id, {
      action: params.action,
      note: params.note,
      title: params.title,
      content: params.content,
      expected_revision: params.expected_revision,
      actor: params.actor,
    });
    return response.data;
  }
}
