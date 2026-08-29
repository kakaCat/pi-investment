import type { ToolPrompt } from '@pi-investment/core-tool';

export interface QuantsysV2StatusParams {
  // 无参数
}

export interface QuantsysV2StatusResult {
  running: boolean;
  status: string;
  db_connected: boolean;
  holdings_count: number;
  recent_signals: number;
  model_loaded: boolean;
  recent_report: boolean;
  balance?: any;
  error?: string;
  timestamp: string;
}

export const quantsysV2StatusPrompt: ToolPrompt<QuantsysV2StatusParams, QuantsysV2StatusResult> = {
  description: '检查 quantsys-v2 后端服务状态：服务运行状态、数据库连接、持仓数量、信号数量、模型加载状态',
  useCases: [
    '重启前后验证服务是否正常运行',
    '故障诊断：定位服务挂死、数据库连接等问题',
    '日常巡检：确认后端服务健康状态',
    '部署验证：确认新版本启动成功',
  ],
  examples: [
    {
      title: '服务正常运行',
      params: {},
      expectedResult: '运行中 (status: running), 数据库已连接, 3 个持仓, 模型已加载',
    },
    {
      title: '服务未运行',
      params: {},
      expectedResult: '未运行 (status: stopped), 数据库未连接',
    },
  ],
  notes: [
    '💡 无参数，直接调用即可',
    '💡 检查服务状态、数据库、持仓、信号、模型',
    '⚠️ 服务异常时查看 error 字段',
  ],
  relatedTools: ['quantsys_v2_restart', 'quantsys_v2_logs'],
  parameters: {},
  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        running: { type: 'boolean', description: '服务是否运行' },
        status: { type: 'string', description: '服务状态：running / degraded / stopped' },
        db_connected: { type: 'boolean', description: '数据库是否连接' },
        holdings_count: { type: 'number', description: '持仓数量' },
        recent_signals: { type: 'number', description: '最近信号数量' },
        model_loaded: { type: 'boolean', description: '模型是否加载' },
        recent_report: { type: 'boolean', description: '是否有最近报告' },
        balance: { type: 'object', description: '账户余额信息' },
        error: { type: 'string', description: '错误信息' },
        timestamp: { type: 'string', description: '检查时间戳' },
      },
      additionalProperties: true,
    },
  },
};
