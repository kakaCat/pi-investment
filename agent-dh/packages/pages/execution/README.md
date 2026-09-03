# @pi-investment/dashboard-execution

P1 **双线执行确认看板**（页面插件 · 纯 webServer 路由，零工具）。

按 docs/design/dashboard-implementation-detail.md 实施：

- `GET /dashboard/execution` —— 自包含静态 HTML（内联 CSS/JS）
- `GET /dashboard/api/board` —— `{success:true,data:{health,checkpoints,tasks,errors,timeline,blockedFlows,degraded,v2Available,fetchedAt}}`

架构锁定：浏览器(:13080) → 同源 /dashboard/api/* → 本插件服务端聚合 → v2(:5001)/os(:8080) HTTP + 本机文件 tail（浏览器不直连内部端口）。

## 设计要点

- 页面插件范式：函数式模块（`name` + `apply`），经 `(ctx as any).inject?.(['webServer'], webCtx => webCtx.effect(...))` 惰性注入并注册 exact 路由（复用 lifecycle /wake 已验证模式）；disposer 由 effect 包裹，插件停用自动注销。
- 无 `@pi-investment/core-tool` / `@pi-investment/quantsys-v2-client` 依赖（理由见设计文档 §3）；依赖仅 `@deepseek-ai/cordis`。
- 数据信封修正：tasks/runs/themes 无 `data` 键、regime/platform 有 `data` 键、health/memory 均无 —— 统一 raw fetch + 调用点 pluck（详见 src/services/data-aggregation.ts 注释）。
- 检查点注册表 src/services/checkpoint-registry.ts 16 行与设计文档 §5.3 一致。

## 开发

```bash
cd agent-dh && pnpm install          # 使嵌套 workspace 生效
pnpm test                            # vitest（本插件无工具 schema，仅占位）
```

注册与重启见 ~/.dsh/profiles/investment/{cordis.patch.yml, package.json}（file: + 符号链接）。

## 验收

```bash
curl -s http://127.0.0.1:13080/dashboard/execution | head
curl -s http://127.0.0.1:13080/dashboard/api/board
```
