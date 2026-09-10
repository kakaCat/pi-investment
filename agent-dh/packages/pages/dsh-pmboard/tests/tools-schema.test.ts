/**
 * reqboard 工具 schema 冒烟：defineTool 在调用时即编译 schema（dsh-tools rc7 起每个
 * object 节点必须显式声明 additionalProperties），编译抛错 = 运行时注册必崩。
 * 本测试仅构造两个工具（不执行），锁定 schema 铁律合规。
 */
import { describe, expect, it } from 'vitest';
import { defineCreateTool, defineStatusTool, defineMoveTool } from '../src/host/agent-tools.js';

// defineTool 编译 schema 不触碰 deps 执行路径；构造用最小 stub 即可
const deps = {
  store: { snapshot: () => ({ requirements: [], tasks: [], triages: [] }) },
  now: () => 0,
} as never;

describe('reqboard 工具 schema（构造即编译）', () => {
  it('reqboard_create schema 合法', () => {
    expect(() => defineCreateTool(deps)).not.toThrow();
  });
  it('reqboard_status schema 合法', () => {
    expect(() => defineStatusTool(deps)).not.toThrow();
  });
  it('reqboard_move schema 合法', () => {
    expect(() => defineMoveTool(deps)).not.toThrow();
  });
});
