#!/usr/bin/env tsx
/**
 * 验证调度器任务配置
 */

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('📊 验证调度器任务配置');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

// 读取日志文件中的任务信息
import { readFileSync } from 'fs';

try {
  const log = readFileSync('/tmp/scheduler-daemon.log', 'utf-8');

  // 提取任务列表
  const taskPattern = /• (.+?)\n\s+状态: (.+?)\n\s+调度: (.+?)\n\s+下次运行: (.+?)(?:\n|$)/g;
  const tasks = [];
  let match;

  while ((match = taskPattern.exec(log)) !== null) {
    tasks.push({
      name: match[1],
      status: match[2],
      schedule: match[3],
      nextRun: match[4]
    });
  }

  // 去重
  const uniqueTasks = tasks.filter((task, index, self) =>
    index === self.findIndex(t => t.name === task.name)
  );

  console.log(`找到 ${uniqueTasks.length} 个已注册的任务:\n`);

  for (const task of uniqueTasks) {
    console.log(`📋 ${task.name}`);
    console.log(`   状态: ${task.status}`);
    console.log(`   调度: ${task.schedule}`);
    console.log(`   下次运行: ${task.nextRun}`);
    console.log('');
  }

  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('✅ 验证完成');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  // 按类型分组统计
  const aiTasks = uniqueTasks.filter(t =>
    ['morning_ai_analysis', 'realtime_quick_check', 'daily_ai_review'].includes(t.name)
  );
  const dataTasks = uniqueTasks.filter(t =>
    ['daily_data_update', 'daily_data_check'].includes(t.name)
  );

  console.log('📊 任务统计:');
  console.log(`   AI决策任务: ${aiTasks.length}个`);
  console.log(`   数据任务: ${dataTasks.length}个`);
  console.log(`   总计: ${uniqueTasks.length}个\n`);

  // 验证关键任务
  const requiredTasks = [
    'morning_ai_analysis',
    'daily_data_update',
    'daily_data_check'
  ];

  console.log('🔍 关键任务检查:');
  for (const taskName of requiredTasks) {
    const found = uniqueTasks.find(t => t.name === taskName);
    if (found) {
      console.log(`   ✅ ${taskName} - 已注册`);
    } else {
      console.log(`   ❌ ${taskName} - 未找到`);
    }
  }

} catch (error) {
  console.error('❌ 读取日志文件失败:', error);
  process.exit(1);
}
