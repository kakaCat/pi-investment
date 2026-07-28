/**
 * Tool Groups — 工具分组与动态加载系统
 *
 * 解决 60+ 工具定义占用过多 LLM 上下文窗口的问题。
 *
 * 设计:
 * - Core 工具（~30个）：始终加载，覆盖 80%+ 日常操作
 * - On-Demand 工具组（~45个）：按场景按需加载
 * - 工具组之间可复合加载（如 factor_analysis + strategy_dev）
 *
 * Token 预算:
 * - Core 工具定义目标: < 8,000 tokens
 * - 单组 On-Demand: < 3,000 tokens/组
 * - 加载全部: < 15,000 tokens (vs 原来 ~30,000)
 */

import type { ToolDefinition } from "./index.js";

// ═══════════════════════════════════════════════════════════════════════════
// 工具名称 → 工具对象 索引（由 initToolGroups 构建）
// ═══════════════════════════════════════════════════════════════════════════

const toolIndex = new Map<string, ToolDefinition>();

/**
 * 初始化工具索引
 * 需要在 agent-loop 中调用，传入 allCustomTools
 */
export function initToolGroups(allTools: ToolDefinition[]): void {
  for (const tool of allTools) {
    toolIndex.set(tool.name, tool);
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 工具分组定义
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Core 工具 — 始终加载，覆盖 80%+ 日常操作
 * 
 * 包含: 工作流管理、数据获取、基础分析、经验系统、监控
 * 不包含: 策略开发、因子研究、ML模型、深度分析、博弈
 */
export const CORE_TOOLS: string[] = [
  // === SDK 基础工具（必须，否则 LLM 无法操作文件/命令） ===
  // 注意: bash/edit/write 是 SDK 内置工具，不在 toolIndex 中，
  // 但 setActiveToolsByName 会从 _toolRegistry 正确解析它们
  "read", "bash", "edit", "write",

  // === 工作流核心 ===
  "plan_task", "clarify", "task_create", "task_update", "task_list",
  "task_execute_async", "task_check_background", "reflect",
  
  // === L1 数据管道（全部，因为数据是基础） ===
  "data_fetch_quote", "data_fetch_kline", "data_fetch_financial",
  "data_fetch_dividend", "data_fetch_macro", "data_fetch_north_flow",
  "data_fetch_market_sentiment",

  // === L2.5 机会雷达（高频使用的扫描） ===
  "opportunity_scan", "analysis_swing_points",

  // === L2.7 股票池管理（日常操作核心） ===
  "pool_manage", "pool_validate",

  // === 风控与止损（每次决策都需要） ===
  "risk_controller",

  // === 持仓管理（核心操作） ===
  "portfolio_status", "portfolio_analyze",

  // === 监控预警 ===
  "monitor_alert", "watch_manage", "watch_price_alert",
  "schedule_next_check",

  // === 经验系统 ===
  "experience_write", "query_experience",

  // === 决策追踪 ===
  "decision_record", "decision_history",

  // === 元能力 ===
  "memory_write", "memory_search", "compact", "browser",

  // === 动态工具加载（渐进披露入口） ===
  "load_tools",
];

/**
 * On-Demand 工具组
 * 
 * 每个组对应一种分析场景。LLM 通过 load_tools 工具显式加载。
 */

export interface ToolGroup {
  /** 组名（用于 load_tools 工具调用） */
  name: string;
  /** 组描述（LLM 判断是否需要加载时的参考） */
  description: string;
  /** 工具名列表 */
  tools: string[];
  /** 触发关键词（LLM 自动判断时参考） */
  keywords: string[];
}

export const TOOL_GROUPS: ToolGroup[] = [
  {
    name: "factor_analysis",
    description: "因子计算、IC分析、分层回测、因子组合优化。用于因子研究和策略开发前的因子评估。",
    tools: [
      "factor_calculate", "factor_analyze", "factor_list",
      "factor_correlation", "factor_portfolio_optimize",
      "factor_layering_backtest", "batch_factor_layering_backtest",
      "factor_ic_monitor",
    ],
    keywords: ["因子", "factor", "IC", "ICIR", "分层", "layering", "单调性", "因子分析", "alpha"],
  },
  {
    name: "strategy_dev",
    description: "策略的创建、回测、优化、批量验证、发现。用于策略开发和迭代。",
    tools: [
      "strategy_list", "strategy_detail", "strategy_write",
      "strategy_execute", "strategy_status", "strategy_optimize",
      "strategy_batch_validate", "strategy_delete", "strategy_discovery",
      "strategy_combo_backtest", "strategy_performance_comparison",
      "backtest_stats", "backtest_history",
    ],
    keywords: ["策略", "strategy", "回测", "backtest", "优化", "optimize", "发现", "参数", "indicator"],
  },
  {
    name: "indicator_dev",
    description: "技术指标的创建、回测和管理。用于开发自定义技术指标。",
    tools: [
      "indicator_list", "indicator_detail", "indicator_create",
      "indicator_update", "indicator_delete", "indicator_backtest",
    ],
    keywords: ["指标", "indicator", "技术指标", "MACD", "RSI", "KDJ", "布林", "均线"],
  },
  {
    name: "model_ml",
    description: "机器学习模型训练、预测、评估和监控。用于ML辅助决策。",
    tools: [
      "model_train", "model_predict", "model_evaluate",
      "model_monitor", "model_list", "calibrate_confidence",
      "training_reports",
    ],
    keywords: ["模型", "model", "机器学习", "ML", "XGBoost", "LightGBM", "训练", "预测", "predict"],
  },
  {
    name: "portfolio_ops",
    description: "组合操作：交易执行、组合优化、信号执行、性能分析。用于真实/虚拟交易操作。",
    tools: [
      "portfolio_trade", "portfolio_account", "portfolio_optimizer",
      "trade_algo_execute", "trade_monitor", "trade_verify",
      "signal_execution", "performance_analyzer", "realtime_signal_scan",
    ],
    keywords: ["交易", "trade", "买入", "卖出", "buy", "sell", "持仓", "组合", "portfolio", "下单", "执行"],
  },
  {
    name: "deep_analysis",
    description: "深度分析：因子模型归因、Barra风险分解、市场风格检测、时间序列分析。用于高级量化分析。",
    tools: [
      "factor_model_attribution", "risk_barra_decomposition",
      "risk_metrics", "market_style_detect",
      "factor_academic", "timeseries_analyzer",
    ],
    keywords: ["归因", "attribution", "Barra", "Fama", "French", "风格", "style", "分解", "decomposition", "GARCH", "ARIMA", "时间序列", "学术"],
  },
  {
    name: "game_theory",
    description: "博弈分析：对手行为、战场评估、操纵检测。用于识别市场博弈机会。",
    tools: [
      "opponent_behavior", "pool_battlefield", "manipulation_detect",
    ],
    keywords: ["博弈", "game", "对手", "opponent", "操纵", "manipulation", "战场", "battlefield", "庄家", "游资", "机构"],
  },
  {
    name: "rotations",
    description: "策略轮动决策：轮动方案、模拟执行、真实执行、效果验证。用于策略组合管理。",
    tools: [
      "rotation_proposal", "rotation_simulate",
      "rotation_execute", "rotation_verify",
    ],
    keywords: ["轮动", "rotation", "切换策略", "调仓", "策略组合"],
  },
  {
    name: "screening",
    description: "股票筛选和行业分析：按行业筛选、质量评分、行业聚合、基准对比。",
    tools: [
      "screening", "sector_analysis", "benchmark_compare",
    ],
    keywords: ["筛选", "screen", "行业", "sector", "板块", "基准", "benchmark", "选股"],
  },
  {
    name: "admin",
    description: "系统管理：数据管理、调度器、进化引擎、后端控制、飞书通知。",
    tools: [
      "data_manager", "data_quality_report", "data_quality_manage",
      "scheduler_manage", "evolution_run",
      "restart_agent", "backend_control", "claude_code",
      "tool_stats_query", "async_jobs",
      "feishu_notify", "daily_report",
    ],
    keywords: ["数据管理", "调度", "scheduler", "进化", "evolution", "重启", "restart", "通知", "feishu", "日报", "report"],
  },
];

// ═══════════════════════════════════════════════════════════════════════════
// 查找工具对象
// ═══════════════════════════════════════════════════════════════════════════

/**
 * 根据工具名称数组获取对应的 ToolDefinition 数组
 * 忽略不存在的工具名及 SDK 内置工具（它们由 _baseToolDefinitions 管理）
 */
export function resolveTools(names: string[]): ToolDefinition[] {
  const SKIP_SDK_BUILTINS = new Set(["read", "bash", "edit", "write", "ls", "grep", "find"]);
  const result: ToolDefinition[] = [];
  const missing: string[] = [];
  for (const name of names) {
    if (SKIP_SDK_BUILTINS.has(name)) continue;
    const tool = toolIndex.get(name);
    if (tool) {
      result.push(tool);
    } else {
      missing.push(name);
    }
  }
  if (missing.length > 0) {
    console.warn(`[tool-groups] Unresolved tool names (not in registry): ${missing.join(", ")}`);
  }
  return result;
}

/**
 * 获取 Core 工具定义
 */
export function getCoreTools(): ToolDefinition[] {
  return resolveTools(CORE_TOOLS);
}

/**
 * 获取指定工具组
 */
export function getGroupTools(groupName: string): ToolDefinition[] {
  const group = TOOL_GROUPS.find(g => g.name === groupName);
  if (!group) {
    console.warn(`[tool-groups] Unknown group: ${groupName}`);
    return [];
  }
  return resolveTools(group.tools);
}

/**
 * 获取指定工具组的工具名列表
 */
export function getGroupToolNames(groupName: string): string[] {
  const group = TOOL_GROUPS.find(g => g.name === groupName);
  return group ? group.tools : [];
}

/**
 * 列出所有可用工具组信息（供 LLM 决策使用）
 */
export function listGroups(): { name: string; description: string; toolCount: number }[] {
  return TOOL_GROUPS.map(g => ({
    name: g.name,
    description: g.description,
    toolCount: g.tools.length,
  }));
}

/**
 * 获取所有 On-Demand 工具名（合并所有组）
 */
export function getAllOnDemandToolNames(): string[] {
  const names = new Set<string>();
  for (const group of TOOL_GROUPS) {
    for (const name of group.tools) {
      names.add(name);
    }
  }
  return [...names];
}

/**
 * 检测当前会话上下文可能需要的工具组
 * 基于关键词匹配，返回推荐的组名列表
 */
export function detectContextGroups(userMessage: string): string[] {
  const lower = userMessage.toLowerCase();
  const matched: string[] = [];
  
  for (const group of TOOL_GROUPS) {
    for (const kw of group.keywords) {
      if (lower.includes(kw.toLowerCase())) {
        matched.push(group.name);
        break;
      }
    }
  }
  
  return matched;
}

// ═══════════════════════════════════════════════════════════════════════════
// 动态工具切换 — 由 agent-loop 注入
// ═══════════════════════════════════════════════════════════════════════════

type SetActiveToolsFn = (toolNames: string[]) => Promise<void>;

let _setActiveTools: SetActiveToolsFn | null = null;

/**
 * 注册动态工具切换函数（由 agent-loop 在 session 创建后调用）
 */
export function registerToolSwitcher(fn: SetActiveToolsFn): void {
  _setActiveTools = fn;
}

/**
 * 当前活跃的工具名集合
 */
let _activeToolNames: string[] = [];

/**
 * 更新活跃工具集合记录
 */
export function setActiveToolNames(names: string[]): void {
  _activeToolNames = names;
}

export function getActiveToolNames(): string[] {
  return _activeToolNames;
}

// ═══════════════════════════════════════════════════════════════════════════
// Pending reload 追踪 — run 内加载的工具要等下一次 prompt 才生效
// ═══════════════════════════════════════════════════════════════════════════

/**
 * run 内新加载、需等待下一次 prompt 才生效的工具组
 *
 * 背景：SDK 在每次 prompt run 开始时快照 tools（createContextSnapshot），
 * run 内 setActiveToolsByName 只改 agent.state.tools，不影响当前 run。
 * 因此 load_tools 生效后记录 pending，由 promptWithDynamicTools 在 run
 * 结束后自动续跑，让新工具进入下一次 run 的快照。
 */
let _pendingReloadGroups: string[] = [];

/**
 * 读取并清空 pending reload 组名（返回自上次 consume 以来新加载的组）
 */
export function consumePendingToolReload(): string[] {
  const pending = _pendingReloadGroups;
  _pendingReloadGroups = [];
  return pending;
}

/**
 * 加载一组工具（累加语义：当前活跃集 ∪ Core ∪ 指定组）
 * 由 load_tools 工具和上下文检测调用
 *
 * 注意：2026-07-27 起从"替换"改为"累加"。旧的替换语义会导致
 * 加载第二组时卸载第一组（日志中 screening 因此报 Tool not found）。
 */
export async function loadToolGroups(groupNames: string[]): Promise<{
  loaded: string[];
  newTools: string[];
  totalTools: number;
}> {
  if (!_setActiveTools) {
    throw new Error("Tool switcher not registered - session not initialized");
  }

  // 累加：已活跃工具 + Core + 请求的组
  const toolNameSet = new Set([..._activeToolNames, ...CORE_TOOLS]);
  const loadedGroups: string[] = [];

  for (const name of groupNames) {
    const group = TOOL_GROUPS.find(g => g.name === name);
    if (group) {
      loadedGroups.push(name);
      for (const toolName of group.tools) {
        toolNameSet.add(toolName);
      }
    }
  }

  const allNames = [...toolNameSet];

  // 计算新增的工具
  const newTools = allNames.filter(n => !_activeToolNames.includes(n));

  // 调用 SDK 更新活跃工具（下一次 prompt run 才生效）
  await _setActiveTools(allNames);
  _activeToolNames = allNames;

  // 只有真正新增了工具才记录 pending，避免重复加载已激活组导致无限续跑
  if (newTools.length > 0) {
    _pendingReloadGroups.push(...loadedGroups);
  }

  console.log(`[tool-groups] Loaded ${allNames.length} tools (Core + ${loadedGroups.join(", ")}), ${newTools.length} newly activated`);

  return {
    loaded: loadedGroups,
    newTools,
    totalTools: allNames.length,
  };
}

/**
 * 重置为仅 Core 工具
 */
export async function resetToCoreTools(): Promise<void> {
  if (!_setActiveTools) return;
  await _setActiveTools(CORE_TOOLS);
  _activeToolNames = [...CORE_TOOLS];
  console.log(`[tool-groups] Reset to core tools (${CORE_TOOLS.length})`);
}

// ═══════════════════════════════════════════════════════════════════════════
// Prompt 级动态工具编排 — 预加载 + run 后自动续跑
// ═══════════════════════════════════════════════════════════════════════════

/**
 * 在 prompt run 开始前按消息关键词预加载匹配的工具组
 *
 * run 前加载直接进入 SDK 的 context 快照，是 run 内唯一"立即生效"的
 * 加载方式。预加载后清空 pending（无需续跑）。
 *
 * @returns 实际新加载的组名
 */
export async function preloadGroupsForMessage(message: string): Promise<string[]> {
  if (!_setActiveTools) return [];

  const detected = detectContextGroups(message);
  const inactive = detected.filter(name => {
    const group = TOOL_GROUPS.find(g => g.name === name);
    return group && group.tools.some(t => !_activeToolNames.includes(t));
  });

  if (inactive.length === 0) return [];

  await loadToolGroups(inactive);
  consumePendingToolReload(); // run 前加载直接进快照，无需续跑
  console.log(`[tool-groups] 预加载工具组: ${inactive.join(", ")}`);
  return inactive;
}

/**
 * 构造续跑消息：告知模型哪些工具组已就绪
 */
function buildToolReloadContinuation(groups: string[]): string {
  return (
    `【系统通知】你请求的工具组 (${groups.join(", ")}) 已完成加载，` +
    `相关工具现在可以直接调用了。请继续完成之前的任务。`
  );
}

/**
 * 带动态工具加载的 prompt 执行
 *
 * 流程：
 * 1. run 前按关键词预加载（快照内生效）
 * 2. 执行 prompt
 * 3. 若 run 内模型调用了 load_tools（产生 pending reload），
 *    自动发一条续跑消息开启新 run —— 新工具进入快照，避免
 *    "Tool xxx not found"（2026-07-27 会话日志中的三次失败根因）
 *
 * @param promptFn 实际的 prompt 执行函数（通常是 session.prompt）
 * @param message 用户消息
 * @param maxContinuations 最大续跑次数（防御模型每轮都加载新组）
 * @returns 最后一次 prompt 的返回值
 */
export async function promptWithDynamicTools<T>(
  promptFn: (msg: string) => Promise<T>,
  message: string,
  maxContinuations = 2,
): Promise<T> {
  await preloadGroupsForMessage(message);

  let result = await promptFn(message);

  for (let i = 0; i < maxContinuations; i++) {
    const pending = consumePendingToolReload();
    if (pending.length === 0) break;

    console.log(`🔄 工具组 [${pending.join(", ")}] 已加载，自动续跑使工具生效`);
    result = await promptFn(buildToolReloadContinuation(pending));
  }

  return result;
}
