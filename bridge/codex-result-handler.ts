/**
 * Codex 任务完成后的处理
 *
 * 当 Codex 完成任务时：
 * 1. 写入结果到 bridge/codex/completed/task_xxx.json
 * 2. 写入通知到 bridge/codex/notifications/task_xxx.txt
 * 3. Claude Hook 监听 notifications/ 目录
 */

import { writeFileSync } from 'fs';
import { join } from 'path';

export function saveCodexResult(taskId: string, result: any) {
  const timestamp = new Date().toISOString();

  // 1. 保存完整结果
  const resultFile = join(__dirname, 'codex', 'completed', `${taskId}.json`);
  writeFileSync(resultFile, JSON.stringify({
    id: taskId,
    completed_at: timestamp,
    result
  }, null, 2));

  // 2. 写入通知（触发 Claude Hook）
  const notificationFile = join(__dirname, 'codex', 'notifications', `${taskId}.txt`);
  writeFileSync(notificationFile, `Codex 任务完成: ${taskId}\n时间: ${timestamp}`);

  console.log(`✅ 任务 ${taskId} 已完成，通知已发送`);
}
