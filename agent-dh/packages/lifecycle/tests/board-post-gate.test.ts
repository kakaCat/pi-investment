import { describe, expect, it, vi } from 'vitest';
import { registerBoardPost } from '../src/board-tools.js';

/**
 * R-015 v15 分档确认门禁测试（2026-09-10 用户授权放宽）。
 *
 * 档位语义：
 *   悬赏档（needs_action=true）→ 无 confirmed 必须硬拦截（needs_user_confirmation），
 *     不得触达后端；带 confirmed 才真发。
 *   纯记录档（needs_action=false）→ 免确认直接发（创建即 done 终态），
 *     但系统噪声（reminder delivered / auto-track / 过短正文）被护栏拒绝。
 */
function mountTool() {
  const createPost = vi.fn(async (input: any) => ({ post: { id: 'p-1', status: input.needs_action ? 'open' : 'done' } }));
  let tool: any;
  const ctx: any = { tools: { register: (t: any) => { tool = t; } } };
  registerBoardPost(ctx, { createPost } as any, 'investor');
  return { tool, createPost };
}

const LONG = '本贴记录一条有长期价值的结论：公告板分档确认改造已于 2026-09-10 落地并通过实测。';

describe('board_post 分档确认门禁', () => {
  it('悬赏档缺 confirmed → needs_user_confirmation 且不触达后端', async () => {
    const { tool, createPost } = mountTool();
    const res = await tool.execute({ title: '【悬赏】谁去修 X', content: LONG, kind: 'proposal', needs_action: true });
    expect(res.success).toBe(false);
    expect(res.status).toBe('needs_user_confirmation');
    expect(createPost).not.toHaveBeenCalled();
    expect(String(res.instruction)).toContain('悬赏档');
  });

  it('悬赏档带 confirmed → 真发且进 open', async () => {
    const { tool, createPost } = mountTool();
    const res = await tool.execute({ title: '【悬赏】谁去修 X', content: LONG, kind: 'proposal', needs_action: true, confirmed: true });
    expect(res.success).toBe(true);
    expect(res.status).toBe('open');
    expect(createPost).toHaveBeenCalledTimes(1);
  });

  it('纯记录档免确认 → 直接发（done 终态）', async () => {
    const { tool, createPost } = mountTool();
    const res = await tool.execute({ title: '【根因】公告板空白成因', content: LONG, kind: 'finding', needs_action: false });
    expect(res.success).toBe(true);
    expect(res.status).toBe('done');
    expect(createPost).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['reminder agent-brain-daily-audit delivered', LONG],
    ['auto-track portfolio_trade ok (g25)', LONG],
    ['reminder: v2:daily_review delivered', LONG],
    ['【根因】公告板空白成因', '太短'],
  ])('纯记录档防噪声护栏拒绝：%s', async (title, content) => {
    const { tool, createPost } = mountTool();
    const res = await tool.execute({ title, content, kind: 'finding', needs_action: false });
    expect(res.status).toBe('rejected_noise');
    expect(createPost).not.toHaveBeenCalled();
  });

  it('噪声标题在悬赏档不受护栏限制（护栏只服务于纯记录免确认档）', async () => {
    const { tool, createPost } = mountTool();
    const res = await tool.execute({ title: 'reminder 检查项待办', content: LONG, kind: 'question', needs_action: true, confirmed: true });
    expect(res.success).toBe(true);
    expect(createPost).toHaveBeenCalledTimes(1);
  });
});
