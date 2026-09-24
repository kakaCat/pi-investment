/**
 * 配置 / 路径 / 开关纯函数（REQ-260924213231-b1c4 T-12：index.ts 超 400 行尺寸门禁，
 * 从组合根抽出本块）。注释随代码搬（硬约束：不重写、不删"为什么/事故出处"型注释）；
 * dshHomePath / nodeIsolationEnabled 由 index.ts **再导出**以保持既有 import 兼容。
 */
import * as os from 'node:os';
import * as path from 'node:path';

export interface PluginConfig {
  /** DSH 主目录（默认 ~/.dsh） */
  dshHome?: string;
  /**
   * 节点隔离开关（REQ-422af1 t10）。**默认关**：关闭时隔离代码路径执行 0 次，
   * 行为完全等同改造前（design/migration.md §3）。显式配置优先于环境变量。
   */
  nodeIsolation?: boolean;
  /** 模板根绝对路径（REQ-260922213356-4a45 T-3）；缺省按包根 templates 解析。 */
  templateRoot?: string;
  /** 地址段开关（T-3；默认 true；false = 完全回退到改造前注入行为）。 */
  addressSectionEnabled?: boolean;
}

export function dshHomePath(config: PluginConfig | undefined, file: string): string {
  const home = config?.dshHome || process.env.DSH_HOME || path.join(os.homedir(), '.dsh');
  return path.join(home, file);
}

/**
 * 节点隔离开关（REQ-422af1 t10 / design/migration.md §3）：**默认关**。
 * 优先级：显式配置 nodeIsolation > 环境变量 NODE_ISOLATION(=1/true/on/yes) > 默认 false。
 * 关闭时 createNodeSettlementDispatcher 的 enabled=false 分支直接返回——
 * 不调度、不建端口、不触会话（stats 四项计数全 0 即其可执行证明）。
 */
export function nodeIsolationEnabled(
  config?: PluginConfig,
  env: Record<string, string | undefined> = process.env,
): boolean {
  if (config?.nodeIsolation !== undefined) return config.nodeIsolation;
  const raw = env.NODE_ISOLATION;
  if (raw === undefined) return false;
  return ['1', 'true', 'on', 'yes'].includes(raw.trim().toLowerCase());
}
