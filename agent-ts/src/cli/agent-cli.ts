#!/usr/bin/env node
/**
 * Agent CLI - 提供命令行接口供quantsys-v2 scheduler调用
 *
 * 架构原则：
 * - Agent不应该有自己的scheduler
 * - Agent应该被Backend的scheduler触发
 * - 这个CLI是Agent对外的唯一调度接口
 */

import { Command } from 'commander';

const program = new Command();

program
  .name('agent-cli')
  .description('PI Investment AI Agent CLI - 被quantsys-v2 scheduler调用')
  .version('1.0.0');

/**
 * 早盘分析任务
 * 由quantsys-v2 scheduler在交易日9:00触发
 */
program
  .command('morning-analysis')
  .description('早盘分析 + 虚拟仓交易决策')
  .option('--account <name>', '账户名称', 'default')
  .option('--dry-run', '模拟运行，不执行实际交易')
  .action(async (options) => {
    console.log('🌅 开始早盘分析任务...');
    console.log(`账户: ${options.account}`);
    console.log(`模式: ${options.dryRun ? '模拟' : '实盘'}`);

    try {
      // TODO: 调用agent的早盘分析逻辑
      // 1. 检查持仓
      // 2. 分析市场
      // 3. 执行交易决策

      console.log('✅ 早盘分析任务完成');
      process.exit(0);
    } catch (error) {
      console.error('❌ 早盘分析任务失败:', error);
      process.exit(1);
    }
  });

/**
 * V13策略执行
 * 由quantsys-v2 scheduler触发
 */
program
  .command('run-strategy')
  .description('执行指定策略')
  .requiredOption('-s, --strategy <id>', '策略ID (v13, v14等)')
  .option('--account <name>', '账户名称', 'default')
  .option('--force', '强制调仓')
  .action(async (options) => {
    console.log(`🚀 开始执行策略: ${options.strategy}`);
    console.log(`账户: ${options.account}`);
    console.log(`强制调仓: ${options.force ? '是' : '否'}`);

    try {
      // 调用quantsys-v2 API执行策略
      const response = await fetch('http://127.0.0.1:5001/api/simulation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: options.strategy,
          account_name: options.account,
          force_rebalance: options.force || false
        })
      });

      const result = await response.json() as {
        success: boolean;
        data: { signals_count: number; trades_count: number };
        error?: string;
      };

      if (result.success) {
        console.log('✅ 策略执行成功');
        console.log(`信号数: ${result.data.signals_count}`);
        console.log(`交易数: ${result.data.trades_count}`);
      } else {
        console.error('❌ 策略执行失败:', result.error);
        process.exit(1);
      }

      process.exit(0);
    } catch (error) {
      console.error('❌ 策略执行失败:', error);
      process.exit(1);
    }
  });

/**
 * 每日复盘
 * 由quantsys-v2 scheduler在交易日15:35触发
 */
program
  .command('daily-review')
  .description('每日持仓复盘分析')
  .option('--account <name>', '账户名称', 'default')
  .action(async (options) => {
    console.log('📊 开始每日复盘...');
    console.log(`账户: ${options.account}`);

    try {
      // TODO: 调用agent的复盘分析逻辑
      // 1. 获取今日交易记录
      // 2. 分析盈亏
      // 3. 总结经验教训
      // 4. 发送飞书通知

      console.log('✅ 每日复盘完成');
      process.exit(0);
    } catch (error) {
      console.error('❌ 每日复盘失败:', error);
      process.exit(1);
    }
  });

/**
 * 健康检查
 */
program
  .command('health')
  .description('检查Agent服务状态')
  .action(async () => {
    try {
      // 检查quantsys-v2后端连接
      const response = await fetch('http://127.0.0.1:5001/api/health');
      const health = await response.json() as {
        status: string;
        db_connected: boolean;
      };

      if (health.status === 'ok') {
        console.log('✅ Agent服务正常');
        console.log(`后端连接: ${health.db_connected ? '正常' : '异常'}`);
        process.exit(0);
      } else {
        console.error('❌ Agent服务异常');
        process.exit(1);
      }
    } catch (error) {
      console.error('❌ 健康检查失败:', error);
      process.exit(1);
    }
  });

program.parse();
