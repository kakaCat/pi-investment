# dsh-pmboard

**项目看板** — [DeepSeek Harness (DSH)](https://github.com/deepseek-ai/dsh) 的需求流水线页面插件。
把「用户在对话里提出一个想法」到「需求立项 → 评审 → 拆分 → 实施 → 验收 → 归档」的完整生命周期，
做成看板可视、工具可调、每步留痕的流水线。

## 这是什么

一个 DSH **双半插件**（host + client）：

- **host 半**（Node）：reqboard JSON + SSE API（`/dashboard/api/reqboard/*`）、
  JSON 台账（两级状态机）、立项捕获管线（捕获用户消息 → 注入立项引导 → 三问弹框立项）、
  以及 **13 个 pm 工具**（见下）供 Agent 调用。
- **client 半**（Web GUI）：侧栏入口 + 中心栏看板视图——需求泳道、任务时间线、
  逐项弹框验收单、归档区。

设计原则：**创建即立项**（无待归类中间态）、**人工闸门在关键节点**
（立项三问 / 计划批准 / 逐项验收 / 归档）、**一切决策留痕可复盘**。

## 安装

在 DSH profile 的 `cordis.patch.yml` 中注册（无必填配置项）：

```yaml
- insert:
    - id: pmboard
      name: 'dsh-pmboard'
```

并在 profile 的 `package.json` 中加入依赖：

```json
{
  "dependencies": {
    "dsh-pmboard": "^0.1.0"
  }
}
```

重启 profile 后，GUI 侧栏会出现「项目看板」入口，Agent 可使用 reqboard_* 系列工具。

## 提供的工具（13 个）

| 工具 | 作用 |
|---|---|
| `reqboard_capture` | 立项弹框：识别到新工作意图时弹出「需求名称/类型/难度」三问，作答即立项并绑定窗口 |
| `reqboard_create` | 手工立项路径（弹框不可用或三值已明确时） |
| `reqboard_status` | 查本窗口绑定状态、条款接收状态、可选动作 |
| `reqboard_move` | 推进需求状态（draft → brainstorming → … → accepting；取消/归档是人工闸门） |
| `reqboard_submit` | 提交阶段产物：需求文档 / 拆分计划 / 验收材料 / 归档材料 |
| `reqboard_ask_confirm` | 关键确认（原子化：确认 → 落章 → 推进） |
| `reqboard_decompose` | 把已批准的拆分计划落成任务卡 |
| `reqboard_accept_sheet` | 验收单逐项弹框验收，未过项自动返工 |
| `reqboard_task_move` | 推进任务状态（todo → in_progress → … → done） |
| `reqboard_task_execute` | 执行任务（DSH Workflow 六阶段） |
| `reqboard_task_status` | 查任务执行进度 |
| `reqboard_task_report` | 任务完成汇报，落任务卡文档 |

## 开发

```bash
pnpm install
pnpm build        # 服务端 dist + 客户端 lib（含 wrap 与产物校验门禁）
pnpm test         # vitest
pnpm typecheck    # tsc --noEmit
```

### 架构（四层，依赖只许向内）

```
src/
├── domain/        # 纯领域：状态机、门规、提示词片段（禁止 import 外层/node/框架）
├── application/   # 用例：立项/拆分/验收/闸门链
├── adapters/      # 端口实现：JSON 台账、文件文档库、会话探针
├── http/          # 路由薄层（组合根 + 错误→状态码唯一映射点）
├── tools/         # 13 个 Agent 工具定义
└── client/        # GUI 半：看板视图（自包含，无外部 UI 依赖）
```

层边界由 `tests/layer-boundary.test.ts` 静态扫描强制；宿主单文件 ≤400 行由尺寸门禁强制。

### Client 构建纪律

DSH shell 的 module-loader 种子表只含 react/react-dom/@deepseek-ai/*——
**client 代码引入的任何裸 npm 包都必须打进 bundle**（tsdown `noExternal`），
否则运行时 `require("xxx") missed the module table`，侧栏入口静默消失。
构建产物经 `scripts/verify-client-build.mjs` 校验（含 WRAP_SENTINEL 哨兵：
禁止对 bundle 做逐行字符串变换）。

## License

[MIT](./LICENSE)
