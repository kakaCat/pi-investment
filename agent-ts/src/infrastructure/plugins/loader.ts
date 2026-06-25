/**
 * Plugin Loader
 *
 * 扫描插件目录，加载带有 piagent.plugin.json 清单的插件。
 * 每个插件子目录结构:
 *
 *   my-plugin/
 *   ├── piagent.plugin.json   # 必需的清单文件
 *   └── index.ts              # 插件入口 (也支持 index.js / index.mjs)
 */
import { existsSync, readdirSync, readFileSync } from "fs";
import { join, resolve } from "path";
import type { PluginApi, PluginManifest, PluginRegistry, PluginSkill } from "./types.js";
import type { PiToolDefinition } from "../../sdk-facade.js";

function createRegistry(): PluginRegistry {
  return { tools: [], skills: [], records: [] };
}

function createPluginApi(
  tools: PiToolDefinition[],
  skills: PluginSkill[],
): PluginApi {
  return {
    registerTool(tool: any) {
      tools.push(tool);
    },
    registerSkill(skill) {
      skills.push(skill);
    },
  };
}

async function loadPlugin(dir: string, registry: PluginRegistry): Promise<void> {
  const manifestPath = join(dir, "piagent.plugin.json");
  if (!existsSync(manifestPath)) return;

  let manifest: PluginManifest;
  try {
    manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  } catch (err) {
    registry.records.push({
      id: dir,
      name: dir,
      source: dir,
      toolCount: 0,
      skillCount: 0,
      status: "error",
      error: `清单解析失败: ${err instanceof Error ? err.message : String(err)}`,
    });
    return;
  }

  const id = manifest.id || dir;
  const pluginTools: PiToolDefinition[] = [];
  const pluginSkills: PluginSkill[] = [];

  // 按优先级尝试入口文件
  const candidates = ["index.js", "index.mjs", "index.ts"];
  let loaded = false;

  for (const candidate of candidates) {
    const entryPath = join(dir, candidate);
    if (!existsSync(entryPath)) continue;

    try {
      // 使用动态 import 加载插件（支持 ESM / CJS / TS via tsx/ts-node）
      const mod = await import(resolve(entryPath));
      const fn = mod.default ?? mod.register;
      if (typeof fn === "function") {
        const api = createPluginApi(pluginTools, pluginSkills);
        await fn(api);
      }
      loaded = true;
      break;
    } catch (err) {
      registry.records.push({
        id,
        name: manifest.name ?? id,
        source: entryPath,
        toolCount: 0,
        skillCount: 0,
        status: "error",
        error: `加载失败: ${err instanceof Error ? err.message : String(err)}`,
      });
      return;
    }
  }

  registry.tools.push(...pluginTools);
  registry.skills.push(...pluginSkills);
  registry.records.push({
    id,
    name: manifest.name ?? id,
    source: dir,
    toolCount: pluginTools.length,
    skillCount: pluginSkills.length,
    status: loaded ? "loaded" : "loaded", // manifest-only plugins are valid
  });
}

/**
 * 从多个插件目录加载所有插件，返回合并的注册表
 */
export async function loadPlugins(pluginDirs: string[]): Promise<PluginRegistry> {
  const registry = createRegistry();

  for (const dir of pluginDirs) {
    if (!existsSync(dir)) continue;

    try {
      const entries = readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (!entry.isDirectory()) continue;
        await loadPlugin(join(dir, entry.name), registry);
      }
    } catch {
      // 忽略无法读取的目录
    }
  }

  return registry;
}
