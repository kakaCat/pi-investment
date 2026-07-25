/**
 * 共享 init 函数幂等守卫测试
 * TUI 集成 wake 后，gateway bootstrap 会重复调用这些 init——重复调用必须无害。
 */
import { initSkillRouter } from "../../services/intelligence/skill-router.js";
import { initSkillGuard } from "../../infrastructure/tools/skill-guard.js";
import { initSkillsBlock } from "../../core/agent/system-prompt.js";
import { setPlanToolContext } from "../../infrastructure/tools/agent/plan-tool.js";
import { initMemoryTools } from "../../infrastructure/tools/index.js";
import { getMemoryStore } from "../../services/intelligence/memory-store.js";
import { loadPlugins } from "../../infrastructure/plugins/index.js";
import { paths } from "../../config/config.js";

describe("共享 init 幂等守卫", () => {
  it("initMemoryTools 重复调用不重置 store（守卫生效）", () => {
    initMemoryTools(paths.piDir);
    const first = getMemoryStore();
    initMemoryTools(paths.piDir);
    const second = getMemoryStore();
    expect(second).toBe(first);
  });

  it("initSkillRouter 重复调用不报错", () => {
    expect(() => {
      initSkillRouter([]);
      initSkillRouter([]);
    }).not.toThrow();
  });

  it("initSkillGuard 重复调用不报错", () => {
    expect(() => {
      initSkillGuard([]);
      initSkillGuard([]);
    }).not.toThrow();
  });

  it("initSkillsBlock 重复调用不报错", () => {
    expect(() => {
      initSkillsBlock([], []);
      initSkillsBlock([], []);
    }).not.toThrow();
  });

  it("setPlanToolContext 重复调用不报错", () => {
    expect(() => {
      setPlanToolContext([]);
      setPlanToolContext([]);
    }).not.toThrow();
  });

  it("loadPlugins 两次调用返回同一 registry（缓存，不重复加载）", async () => {
    const first = await loadPlugins(paths.pluginDirs);
    const second = await loadPlugins(paths.pluginDirs);
    expect(second).toBe(first); // 引用相等 = 缓存生效
  });
});
