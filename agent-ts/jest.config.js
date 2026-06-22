/** @type {import('jest').Config} */
export default {
  preset: 'ts-jest/presets/default-esm',
  testEnvironment: 'node',
  roots: ['<rootDir>/src'],
  testMatch: ['**/__tests__/**/*.test.ts', '**/*.test.ts'],

  // ESM 支持
  extensionsToTreatAsEsm: ['.ts'],

  // 模块名称映射 - 移除 .js 扩展名
  moduleNameMapper: {
    '^(\\.{1,2}/.*)\\.js$': '$1',
  },

  // Transform 配置
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      useESM: true,
      tsconfig: {
        allowSyntheticDefaultImports: true,
        esModuleInterop: true,
        moduleResolution: 'node',
      }
    }],
  },

  // 忽略的文件
  testPathIgnorePatterns: [
    '/node_modules/',
    '/dist/',
    '\\.d\\.ts$'
  ],

  // 收集覆盖率
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
    '!src/**/*.test.ts',
    '!src/**/__tests__/**',
  ],

  // 超时设置
  testTimeout: 30000,

  // 详细输出
  verbose: true,
};
