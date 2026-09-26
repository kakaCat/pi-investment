#!/usr/bin/env tsx
/**
 * RTM 文件修复脚本：为缺失 RTM 文件的需求补生成
 * 
 * 用法：
 *   tsx scripts/fix-missing-rtm.ts REQ-260926205654-163a
 *   tsx scripts/fix-missing-rtm.ts --all  # 修复所有需求
 */
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { RTMGenerator, runRTMTrigger } from '../src/application/internal/rtm-yaml.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const workspaceRoot = process.cwd()
const requirementsDir = join(workspaceRoot, 'docs/requirements')
const ledgerPath = join(workspaceRoot, '.dsh-data/dsh-reqboard.json')

async function loadLedger() {
  if (!existsSync(ledgerPath)) {
    console.error('❌ 台账文件不存在：', ledgerPath)
    process.exit(1)
  }
  const ledger = JSON.parse(await import('node:fs/promises').then(m => 
    m.readFile(ledgerPath, 'utf-8')
  ))
  return ledger
}

async function fixRequirement(reqId: string) {
  console.log(`\n🔧 修复需求：${reqId}`)
  
  const ledger = await loadLedger()
  const req = ledger.requirements.find((r: RequirementRecord) => r.id === reqId)
  
  if (!req) {
    console.error(`❌ 需求不存在于台账：${reqId}`)
    return false
  }
  
  const reqDir = join(requirementsDir, reqId)
  if (!existsSync(reqDir)) {
    console.error(`❌ 需求目录不存在：${reqDir}`)
    return false
  }
  
  console.log(`  状态：${req.status}`)
  console.log(`  分类：${req.category}`)
  
  // 检查应该有哪些 RTM 文件
  const expectedFiles: string[] = []
  if (req.status !== 'draft') expectedFiles.push('rtm-lifecycle.yml')
  if (['brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'archived', 'done'].includes(req.status)) {
    expectedFiles.push('rtm-brainstorming.yml')
  }
  if (['design', 'decomposing', 'implementing', 'accepting', 'archived', 'done'].includes(req.status)) {
    expectedFiles.push('rtm-design.yml')
  }
  if (['decomposing', 'implementing', 'accepting', 'archived', 'done'].includes(req.status)) {
    expectedFiles.push('rtm-decomposing.yml', 'rtm-implementing.yml')
  }
  if (['accepting', 'archived', 'done'].includes(req.status)) {
    expectedFiles.push('rtm-accepting.yml')
  }
  
  const missingFiles = expectedFiles.filter(f => !existsSync(join(reqDir, f)))
  
  if (missingFiles.length === 0) {
    console.log(`  ✅ 所有 RTM 文件都存在`)
    return true
  }
  
  console.log(`  ⚠️  缺失文件：${missingFiles.join(', ')}`)
  
  // 尝试生成
  const generator = new RTMGenerator({
    workspaceRoot,
    ledger: {
      requirement: (id: string) => ledger.requirements.find((r: any) => r.id === id),
      tasksOf: (reqId: string) => ledger.tasks.filter((t: any) => t.requirementId === reqId),
    },
    generatedBy: 'fix-script',
    enabledStagesOf: () => ['draft', 'brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'done'],
  })
  
  let success = true
  
  // 按顺序生成各个 RTM 文件
  if (missingFiles.includes('rtm-lifecycle.yml')) {
    console.log(`  🔄 生成 rtm-lifecycle.yml...`)
    const result = runRTMTrigger(generator, 'create', reqId)
    if (result.ok) {
      console.log(`    ✅ 已生成`)
    } else {
      console.log(`    ❌ 失败：${result.error}`)
      success = false
    }
  }
  
  if (missingFiles.includes('rtm-brainstorming.yml')) {
    console.log(`  🔄 生成 rtm-brainstorming.yml...`)
    const result = runRTMTrigger(generator, 'submit:requirement', reqId)
    if (result.ok) {
      console.log(`    ✅ 已生成`)
    } else {
      console.log(`    ❌ 失败：${result.error}`)
      success = false
    }
  }
  
  if (missingFiles.includes('rtm-design.yml')) {
    console.log(`  🔄 生成 rtm-design.yml...`)
    const result = runRTMTrigger(generator, 'submit:design', reqId)
    if (result.ok) {
      console.log(`    ✅ 已生成`)
    } else {
      console.log(`    ❌ 失败：${result.error}`)
      success = false
    }
  }
  
  if (missingFiles.includes('rtm-decomposing.yml') || missingFiles.includes('rtm-implementing.yml')) {
    console.log(`  🔄 生成 rtm-decomposing.yml 和 rtm-implementing.yml...`)
    const result = runRTMTrigger(generator, 'confirm:plan', reqId)
    if (result.ok) {
      console.log(`    ✅ 已生成`)
    } else {
      console.log(`    ❌ 失败：${result.error}`)
      success = false
    }
  }
  
  return success
}

async function main() {
  const args = process.argv.slice(2)
  
  if (args.length === 0 || args.includes('--help')) {
    console.log(`
用法：
  tsx scripts/fix-missing-rtm.ts REQ-xxx        # 修复单个需求
  tsx scripts/fix-missing-rtm.ts --all          # 修复所有需求
  tsx scripts/fix-missing-rtm.ts --help         # 显示帮助
`)
    process.exit(0)
  }
  
  if (args.includes('--all')) {
    const ledger = await loadLedger()
    console.log(`📋 找到 ${ledger.requirements.length} 个需求`)
    
    let fixed = 0
    let failed = 0
    
    for (const req of ledger.requirements) {
      const success = await fixRequirement(req.id)
      if (success) fixed++
      else failed++
    }
    
    console.log(`\n✅ 完成：${fixed} 个成功，${failed} 个失败`)
  } else {
    const reqId = args[0]
    const success = await fixRequirement(reqId)
    process.exit(success ? 0 : 1)
  }
}

main().catch(err => {
  console.error('❌ 脚本执行失败：', err)
  process.exit(1)
})
