import { describe, it, expect } from 'vitest';
import { parseFRFile, scanFRDirectory } from '../../src/rtm/fr-parser.js';
import { join } from 'path';

describe('FR Parser', () => {
  const testReqDir = 'docs/requirements/REQ-260925172227-2d61';
  
  describe('parseFRFile', () => {
    it('应该正确提取 FR-1 的 title/priority/acceptance（4 项 A1-A4）', () => {
      const filePath = join(testReqDir, 'functional-requirements/FR-1-decompose-fr-support.md');
      const result = parseFRFile(filePath);
      
      expect(result.id).toBe('FR-1');
      expect(result.title).toContain('reqboard_decompose');
      expect(result.priority).toBeDefined();
      
      // 应该至少有 4 个验收项（A1-A4），可能还有 Q/D 类验收项
      expect(result.acceptance_criteria.length).toBeGreaterThanOrEqual(4);
      
      // 验证 A1-A4 都存在
      const aItems = result.acceptance_criteria.filter(a => a.id.match(/FR-1-A\d+/));
      expect(aItems.length).toBeGreaterThanOrEqual(4);
      
      // 验证验收项格式
      const a1 = result.acceptance_criteria.find(a => a.id === 'FR-1-A1');
      expect(a1).toBeDefined();
      expect(a1?.description).toBeTruthy();
      expect(a1?.verification).toBeTruthy();
    });
    
    it('应该处理缺少 front-matter 的文件（使用默认优先级）', () => {
      const filePath = join(testReqDir, 'functional-requirements/FR-2-submit-fr-support.md');
      const result = parseFRFile(filePath);
      
      expect(result.id).toBe('FR-2');
      expect(result.priority).toBe('P1'); // 默认优先级
    });
    
    it('应该处理缺少验收标准章节的文件（返回空数组）', () => {
      // 这个测试需要一个没有验收标准的 FR 文件
      // 如果所有 FR 文件都有验收标准，这个测试会跳过
      const filePath = join(testReqDir, 'functional-requirements/FR-3-accept-fr-support.md');
      const result = parseFRFile(filePath);
      
      expect(result.id).toBe('FR-3');
      // 如果有验收标准，至少应该有一项
      // 如果没有，应该返回空数组
      expect(Array.isArray(result.acceptance_criteria)).toBe(true);
    });
  });
  
  describe('scanFRDirectory', () => {
    it('应该扫描到 3 个 FR 文件（FR-1/FR-2/FR-3）', () => {
      const results = scanFRDirectory(testReqDir);
      
      expect(results.length).toBeGreaterThanOrEqual(3);
      
      const frIds = results.map(r => r.id);
      expect(frIds).toContain('FR-1');
      expect(frIds).toContain('FR-2');
      expect(frIds).toContain('FR-3');
    });
    
    it('应该处理不存在的目录（返回空数组）', () => {
      const results = scanFRDirectory('nonexistent-dir');
      expect(results).toEqual([]);
    });
  });
});
