# @pi-investment/dashboard-genome · 自主进化看板

DSH GUI 双半插件，把 **Autonomy 线（自进化系统）能力设计层**从黑盒变白盒：
**"改了什么规则 / 什么在试运行、何时出结果 / 进化链路有无卡住"** 一页看清。

数据域 = 提示词基因组 `~/.dsh-agent-dh/genome/`（genome.json + candidates.json），
F1 哨兵（2026-09-06 状态一致性核验，与 `ValidationGateTool.runConsistencyCheck`
同源规则）即本页的日常可视化仪表——g16 类"观察版滞留/登记断链"漂移进门可见。

## 五区域单页

| # | 区域 | 内容 |
|---|------|------|
| ① | 概览头 | genome 版本(gN) / 4 段 / 谱系事件数 / 候选数(观察中·待裁决) / 一致性健康徽章🟢或⚠️ / 创建·更新·核验时间 |
| ② | 段状态矩阵 | 4 卡：宪法🔒锁定 / 决策原则 / 操作规则 / 经验教训 — 版本号 + 最近变更（gN·类型·时间·理由可展开） |
| ③ | 一致性诊断 | C1 孤儿候选 / C2 未登记版本 / C3 原子写残留(*.tmp)，异常红字明细 + 规则说明 |
| ④ | 候选生命周期 | 观察中(进度条+剩余天数) / 待裁决(已过观察期未 gate) / 已转正 / 已回滚·拒绝，按状态 tab 过滤 |
| ⑤ | 谱系时间线 | history 倒序：gN + 段 + 更新/转正/回滚徽章 + 时间 + git_commit + 理由展开 |

**重检按钮**：随时重读 genome.json / candidates.json 并重跑 C1/C2/C3（页面 30s 自动轮询）。

## 与 dashboard-execution 的关系（互补，非重复）

- **execution（执行确认看板）** 管 genome **文件健康**（文件存在/更新时间，执行视角的检查点）。
- **genome（本看板）** 管 genome **内容与生命周期**（改了什么段、谁在试运行、gate 有没有裁，能力设计视角）。
- 本页只读展示 + 前端重检；**治理动作（promote/rollback/register）仍走 gate 工具与 agent 处置**，页面不加写端点。

## 结构（execution 同构）

```
src/index.ts                 host 半：name + apply，惰性注入 webServer 注册
src/routes/genome-routes.ts  /dashboard/api/genome（200 {success,data} / 500 {success:false,error}）
src/services/genome-aggregation.ts  只读聚合 + C1/C2/C3 一致性核验（fs 直读 genomeDir）
src/types/index.ts           host↔client 共享类型（GenomeData 信封）
src/client/                  client 半：侧栏入口 + 中心栏视图（纯 DOM，零第三方）
  index.ts / sidebar-entry.ts / board-mount.ts / view.ts / styles.ts / dom.ts / types.ts
lib/client.js                构建产物（tsdown CJS + wrap-client.mjs 模块加载器封装，提交入库）
```

- client 半入口 = 顶部侧栏行「自主进化」（logoRow 之下，holdings 顶部 DOM 行范式；
  未占用 sidebar.footer.action 席位——execution 已占）。面板互斥走
  `dsh-panel-activate` 事件 + `html[data-dsh-gen-active]`（开板驱逐其余 attr，
  他人开板被动自关，不依赖旧面板静态互斥数组）。
- HMR 安全：`window.__dshGenomeClient.dispose` 防重复挂载。
- 构建：`pnpm --filter @pi-investment/dashboard-genome build:client`
  （tsdown CJS + wrap；react 已不引用，tsdown external 保留无害）。

## 注册（profile 三处，勿遗漏）

1. `cordis.patch.yml` plugins insert 加 `{id: dashboard-genome, name: '@pi-investment/dashboard-genome', config: {}}`
2. `package.json` dependencies 加 `"@pi-investment/dashboard-genome": "file:../../../pi-investment/agent-dh/packages/pages/genome"`
3. `node_modules/@pi-investment/` 软链 → `agent-dh/packages/pages/genome`
4. 重启 profile（先 `pnpm build:client`——MissingClientBundleError 启动即失败）

## 验证

- `curl http://127.0.0.1:13080/dashboard/api/genome` → `{success:true, data:{genomeVersion, sections, candidates, consistency, history, fetchedAt}}`
- GUI 侧栏点「自主进化」→ 五区渲染；g19 rules v8 观察中（9/10 到期转「待裁决」）
- 一致性健康时 🟢；人为制造漂移（如删除 candidates.json 登记）应出现 C2 红字

## 谱系

- 2026-09-06 w-a8a89c6a：F1（A 步 skill 哨兵 + B 步 gate 诊断腿）落地后，用户要求 Autonomy 线
  能力设计层可视化；设计确认（5 区域单页）后实现本包。
