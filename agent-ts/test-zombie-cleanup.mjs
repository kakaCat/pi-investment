#!/usr/bin/env node
/**
 * 测试：僵尸进程清理
 * 测试 backend_control 能否清理已死但 PID 文件仍存在的进程记录
 */

import { startService, stopService, savePid, loadPids } from './dist/infrastructure/tools/agent/backend-control-tool.js';
import { mkdirSync, rmSync, existsSync } from 'fs';
import { join } from 'path';

const TEST_DIR = join(process.cwd(), '.backend-zombie-test');

async function testZombieProcessCleanup() {
  console.log('🧪 僵尸进程清理测试\n');
  console.log('='.repeat(60));

  try {
    // 清理测试目录
    if (existsSync(TEST_DIR)) {
      rmSync(TEST_DIR, { recursive: true });
    }
    mkdirSync(TEST_DIR, { recursive: true });

    // 场景：模拟僵尸进程（PID 存在但进程已死）
    console.log('\n📝 场景：僵尸进程清理');
    console.log('-'.repeat(60));

    const zombiePid = 99999; // 一个不存在的 PID
    console.log(`   创建僵尸 PID 记录: ${zombiePid}`);
    savePid('rest', zombiePid, TEST_DIR);

    const pids = loadPids(TEST_DIR);
    console.log(`   PID 文件内容:`, pids);

    console.log('\n   尝试启动服务（应该自动清理僵尸 PID）...');
    const result = await startService('rest', TEST_DIR, undefined, undefined, { autoCleanupPortConflict: true });

    if (result.success) {
      console.log('✅ 成功启动（自动清理了僵尸进程）');
      console.log(`   新 PID: ${result.pid}`);
      console.log(`   消息: ${result.message}`);

      // 验证 PID 已更新
      const updatedPids = loadPids(TEST_DIR);
      console.log(`   更新后的 PID: ${updatedPids.rest?.pid}`);

      if (updatedPids.rest?.pid === result.pid && result.pid !== zombiePid) {
        console.log(`   ✅ 确认：僵尸 PID (${zombiePid}) 已被清理`);
      }

      // 清理服务
      console.log('\n   停止服务...');
      await stopService('rest', TEST_DIR);
      console.log('   ✅ 服务已停止');
    } else {
      console.log('❌ 启动失败');
      console.log(`   错误: ${result.error}`);
      if (result.diagnostics) {
        console.log(`   诊断:`, result.diagnostics);
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
testZombieProcessCleanup();
