/**
 * PI Investment - AI 股票投资顾问
 * Entry point
 */
import "./infrastructure/tui/pi-tui-compat.js";
import "./api/index.js";

// 注意：调度器已迁移到 quantsys-v2
// Agent 只保留 AI 决策任务，通过 agent_turn 类型执行
// 数据处理任务由 quantsys-v2 的调度器自主完成
