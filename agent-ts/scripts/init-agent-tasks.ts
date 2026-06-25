#!/usr/bin/env node
/**
 * 测试 Agent AI 决策任务初始化
 */
import { initAgentDecisionTasks } from '../src/services/scheduler/init-agent-tasks.js';

async function main() {
  try {
    await initAgentDecisionTasks();
    process.exit(0);
  } catch (error) {
    console.error('初始化失败:', error);
    process.exit(1);
  }
}

main();
