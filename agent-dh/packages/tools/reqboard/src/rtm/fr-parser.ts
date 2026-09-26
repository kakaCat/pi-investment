import { readFileSync, readdirSync } from 'fs';
import { join } from 'path';
import type { FRMetadata } from '../types/rtm.js';

/**
 * 解析单个 FR 文件
 * @param filePath FR 文件的完整路径
 * @returns FR 元数据
 */
export function parseFRFile(filePath: string): FRMetadata {
  const content = readFileSync(filePath, 'utf-8');
  const lines = content.split('\n');
  
  // 1. 提取 FR ID 和标题（第一行：# FR-1: 标题）
  const titleLine = lines[0] || '';
  const titleMatch = titleLine.match(/^#\s+(FR-\d+):\s+(.+)$/);
  if (!titleMatch) {
    throw new Error(`Invalid FR file format: ${filePath}, first line must be "# FR-N: title"`);
  }
  
  const id = titleMatch[1];
  const title = titleMatch[2].trim();
  
  // 2. 提取 priority（从 front-matter，如果有）
  let priority = 'P1'; // 默认优先级
  if (lines[1] === '---') {
    // 有 front-matter
    for (let i = 2; i < lines.length; i++) {
      if (lines[i] === '---') break;
      const match = lines[i].match(/^priority:\s*(.+)$/);
      if (match) {
        priority = match[1].trim();
        break;
      }
    }
  }
  
  // 3. 提取验收标准
  const acceptanceCriteria: FRMetadata['acceptance_criteria'] = [];
  let inAcceptanceSection = false;
  let inVerificationBlock = false; // 是否在 **验收标准** 块中
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    // 检测进入验收标准章节（## 3. 验收标准）
    if (line.match(/^##\s+3\.\s+验收标准/)) {
      inAcceptanceSection = true;
      continue;
    }
    
    // 检测进入验收标准块（**验收标准**:）
    if (line.match(/^\*\*验收标准\*\*[:：]/)) {
      inVerificationBlock = true;
      continue;
    }
    
    // 检测退出验收标准章节（下一个 ## 章节）
    if (inAcceptanceSection && line.match(/^##\s+[4-9]/)) {
      break;
    }
    
    // 格式 1：完整格式（- **A1**: 描述）
    if (inAcceptanceSection) {
      const match1 = line.match(/^\s*-\s*\*\*([AQD]\d+)\*\*:\s+(.+)$/);
      if (match1) {
        const suffix = match1[1];
        const acceptanceId = `${id}-${suffix}`;
        const description = match1[2].trim();
        
        // 查找下一行的验证方式
        let verification = '';
        if (i + 1 < lines.length) {
          const nextLine = lines[i + 1];
          const verifyMatch = nextLine.match(/^\s+验证[：:]\s*(.+)$/);
          if (verifyMatch) {
            verification = verifyMatch[1].trim();
          }
        }
        
        acceptanceCriteria.push({
          id: acceptanceId,
          description,
          verification
        });
        continue;
      }
    }
    
    // 格式 2：简短格式（- A1: 描述）
    if (inVerificationBlock) {
      const match2 = line.match(/^\s*-\s*([AQD]\d+):\s+(.+)$/);
      if (match2) {
        const suffix = match2[1];
        const acceptanceId = `${id}-${suffix}`;
        const description = match2[2].trim();
        
        acceptanceCriteria.push({
          id: acceptanceId,
          description,
          verification: '' // 简短格式通常没有单独的验证说明
        });
      }
    }
  }
  
  return {
    id,
    title,
    priority,
    file: filePath,
    acceptance_criteria: acceptanceCriteria
  };
}

/**
 * 扫描 FR 目录，解析所有 FR 文件
 * @param reqDir 需求目录（如 docs/requirements/REQ-xxx）
 * @returns FR 元数据列表
 */
export function scanFRDirectory(reqDir: string): FRMetadata[] {
  const frDir = join(reqDir, 'functional-requirements');
  
  try {
    const files = readdirSync(frDir);
    const frFiles = files.filter(f => f.match(/^FR-\d+-.*\.md$/));
    
    const results: FRMetadata[] = [];
    for (const file of frFiles) {
      const filePath = join(frDir, file);
      try {
        const metadata = parseFRFile(filePath);
        results.push(metadata);
      } catch (error) {
        console.warn(`Failed to parse FR file ${file}:`, error);
        // 继续处理其他文件
      }
    }
    
    return results;
  } catch (error) {
    // 目录不存在或读取失败，返回空数组
    return [];
  }
}
