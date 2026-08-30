#!/usr/bin/env node
/**
 * 真实场景测试：端口冲突自动清理
 * 测试 backend_control 工具是否能自动清理端口冲突
 */

import { startService, stopService, savePid, loadPids } from './dist/infrastructure/tools/agent/backend-control-tool.js';
import { mkdirSync, rmSync, existsSync } from 'fs';
import { join } from 'path';

const TEST_DIR = join(process.cwd(), '.backend-port-test');

async function testPortConflictAutoCleanup() {
  console.log('🧪 端口冲突自动清理测试\n');
  console.log('='.repeat(60));

  try {
    // 清理测试目录
    if (existsSync(TEST_DIR)) {
      rmSync(TEST_DIR, { recursive: true });
    }
    mkdirSync(TEST_DIR, { recursive: true });

    // 场景1：正常启动（无冲突）
    console.log('\n📝 场景1：正常启动服务');
    console.log('-'.repeat(60));
    const result1 = await startService('rest', TEST_DIR, undefined, undefined, { autoCleanupPortConflict: true });

    if (result1.success) {
      console.log('✅ 成功启动');
      console.log(`   PID: ${result1.pid}`);
      console.log(`   消息: ${result1.message}`);

      // 等待服务稳定
      await new Promise(resolve => setTimeout(resolve, 2000));

      // 场景2：尝试重复启动（应该检测到端口冲突并自动清理）
      console.log('\n📝 场景2：重复启动（测试端口冲突自动清理）');
      console.log('-'.repeat(60));
      console.log(`   当前服务 PID: ${result1.pid}`);
      console.log('   尝试再次启动...');

      const result2 = await startService('rest', TEST_DIR, undefined, undefined, { autoCleanupPortConflict: true });

      if (result2.success) {
        console.log('✅ 成功重启（自动清理了旧进程）');
        console.log(`   新 PID: ${result2.pid}`);
        console.log(`   消息: ${result2.message}`);

        if (result2.pid !== result1.pid) {
          console.log(`   ✅ 确认：新进程 PID (${result2.pid}) ≠ 旧进程 PID (${result1.pid})`);
        }

        // 清理新服务
        await stopService('rest', TEST_DIR);
      } else {
        console.log('❌ 重启失败');
        console.log(`   错误: ${result2.error}`);
        if (result2.diagnostics) {
          console.log(`   诊断: ${JSON.stringify(result2.diagnostics, null, 2)}`);
        }

        // 手动清理第一次启动的服务
        await stopService('rest', TEST_DIR);
      }
    } else {
      console.log('❌ 启动失败');
      console.log(`   错误: ${result1.error}`);
      if (result1.diagnostics) {
        console.log(`   诊断: ${JSON.stringify(result1.diagnostics, null, 2)}`);
      }
    }

    console.log('\n' + '='.repeat(60));
    console.log('✅ 测试完成\n');

  } catch (error) {
    console.error('\n❌ 测试失败:', error.message);
    console.error(error.stack);
  } finally {
    // 清理测试目录
    if (existsSync(TEST_DIR)) {
      rmSync(TEST_DIR, { recursive: true });
    }
  }
}

// 运行测试
testPortConflictAutoCleanup();
