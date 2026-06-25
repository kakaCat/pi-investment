/**
 * 批量修复工具返回类型
 *
 * 此脚本扫描所有工具文件，将返回 string 的改为返回 AgentToolResult
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 需要修复的目录
const toolsDirs = [
  'src/infrastructure/tools/analysis',
  'src/infrastructure/tools/invest',
  'src/infrastructure/tools/data',
  'src/infrastructure/tools/market',
  'src/infrastructure/tools/strategy',
  'src/infrastructure/tools/risk',
  'src/infrastructure/tools/factor',
  'src/infrastructure/tools/model',
  'src/infrastructure/tools/report',
  'src/infrastructure/tools/monitor',
  'src/infrastructure/tools/core',
  'src/infrastructure/tools/signal',
];

function fixFile(filePath: string): boolean {
  console.log(`检查文件: ${filePath}`);

  let content = fs.readFileSync(filePath, 'utf-8');
  let modified = false;

  // 1. 添加导入语句（如果还没有）
  if (!content.includes('wrapToolResult')) {
    const importLine = `import { wrapToolResult, wrapToolError } from '../utils/tool-result-wrapper.js';\n`;

    // 找到最后一个 import 语句的位置
    const importRegex = /^import .+ from .+;$/gm;
    const matches = Array.from(content.matchAll(importRegex));

    if (matches.length > 0) {
      const lastImport = matches[matches.length - 1];
      const insertPos = lastImport.index! + lastImport[0].length + 1;
      content = content.slice(0, insertPos) + importLine + content.slice(insertPos);
      modified = true;
      console.log(`  ✓ 添加了导入语句`);
    }
  }

  // 2. 修复简单的 return output; 语句（在 execute 方法内）
  // 匹配模式: return output; 且前面有足够的缩进（在方法内部）
  const simpleReturnRegex = /^(\s{6,})return output;$/gm;
  if (simpleReturnRegex.test(content)) {
    content = content.replace(simpleReturnRegex, '$1return wrapToolResult(output);');
    modified = true;
    console.log(`  ✓ 修复了简单 return 语句`);
  }

  // 3. 修复错误返回语句 - 已经是对象形式但缺少 details
  const errorReturnRegex = /return \{ content: \[(.*?)\] \};/g;
  content = content.replace(errorReturnRegex, (match, contentPart) => {
    if (!match.includes('details:')) {
      return `return { content: [${contentPart}], details: {} };`;
    }
    return match;
  });

  if (modified) {
    fs.writeFileSync(filePath, content, 'utf-8');
    console.log(`  ✅ 文件已修复: ${filePath}`);
    return true;
  }

  return false;
}

function scanAndFix() {
  let totalFixed = 0;

  for (const dir of toolsDirs) {
    const fullPath = path.join(__dirname, '..', dir);

    if (!fs.existsSync(fullPath)) {
      console.log(`⚠️  目录不存在: ${fullPath}`);
      continue;
    }

    const files = fs.readdirSync(fullPath)
      .filter(f => f.endsWith('.ts') && !f.endsWith('.test.ts') && f.includes('-tool'));

    console.log(`\n📁 扫描目录: ${dir} (${files.length} 个工具文件)`);

    for (const file of files) {
      const filePath = path.join(fullPath, file);
      if (fixFile(filePath)) {
        totalFixed++;
      }
    }
  }

  console.log(`\n✅ 完成！共修复 ${totalFixed} 个文件`);
}

// 运行修复
scanAndFix();
