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
    const getParseCondition = () => (client as any).parseCondition.bind(client);

    test('基本价格条件', () => {
      const result = getParseCondition()('price>100');
      expect(result).toEqual([{
        type: 'price_break',
        params: { direction: 'above', price: 100 }
      }]);
    });

    test('涨跌幅条件', () => {
      const result = getParseCondition()('change_pct>5');
      expect(result).toEqual([{
        type: 'pct_change',
        params: { direction: 'above', pct: 5 }
      }]);
    });

    test('成交量条件 - 暂不支持', () => {
      // volume 字段当前实现不支持
      expect(() => getParseCondition()('volume>1000000')).toThrow('Unknown watch condition field');
    });

    test('支持不同操作符', () => {
      expect(getParseCondition()('price>=100')).toEqual([{
        type: 'price_break',
        params: { direction: 'above', price: 100 }
      }]);

      expect(getParseCondition()('price<50')).toEqual([{
        type: 'price_break',
        params: { direction: 'below', price: 50 }
      }]);

      expect(getParseCondition()('price<=200')).toEqual([{
        type: 'price_break',
        params: { direction: 'below', price: 200 }
      }]);
    });

    test('支持小数值', () => {
      const result = getParseCondition()('price>99.5');
      expect(result).toEqual([{
        type: 'price_break',
        params: { direction: 'above', price: 99.5 }
      }]);
    });

    test('支持负数', () => {
      const result = getParseCondition()('change_pct>-5');
      expect(result).toEqual([{
        type: 'pct_change',
        params: { direction: 'above', pct: -5 }
      }]);
    });

    test('支持操作符周围的空格', () => {
      expect(getParseCondition()('price > 100')).toEqual([{
        type: 'price_break',
        params: { direction: 'above', price: 100 }
      }]);

      expect(getParseCondition()('price>100')).toEqual([{
        type: 'price_break',
        params: { direction: 'above', price: 100 }
      }]);

      expect(getParseCondition()('  price  >=  100  ')).toEqual([{
        type: 'price_break',
        params: { direction: 'above', price: 100 }
      }]);
    });

    test('无效格式应抛出友好错误', () => {
      expect(() => getParseCondition()('price')).toThrow('Invalid watch condition format');
      expect(() => getParseCondition()('price>')).toThrow('Invalid watch condition format');
      expect(() => getParseCondition()('>100')).toThrow('Invalid watch condition format');
      expect(() => getParseCondition()('price>abc')).toThrow('Invalid watch condition format');
    });

    test('不支持的字段应抛出明确错误', () => {
      expect(() => getParseCondition()('invalid_field>100')).toThrow('Unknown watch condition field');
    });
  });

  describe('manageWatchRule integration', () => {
    test.skip('创建规则时正确转换 condition 到 conditions', async () => {
      // 这个测试需要实际的后端，或者使用 vitest mock
      // 暂时跳过，待实现 vitest mock
    });
  });
});
