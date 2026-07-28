/**
 * Tool Groups - 动态工具加载测试
 *
 * 覆盖 2026-07-27 会话日志暴露的 bug：
 * load_tools 加载的工具在下一个 turn 报 "Tool not found"。
 *
 * 根因：SDK 在每次 prompt run 开始时快照 tools，run 内
 * setActiveToolsByName 要等下一次 prompt 才生效；且 loadToolGroups
 * 是替换语义，加载第二组会卸载第一组。
 *
 * 修复契约：
 * 1. loadToolGroups 累加语义（并集），不再互相卸载
 * 2. 加载产生 pending reload 记录，consumePendingToolReload 读取并清空
 * 3. preloadGroupsForMessage 在 run 前按关键词预加载（快照内生效）
 * 4. promptWithDynamicTools 在 run 结束后发现 pending reload 时自动续跑
 */
import { describe, it, expect, beforeEach } from '@jest/globals';
import {
  CORE_TOOLS,
  registerToolSwitcher,
  setActiveToolNames,
  getActiveToolNames,
  loadToolGroups,
  consumePendingToolReload,
  preloadGroupsForMessage,
  promptWithDynamicTools,
} from './tool-groups.js';

let switchedTo: string[][];

beforeEach(() => {
  switchedTo = [];
  registerToolSwitcher(async (names: string[]) => {
    switchedTo.push([...names]);
  });
  setActiveToolNames([...CORE_TOOLS]);
  consumePendingToolReload(); // 清空 pending 状态
});

describe('loadToolGroups 累加语义', () => {
  it('加载第二组时保留第一组和 Core 工具', async () => {
    await loadToolGroups(['game_theory']);
    expect(getActiveToolNames()).toContain('opponent_behavior');

    await loadToolGroups(['strategy_dev']);

    const active = getActiveToolNames();
    expect(active).toContain('strategy_list');       // 新组生效
    expect(active).toContain('opponent_behavior');   // 旧组不被卸载
    expect(active).toContain('pool_manage');         // Core 保留
  });
});

describe('pending reload 追踪', () => {
  it('初始无 pending；加载后可 consume 一次并清空', async () => {
    expect(consumePendingToolReload()).toEqual([]);

    await loadToolGroups(['game_theory']);

    expect(consumePendingToolReload()).toEqual(['game_theory']);
    expect(consumePendingToolReload()).toEqual([]);
  });

  it('重复加载已激活的组不产生 pending（避免无限续跑）', async () => {
    await loadToolGroups(['game_theory']);
    consumePendingToolReload();

    await loadToolGroups(['game_theory']);

    expect(consumePendingToolReload()).toEqual([]);
  });
});

describe('preloadGroupsForMessage', () => {
  it('按关键词在 run 前加载匹配组，且不留 pending', async () => {
    const loaded = await preloadGroupsForMessage('查看我的持仓和交易记录');

    expect(loaded).toContain('portfolio_ops');
    expect(getActiveToolNames()).toContain('portfolio_trade');
    expect(consumePendingToolReload()).toEqual([]);
  });

  it('无关键词匹配时不加载任何组', async () => {
    const loaded = await preloadGroupsForMessage('继续处理任务');

    expect(loaded).toEqual([]);
  });
});

describe('promptWithDynamicTools', () => {
  it('run 内调用 load_tools 后自动续跑，新工具在续跑 run 中可用', async () => {
    const calls: string[] = [];
    const activeDuringCall: string[][] = [];
    const promptFn = async (msg: string) => {
      calls.push(msg);
      activeDuringCall.push([...getActiveToolNames()]);
      if (calls.length === 1) {
        // 模拟模型在 run 内调用 load_tools 工具
        await loadToolGroups(['game_theory']);
      }
      return calls.length;
    };

    const result = await promptWithDynamicTools(promptFn, '继续处理任务');

    expect(calls.length).toBe(2);
    expect(calls[1]).toContain('game_theory'); // 续跑消息说明哪些工具已就绪
    expect(result).toBe(2);                    // 返回最后一次 prompt 的结果
  });

  it('无 pending reload 时不续跑', async () => {
    const calls: string[] = [];
    const promptFn = async (msg: string) => {
      calls.push(msg);
      return 'done';
    };

    const result = await promptWithDynamicTools(promptFn, '继续处理任务');

    expect(calls.length).toBe(1);
    expect(result).toBe('done');
  });

  it('续跑次数有上限（防御模型每轮都加载新组）', async () => {
    const groups = ['game_theory', 'strategy_dev', 'screening', 'admin'];
    const calls: string[] = [];
    const promptFn = async (msg: string) => {
      calls.push(msg);
      await loadToolGroups([groups[calls.length - 1]]); // 每次都加载新组
      return calls.length;
    };

    await promptWithDynamicTools(promptFn, '继续处理任务', 2);

    expect(calls.length).toBe(3); // 1 次初始 + 2 次续跑
  });
});
