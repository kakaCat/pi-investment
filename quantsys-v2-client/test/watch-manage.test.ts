/**
 * 测试 watch_manage 修复
 * 验证 parseCondition 方法能正确转换条件字符串为后端期望的数组格式
 */

import { QuantsysV2Client } from '../src/client';

describe('watch_manage bug fix', () => {
  let client: QuantsysV2Client;

  beforeEach(() => {
    client = new QuantsysV2Client({
      baseURL: 'http://localhost:5001',
      timeout: 10000,
    });
  });

  describe('parseCondition method', () => {
    // 通过反射访问私有方法进行单元测试
    const parseCondition = (client as any).parseCondition.bind(client);

    test('基本价格条件', () => {
      const result = parseCondition('price>100');
      expect(result).toEqual([{
        type: 'price_threshold',
        params: { operator: '>', value: 100 }
      }]);
    });

    test('涨跌幅条件', () => {
      const result = parseCondition('change_pct>5');
      expect(result).toEqual([{
        type: 'change_pct_threshold',
        params: { operator: '>', value: 5 }
      }]);
    });

    test('成交量条件', () => {
      const result = parseCondition('volume>1000000');
      expect(result).toEqual([{
        type: 'volume_threshold',
        params: { operator: '>', value: 1000000 }
      }]);
    });

    test('支持不同操作符', () => {
      expect(parseCondition('price>=100')).toEqual([{
        type: 'price_threshold',
        params: { operator: '>=', value: 100 }
      }]);

      expect(parseCondition('price<50')).toEqual([{
        type: 'price_threshold',
        params: { operator: '<', value: 50 }
      }]);

      expect(parseCondition('price<=200')).toEqual([{
        type: 'price_threshold',
        params: { operator: '<=', value: 200 }
      }]);

      expect(parseCondition('price=100')).toEqual([{
        type: 'price_threshold',
        params: { operator: '=', value: 100 }
      }]);
    });

    test('支持小数值', () => {
      const result = parseCondition('price>99.5');
      expect(result).toEqual([{
        type: 'price_threshold',
        params: { operator: '>', value: 99.5 }
      }]);
    });

    test('支持负数', () => {
      const result = parseCondition('change_pct>-5');
      expect(result).toEqual([{
        type: 'change_pct_threshold',
        params: { operator: '>', value: -5 }
      }]);
    });

    test('支持操作符周围的空格', () => {
      expect(parseCondition('price > 100')).toEqual([{
        type: 'price_threshold',
        params: { operator: '>', value: 100 }
      }]);

      expect(parseCondition('price>100')).toEqual([{
        type: 'price_threshold',
        params: { operator: '>', value: 100 }
      }]);

      expect(parseCondition('  price  >=  100  ')).toEqual([{
        type: 'price_threshold',
        params: { operator: '>=', value: 100 }
      }]);
    });

    test('无效格式应抛出友好错误', () => {
      expect(() => parseCondition('price')).toThrow('Invalid watch condition format');
      expect(() => parseCondition('price>')).toThrow('Invalid watch condition format');
      expect(() => parseCondition('>100')).toThrow('Invalid watch condition format');
      expect(() => parseCondition('price>abc')).toThrow('Invalid watch condition format');
    });

    test('不支持的字段应抛出明确错误', () => {
      expect(() => parseCondition('invalid_field>100')).toThrow('Unknown watch condition field');
      expect(() => parseCondition('invalid_field>100')).toThrow('Supported fields: price, change_pct, volume');
    });
  });

  describe('manageWatchRule integration', () => {
    test('创建规则时正确转换 condition 到 conditions', async () => {
      // 这个测试需要实际的后端，或者使用 mock
      // 这里只是演示测试结构
      
      // Mock axios post
      const mockPost = jest.spyOn((client as any).client, 'post');
      mockPost.mockResolvedValue({
        data: { success: true, rule_id: 123 }
      });

      try {
        await client.manageWatchRule({
          action: 'create',
          name: '茅台价格突破',
          symbol: '600519',
          condition: 'price>2000'
        });

        // 验证发送给后端的数据格式
        expect(mockPost).toHaveBeenCalledWith(
          '/api/watch/rules',
          expect.objectContaining({
            name: '茅台价格突破',
            symbol: '600519',
            conditions: [{
              type: 'price_threshold',
              params: { operator: '>', value: 2000 }
            }]
          })
        );

        // 验证没有 condition 字段（只有 conditions）
        const callArgs = mockPost.mock.calls[0][1];
        expect(callArgs).not.toHaveProperty('condition');
        expect(callArgs).toHaveProperty('conditions');
      } finally {
        mockPost.mockRestore();
      }
    });
  });
});
