#!/usr/bin/env node
/**
 * Agent-DH 启动入口
 *
 * 基于 DeepSeek Harness 框架的独立应用启动器
 */

import { Context } from '@deepseek-ai/cordis';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import YAML from 'yaml';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const projectRoot = resolve(__dirname, '..');

interface StartOptions {
  port?: number;
  config?: string;
  verbose?: boolean;
}

/**
 * 加载插件配置
 */
function loadConfig(configPath: string) {
  const configFile = resolve(projectRoot, configPath);
  const content = readFileSync(configFile, 'utf-8');
  return YAML.parse(content);
}

/**
 * 启动 Agent-DH
 */
export async function start(options: StartOptions = {}) {
  const {
    port = 13080,
    config = 'config/cordis.yml',
    verbose = false,
  } = options;

  console.log('========================================');
  console.log('  Agent-DH 启动中...');
  console.log('========================================');
  console.log(`端口: ${port}`);
  console.log(`配置: ${config}`);
  console.log(`项目根目录: ${projectRoot}`);
  console.log('');

  // 创建 Cordis 上下文
  const ctx = new Context();

  // 加载配置文件
  const pluginConfigs = loadConfig(config);

  if (verbose) {
    console.log('加载插件配置:', JSON.stringify(pluginConfigs, null, 2));
  }

  // 加载插件
  for (const pluginConfig of pluginConfigs) {
    if (pluginConfig.disabled) {
      console.log(`⊘ 跳过禁用插件: ${pluginConfig.id}`);
      continue;
    }

    if (pluginConfig.insert) {
      // 批量插入插件
      for (const plugin of pluginConfig.insert) {
        await loadPlugin(ctx, plugin, verbose);
      }
    } else {
      // 单个插件
      await loadPlugin(ctx, pluginConfig, verbose);
    }
  }

  console.log('');
  console.log('✓ Agent-DH 启动完成');
  console.log(`✓ 监听端口: ${port}`);
  console.log('');

  // 保持进程运行
  process.on('SIGINT', () => {
    console.log('\n正在关闭 Agent-DH...');
    ctx.dispose();
    process.exit(0);
  });

  return ctx;
}

/**
 * 加载单个插件
 */
async function loadPlugin(ctx: Context, pluginConfig: any, verbose: boolean) {
  if (!pluginConfig.name) {
    return;
  }

  try {
    if (verbose) {
      console.log(`→ 加载插件: ${pluginConfig.name} (id: ${pluginConfig.id})`);
    }

    const module = await import(pluginConfig.name);
    const Plugin = module.default || module;

    ctx.plugin(Plugin, pluginConfig.config || {});

    console.log(`✓ ${pluginConfig.id}`);
  } catch (error) {
    console.error(`✗ 加载插件失败: ${pluginConfig.name}`);
    console.error(error);
  }
}

// CLI 入口
if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const options: StartOptions = {};

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--port':
      case '-p':
        options.port = parseInt(args[++i], 10);
        break;
      case '--config':
      case '-c':
        options.config = args[++i];
        break;
      case '--verbose':
      case '-v':
        options.verbose = true;
        break;
      case '--help':
      case '-h':
        console.log(`
Agent-DH 启动器

用法:
  npm start                    # 默认端口 13080
  npm start -- --port 13081    # 指定端口
  npm start -- --verbose       # 详细日志

选项:
  --port, -p <port>           监听端口 (默认: 13080)
  --config, -c <path>         配置文件路径 (默认: config/cordis.yml)
  --verbose, -v               显示详细日志
  --help, -h                  显示帮助信息
`);
        process.exit(0);
    }
  }

  start(options).catch((error) => {
    console.error('启动失败:', error);
    process.exit(1);
  });
}
