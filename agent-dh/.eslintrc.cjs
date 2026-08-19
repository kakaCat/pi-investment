module.exports = {
  root: true,
  env: { node: true, es2022: true },
  parser: '@typescript-eslint/parser',
  parserOptions: { ecmaVersion: 2022, sourceType: 'module' },
  plugins: ['@typescript-eslint'],
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended'],
  ignorePatterns: [
    'node_modules/',
    'dist/',
    'vendor/',
    'agent-dh.bak.*/',
    '**/*.test.ts',
    '**/*.spec.ts',
    '*.config.*',
  ],
  rules: {
    // 仓库大量插件使用 defineTool(... as any) 与动态响应解包，any 暂不阻断
    '@typescript-eslint/no-explicit-any': 'off',
    // 允许下划线前缀的刻意未使用参数（如 render: (_args, value) => ...）
    '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
  },
};
