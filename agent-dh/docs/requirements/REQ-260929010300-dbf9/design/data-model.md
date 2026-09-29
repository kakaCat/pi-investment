# 数据模型视角 · REQ-260929010300-dbf9 设计 `serves: FR-1, FR-2, FR-3, FR-4, FR-7`

> 本设计是**纯前端渲染层**改动：不改台账、不改队列文件、不改产物字段。

## 持久化数据：零变更 `serves: FR-3, FR-7`

不新增 / 不修改任何字段，不改 `queue.json` 的结构与语义，不 bump 任何版本号。
服务端与存储层零 diff——回滚只需回滚前端代码，不涉及数据修复。

## 运行时结构与不变量 `serves: FR-3, FR-4`

| 结构 | 形态 | 不变量 |
|---|---|---|
| 实例表 `disposers` | `Map<string, () => void>` | 每个 canvasId 至多一条；重复挂载先释放旧条目再写入新条目 |
| 画布 id | `string`（缺省 `'dag-canvas'`） | 同页两实例 id 必须不同；`document.getElementById(canvasId)` 命中唯一 |
| 面板容器 id | `string` | 只给面板根 div 打锚点（`dsh-pm-dag-panel` 的 id），不参与唯一性查询 |

## 入参结构类型（收敛，不伪造） `serves: FR-1, FR-2, FR-7`

绘制真正用到的字段 = `id / title / status / phase / side / dependsOn / parentId? / stageKind? / cardDoc?`；
`TaskRecord` 与 `StageTaskRef` 都是它的**超集**。设计把三个入口的入参类型收敛为这个结构类型（或加一层最小适配），
**面板侧不得为满足类型而补造 `TaskRecord` 的其余字段**（`requirementId / scope / acceptance / context / executions` 等一概不需要）。

`ready` 保持 `readonly string[] | undefined`，两态语义不得混同：`undefined` = 前端按依赖推导；
空数组 = 队列确实没有可开工卡。**2026-09-29 裁定 B 后统计条已删**——`ready` 只驱动画布上的可开工绿点，
不再有任何文字标注（FR-7 随之作废）。
