/**
 * Plugin System Types
 *
 * 插件清单文件: piagent.plugin.json
 * 插件入口文件: index.ts 或 index.js
 *
 * 示例插件:
 *   export default function(api) {
 *     api.registerTool({ name: "my_tool", ... });
 *     api.registerSkill({ name: "my-skill", description: "...", content: "# ..." });
 *   }
 */

// Re-export for plugin authors
export type { ToolDefinition } from "@mariozechner/pi-coding-agent";

/**
 * 插件注册的 Skill（注入到系统提示词中）
 */
export interface PluginSkill {
  name: string;
  description: string;
  /** 调用方式，默认为 name */
  invocation?: string;
  /** 可选的 Markdown 内容，追加到 Skill 描述后 */
  content?: string;
}

/**
 * 插件 API —— 传给插件的 register 函数
 */
export interface PluginApi {
  registerTool(tool: import("@mariozechner/pi-coding-agent").ToolDefinition): void;
  registerSkill(skill: PluginSkill): void;
}

/**
 * piagent.plugin.json 清单
 */
export interface PluginManifest {
  id: string;
  name?: string;
  description?: string;
  version?: string;
}

/**
 * 插件加载记录
 */
export interface PluginRecord {
  id: string;
  name: string;
  source: string;
  toolCount: number;
  skillCount: number;
  status: "loaded" | "error";
  error?: string;
}

/**
 * 插件注册表 —— 所有已加载插件贡献的工具和技能
 */
export interface PluginRegistry {
  tools: import("@mariozechner/pi-coding-agent").ToolDefinition[];
  skills: PluginSkill[];
  records: PluginRecord[];
}
