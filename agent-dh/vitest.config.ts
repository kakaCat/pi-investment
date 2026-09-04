import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

// quantsys-v2-client 位于仓库顶层（agent-dh 的上一级），经 file: 依赖引用。
// alias 用 __dirname 相对解析，保证 main 工作区与 git worktree（路径不同）都指向
// 各自真实的 quantsys-v2-client 源码，避免绝对路径硬编码导致的漂移。
const qv2ClientSrc = fileURLToPath(new URL('../quantsys-v2-client/src', import.meta.url));

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['tests/**/*.test.ts', 'packages/**/tests/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['packages/*/src/**/*.ts'],
      exclude: ['**/*.test.ts', '**/node_modules/**'],
    },
  },
  resolve: {
    alias: {
      '@pi-investment/quantsys-v2-client': qv2ClientSrc,
    },
  },
});
