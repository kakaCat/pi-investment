import { AgentDHClient } from '@pi-investment/agent-dh-client';

/**
 * 示例 3: 股票池管理
 * 
 * 这个示例展示如何：
 * 1. 创建股票池
 * 2. 添加股票成员
 * 3. 查询池成员
 * 4. 刷新股票池
 * 5. 管理多个股票池
 */

async function main() {
  console.log('=== 股票池管理示例 ===\n');

  // 创建客户端
  const client = AgentDHClient.createDefault();

  // 1. 列出现有股票池
  console.log('[1] 查询现有股票池...\n');
  
  const existingPools = await client.quantsysV2.listPools();
  console.log(`    当前有 ${existingPools.length} 个股票池:`);
  existingPools.slice(0, 5).forEach((pool, index) => {
    console.log(`    ${index + 1}. ${pool.name} (成员: ${pool.member_count || 0})`);
  });
  console.log();

  // 2. 创建新股票池
  console.log('[2] 创建新股票池...\n');

  const pool = await client.quantsysV2.createPool({
    name: '高 ROE 价值池',
    description: 'ROE > 15%, 负债率 < 60% 的优质公司',
  });

  console.log(`    ✓ 股票池已创建`);
  console.log(`      ID: ${pool.id}`);
  console.log(`      名称: ${pool.name}`);
  console.log();

  // 3. 添加股票成员
  console.log('[3] 添加股票成员...\n');

  const stocks = [
    { symbol: '600519.SH', name: '贵州茅台', roe: 30.5 },
    { symbol: '600036.SH', name: '招商银行', roe: 16.8 },
    { symbol: '000858.SZ', name: '五粮液', roe: 22.3 },
    { symbol: '601318.SH', name: '中国平安', roe: 17.2 },
  ];

  for (const stock of stocks) {
    await client.quantsysV2.addPoolMember(pool.id, {
      symbol: stock.symbol,
      metadata: {
        name: stock.name,
        roe: stock.roe,
        added_by: 'manual',
        reason: '高ROE优质股',
      },
    });
    console.log(`    ✓ 已添加: ${stock.name} (${stock.symbol}), ROE: ${stock.roe}%`);
  }
  console.log();

  // 4. 查询池成员
  console.log('[4] 查询池成员...\n');

  const members = await client.quantsysV2.getPoolMembers(pool.id);
  console.log(`    股票池 "${pool.name}" 当前有 ${members.length} 个成员:\n`);

  members.forEach((member, index) => {
    const metadata = member.metadata || {};
    console.log(`    ${index + 1}. ${metadata.name || member.symbol}`);
    console.log(`       代码: ${member.symbol}`);
    console.log(`       ROE: ${metadata.roe || 'N/A'}%`);
    console.log(`       加入时间: ${new Date(member.added_at).toLocaleDateString()}`);
    console.log();
  });

  // 5. 获取池信息
  console.log('[5] 获取池详细信息...\n');

  const poolInfo = await client.quantsysV2.getPool(pool.id);
  console.log('    股票池详情:');
  console.log(`    ┌─────────────────────────────────────┐`);
  console.log(`    │ 名称: ${poolInfo.name}`);
  console.log(`    │ 描述: ${poolInfo.description}`);
  console.log(`    │ 成员数: ${members.length}`);
  console.log(`    │ 创建时间: ${new Date(poolInfo.created_at).toLocaleString()}`);
  console.log(`    └─────────────────────────────────────┘\n`);

  // 6. 刷新股票池（重新扫描）
  console.log('[6] 刷新股票池...\n');
  
  console.log('    提示: 刷新股票池将重新扫描并更新成员');
  // await client.quantsysV2.refreshPool(pool.id);
  // console.log("    ✓ 股票池已刷新");
  console.log();

  // 7. 移除成员
  console.log('[7] 移除成员...\n');

  if (members.length > 0) {
    const memberToRemove = members[members.length - 1];
    console.log(`    移除: ${memberToRemove.symbol}`);
    
    await client.quantsysV2.removePoolMember(pool.id, memberToRemove.symbol);
    console.log(`    ✓ 已移除 ${memberToRemove.symbol}`);
    
    const updatedMembers = await client.quantsysV2.getPoolMembers(pool.id);
    console.log(`    当前成员数: ${updatedMembers.length}`);
    console.log();
  }

  // 8. 池管理最佳实践
  console.log('[8] 股票池管理最佳实践:\n');
  console.log('    1. 定期刷新股票池（每日/每周）');
  console.log('    2. 设置明确的筛选条件');
  console.log('    3. 记录成员变化原因（metadata）');
  console.log('    4. 监控池的表现和风险');
  console.log('    5. 结合策略回测验证池的有效性\n');

  // 9. 清理（可选）
  console.log('[9] 清理示例数据...\n');
  console.log('    提示: 如需删除股票池，使用:');
  console.log(`    await client.quantsysV2.deletePool(${pool.id});\n`);

  console.log('=== 示例完成 ===');
}

// 运行示例
main().catch((error) => {
  console.error('❌ 错误:', error);
  process.exit(1);
});
