/**
 * 股票池工具简化测试
 * 验证核心功能和优化项
 */

import { describe, it, expect } from '@jest/globals';

describe('股票池工具优化验证', () => {
  describe('代码质量检查', () => {
    it('应该没有 as any 类型断言', async () => {
      const fs = await import('fs/promises');
      const manageContent = await fs.readFile(
        'src/infrastructure/tools/pool/pool-manage-tool.ts',
        'utf-8'
      );
      const validateContent = await fs.readFile(
        'src/infrastructure/tools/pool/pool-validate-tool.ts',
        'utf-8'
      );

      expect(manageContent).not.toContain('as any');
      expect(validateContent).not.toContain('as any');
    });

    it('应该包含分页参数定义', async () => {
      const fs = await import('fs/promises');
      const content = await fs.readFile(
        'src/infrastructure/tools/pool/pool-manage-tool.ts',
        'utf-8'
      );

      expect(content).toContain('max_buy_signals');
      expect(content).toContain('max_sell_signals');
    });

    it('应该包含超时估算逻辑', async () => {
      const fs = await import('fs/promises');
      const content = await fs.readFile(
        'src/infrastructure/tools/pool/pool-validate-tool.ts',
        'utf-8'
      );

      expect(content).toContain('estimatedSeconds');
      expect(content).toContain('预计需要约');
    });

    it('应该包含错误示例参数', async () => {
      const fs = await import('fs/promises');
      const content = await fs.readFile(
        'src/infrastructure/tools/pool/pool-manage-tool.ts',
        'utf-8'
      );

      expect(content).toContain('example?: string');
      expect(content).toContain('💡 示例');
    });

    it('应该有统一的配置文件', async () => {
      const fs = await import('fs/promises');

      // 检查文件存在
      await expect(
        fs.access('src/config/tool-thresholds.ts')
      ).resolves.toBeUndefined();

      const content = await fs.readFile(
        'src/config/tool-thresholds.ts',
        'utf-8'
      );

      expect(content).toContain('TOOL_PERSISTENCE_THRESHOLDS');
      expect(content).toContain('pool_validate');
      expect(content).toContain('pool_scan_signals');
    });

    it('pool-validate-tool 应该导入统一配置', async () => {
      const fs = await import('fs/promises');
      const content = await fs.readFile(
        'src/infrastructure/tools/pool/pool-validate-tool.ts',
        'utf-8'
      );

      expect(content).toContain('TOOL_PERSISTENCE_THRESHOLDS');
      expect(content).toContain('tool-thresholds');
    });
  });

  describe('API 接口一致性', () => {
    it('PoolSignalScanParams 应该包含新参数', async () => {
      const fs = await import('fs/promises');
      const content = await fs.readFile(
        'src/infrastructure/adapters/quant/quant-v2-client.ts',
        'utf-8'
      );

      // 查找 PoolSignalScanParams 接口定义
      const interfaceMatch = content.match(
        /export interface PoolSignalScanParams[\s\S]*?\}/
      );

      expect(interfaceMatch).toBeTruthy();
      if (interfaceMatch) {
        const interfaceContent = interfaceMatch[0];
        expect(interfaceContent).toContain('max_buy_signals');
        expect(interfaceContent).toContain('max_sell_signals');
      }
    });
  });

  describe('工具注册检查', () => {
    it('工具应该在 index.ts 中注册', async () => {
      const fs = await import('fs/promises');
      const content = await fs.readFile(
        'src/infrastructure/tools/index.ts',
        'utf-8'
      );

      expect(content).toContain('poolManageTool');
      expect(content).toContain('poolValidateTool');
      expect(content).toContain('./pool/pool-manage-tool');
      expect(content).toContain('./pool/pool-validate-tool');
    });
  });

  describe('错误信息增强检查', () => {
    it('应该为关键操作提供示例', async () => {
      const fs = await import('fs/promises');
      const content = await fs.readFile(
        'src/infrastructure/tools/pool/pool-manage-tool.ts',
        'utf-8'
      );

      // 检查是否包含示例字符串
      expect(content).toContain('"action": "create"');
      expect(content).toContain('"action": "scan_create"');
      expect(content).toContain('"action": "update_member"');
      expect(content).toContain('"action": "scan_signals"');
    });
  });

  describe('代码复杂度检查', () => {
    it('文件行数应该在合理范围内', async () => {
      const fs = await import('fs/promises');

      const manageContent = await fs.readFile(
        'src/infrastructure/tools/pool/pool-manage-tool.ts',
        'utf-8'
      );
      const validateContent = await fs.readFile(
        'src/infrastructure/tools/pool/pool-validate-tool.ts',
        'utf-8'
      );

      const manageLines = manageContent.split('\n').length;
      const validateLines = validateContent.split('\n').length;

      // pool-manage-tool 应该在 500 行以内
      expect(manageLines).toBeLessThan(500);

      // pool-validate-tool 应该在 200 行以内
      expect(validateLines).toBeLessThan(200);

      console.log(`📊 pool-manage-tool.ts: ${manageLines} 行`);
      console.log(`📊 pool-validate-tool.ts: ${validateLines} 行`);
    });
  });
});

describe('配置文件结构验证', () => {
  it('配置应该包含所有工具的阈值', async () => {
    const fs = await import('fs/promises');
    const content = await fs.readFile(
      'src/config/tool-thresholds.ts',
      'utf-8'
    );

    const expectedKeys = [
      'pool_validate',
      'pool_scan_signals',
      'factor_analyze',
      'backtest',
      'default',
    ];

    for (const key of expectedKeys) {
      expect(content).toContain(key);
    }
  });

  it('配置应该导出辅助函数', async () => {
    const fs = await import('fs/promises');
    const content = await fs.readFile(
      'src/config/tool-thresholds.ts',
      'utf-8'
    );

    expect(content).toContain('export function getThreshold');
    expect(content).toContain('export function formatThreshold');
  });
});
