# @pi-investment/dashboard-execution

P1 **双线执行确认看板** —— DSH GUI **双半插件**（标准实现方式，参照 dsh-taskboard：
host 半 + GUI-native client 半由 dsh web shell 挂载，非独立 HTML 页面）。

## 双半架构

```
┌─ @pi-investment/dashboard-execution（一个包，两个半）─────────────────┐
│  host 半（服务端）    src/index.ts + services/ + routes/              │
│    • 惰性注入 webServer，注册 GET /dashboard/api/board（唯一路由）     │
│    • 聚合：v2(:5001)/os(:8080) HTTP 健康 + scheduler tasks/runs +     │
│      genome + 本机日志 tail → BoardData JSON（同源、免认证）            │
│  client 半（浏览器 GUI）src/client/ → tsdown → lib/client.js          │
│    • package.json 声明 dsh.client{platform:web,inject:[]} +           │
│      exports["./client"] → dsh web shell 组合 boot graph entry         │
│      （id = 包名 @pi-investment/dashboard-execution，combo URL 提供）   │
│    • 运行后：侧栏插入「执行看板」入口 + 中心栏挂载看板视图              │
│      （fetch 同源 /dashboard/api/board；无需注入 connection 等服务）    │
│    • 激活语义复用 dsh-panel-activate 事件 + html[data-dsh-exec-active] │
│      与其它面板互斥；MutationObserver 自愈入口                          │
└───────────────────────────────────────────────────────────────────────┘
```

board JSON 载荷：{success:true, data:{health, checkpoints, tasks, errors, timeline, blockedFlows, degraded, v2Available, fetchedAt}}。
浏览器(:13080) → 同源 /dashboard/api/board → host 聚合 → v2/os + 本机文件（浏览器不直连内部端口）。

## 设计要点

- **双半契约**（dsh-taskboard 0.6.4 对照验证）：包级 dsh.client 声明（host 侧 boot graph 依赖，
  inject 取声明值）+ exports["./client"] 字符串；client bundle 必须存在于声明时
  （MissingClientBundleError 启动即失败）→ 顺序：先 build:client 再重启。
- client 入口契约：export const name/inject/apply；apply(ctx) 永不 throw，用 ctx.effect?.(disposer, label)
  注册清理；bundle wrapper id = 包名（scripts/wrap-client.mjs 生成 window.__ModuleLoader__.load）。
- host 半范式：函数式模块（name + apply），经 (ctx as any).inject?.([webServer], webCtx => webCtx.effect(...))
  惰性注入并注册 exact 路由（disposer 自动注销，模式同 lifecycle /wake 已线上验证）。
- 无 core-tool / quantsys-v2-client 依赖（理由见设计文档 §3）；host 依赖仅 @deepseek-ai/cordis；
  client 半纯 DOM/fetch 零第三方依赖。
- 数据信封修正：tasks/runs/themes 无 data 键、regime/platform 有 data 键、health/memory 均无 ——
  统一 raw fetch + 调用点 pluck（详见 src/services/data-aggregation.ts 注释）。
- 检查点注册表 src/services/checkpoint-registry.ts 16 行与设计文档 §5.3 一致。

## 开发

```bash
cd packages/pages/execution
node ../../../node_modules/tsdown/dist/run.mjs -c tsdown.client.config.ts && node scripts/wrap-client.mjs
# 或 pnpm --filter @pi-investment/dashboard-execution build:client
```

client 改后必须重跑 build:client 再重启 :13080（dsh web 启动时按 clientPath mtime/内容重读 bundle）。

## 验收

```bash
curl -s http://127.0.0.1:13080/dashboard/api/board          # board JSON（同源供 client fetch）
# GUI：dsh web shell 侧栏出现「执行看板」入口，点击在中心栏渲染看板视图
#（不再是 /dashboard/execution HTML 页面 —— 用户纠正：HTML 页面非标准，标准是双半插件挂载）
```
