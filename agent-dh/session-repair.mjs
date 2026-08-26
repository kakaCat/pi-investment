#!/usr/bin/env node

/**
 * DSH Session Repair Tool
 * 
 * 修复会话持久化损坏问题：
 * - 检测并修复缺少 identified message 的事件
 * - 备份原始会话文件
 * - 生成修复报告
 */

import { readFile, writeFile, copyFile } from 'node:fs/promises';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import zlib from 'node:zlib';
import { promisify } from 'node:util';

const __dirname = dirname(fileURLToPath(import.meta.url));
const unzip = promisify(zlib.unzip);
const gzip = promisify(zlib.gzip);

/**
 * 解压并解析会话文件
 */
async function readSessionFile(filePath) {
  try {
    const compressed = await readFile(filePath);
    const decompressed = await unzip(compressed);
    const lines = decompressed.toString('utf-8').split('\n').filter(line => line.trim());
    return lines.map((line, index) => {
      try {
        return { line: index + 1, event: JSON.parse(line), raw: line };
      } catch (err) {
        console.warn(`Warning: Failed to parse line ${index + 1}: ${err.message}`);
        return { line: index + 1, event: null, raw: line, error: err.message };
      }
    });
  } catch (err) {
    throw new Error(`Failed to read session file: ${err.message}`);
  }
}

/**
 * 验证事件是否有有效的 identified message
 */
function validateMessageEvent(event, seq) {
  const type = event?.type;
  if (type !== 'user/message' && type !== 'assistant/message' && type !== 'tool/result') {
    return { valid: true };
  }

  const data = event?.data;
  if (typeof data !== 'object' || data === null) {
    return { valid: false, reason: 'data is not an object' };
  }

  const message = type === 'user/message' ? data : data?.message;
  if (typeof message !== 'object' || message === null) {
    return { valid: false, reason: 'message is not an object' };
  }

  if (typeof message.id !== 'string' || message.id === '') {
    return { valid: false, reason: 'message.id is missing or empty', hasMessage: true };
  }

  return { valid: true };
}

/**
 * 修复缺少 id 的消息
 */
function repairMessageEvent(event, seq) {
  const type = event.type;
  if (type !== 'user/message' && type !== 'assistant/message' && type !== 'tool/result') {
    return event;
  }

  const repaired = JSON.parse(JSON.stringify(event)); // deep clone
  const data = repaired.data;
  const message = type === 'user/message' ? data : data?.message;

  if (message && (typeof message.id !== 'string' || message.id === '')) {
    // 生成一个修复用的 message ID
    message.id = `repaired-msg-${seq}-${Date.now()}`;
    console.log(`  ✓ Repaired message at seq ${seq}: added id "${message.id}"`);
  }

  return repaired;
}

/**
 * 修复会话文件
 */
async function repairSessionFile(filePath, dryRun = false) {
  console.log(`\nProcessing: ${filePath}`);
  console.log('='.repeat(80));

  const events = await readSessionFile(filePath);
  const issues = [];
  const repaired = [];

  // 扫描问题
  for (let i = 0; i < events.length; i++) {
    const { line, event, raw, error } = events[i];
    
    if (error) {
      issues.push({ seq: line, type: 'parse-error', error });
      repaired.push(raw); // 保留原始行
      continue;
    }

    if (!event) {
      repaired.push(raw);
      continue;
    }

    const validation = validateMessageEvent(event, line);
    if (!validation.valid) {
      issues.push({ 
        seq: line, 
        type: 'missing-id', 
        reason: validation.reason,
        eventType: event.type 
      });
      
      // 修复事件
      const repairedEvent = repairMessageEvent(event, line);
      repaired.push(JSON.stringify(repairedEvent));
    } else {
      repaired.push(raw);
    }
  }

  // 输出报告
  console.log(`\nScan Results:`);
  console.log(`  Total events: ${events.length}`);
  console.log(`  Issues found: ${issues.length}`);
  
  if (issues.length > 0) {
    console.log(`\nIssues:`);
    for (const issue of issues) {
      console.log(`  - Seq ${issue.seq}: ${issue.type} - ${issue.reason}`);
      if (issue.eventType) {
        console.log(`    Event type: ${issue.eventType}`);
      }
    }
  }

  if (issues.length === 0) {
    console.log(`\n✓ No issues found. Session file is valid.`);
    return { repaired: false, issues: [] };
  }

  if (dryRun) {
    console.log(`\n[DRY RUN] Would repair ${issues.length} issue(s)`);
    return { repaired: false, issues, dryRun: true };
  }

  // 备份原文件
  const backupPath = `${filePath}.backup-${Date.now()}`;
  await copyFile(filePath, backupPath);
  console.log(`\n✓ Backup created: ${backupPath}`);

  // 写入修复后的文件
  const repairedContent = repaired.join('\n') + '\n';
  const compressed = await gzip(Buffer.from(repairedContent, 'utf-8'));
  await writeFile(filePath, compressed);
  console.log(`✓ Repaired session written to: ${filePath}`);

  return { repaired: true, issues, backupPath };
}

/**
 * 主函数
 */
async function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
    console.log(`
DSH Session Repair Tool

Usage:
  node session-repair.mjs [options] <session-file>

Options:
  --dry-run    Show what would be repaired without making changes
  --help, -h   Show this help message

Examples:
  # Check a session file for issues
  node session-repair.mjs --dry-run /path/to/session.jsonl.zstd

  # Repair a session file
  node session-repair.mjs /path/to/session.jsonl.zstd
`);
    process.exit(0);
  }

  const dryRun = args.includes('--dry-run');
  const filePath = args.find(arg => !arg.startsWith('--'));

  if (!filePath) {
    console.error('Error: No session file specified');
    process.exit(1);
  }

  try {
    const result = await repairSessionFile(filePath, dryRun);
    
    console.log(`\n${'='.repeat(80)}`);
    if (result.repaired) {
      console.log(`✓ Session repaired successfully`);
      console.log(`  Issues fixed: ${result.issues.length}`);
      console.log(`  Backup: ${result.backupPath}`);
    } else if (result.dryRun) {
      console.log(`✓ Dry run completed`);
    } else {
      console.log(`✓ No repairs needed`);
    }
    
    process.exit(0);
  } catch (err) {
    console.error(`\nError: ${err.message}`);
    console.error(err.stack);
    process.exit(1);
  }
}

main();
