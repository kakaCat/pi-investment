#!/usr/bin/env node

/**
 * 测试 market_cli 工具的 market.news 功能
 */

import { marketCliTool } from './dist/infrastructure/tools/index.js';

console.log('Testing market_cli tool...\n');

async function test() {
    try {
        // 测试 market.news 命令
        console.log('Executing: market_cli({ command: "market.news", params: { limit: 3 } })');
        const result = await marketCliTool.handler({
            command: 'market.news',
            params: { limit: 3 }
        });

        console.log('\n✅ Success! Result:');
        console.log(JSON.stringify(result, null, 2));

        if (result.data && result.data.news) {
            console.log(`\n📰 Retrieved ${result.data.news.length} news items`);
            console.log('\nFirst news item:');
            const first = result.data.news[0];
            console.log(`  标题: ${first.新闻标题}`);
            console.log(`  时间: ${first.发布时间}`);
            console.log(`  来源: ${first.文章来源}`);
        }

    } catch (error) {
        console.error('❌ Error:', error.message);
        process.exit(1);
    }
}

test();
