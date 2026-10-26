# 数据模型 · REQ-261019224003-0041

> serves: FR-5, FR-6, FR-7

## 1. pm 卡面新增字段（serves: FR-7）

| 字段 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `blockedReason` | `string` | 否 | `''`（缺失即空） | 承载 workprocess 的 blocked/paused 卡因；显示面随卡渲染 |
| `closePolicy` | `'auto' \| 'manual'` | 否 | `'auto'`（缺失即 auto） | 承载 workprocess `close` 语义；收口行为按此分流 |

- 兼容：存量台账 JSON 无此二字段 ⇒ 读取侧一律按默认解释；不跑回填脚本。
- 回滚：字段停用（读取侧忽略）+ git revert；字段是纯增量，无破坏性。
- 约束：`closePolicy` 非法值 ⇒ 装配/写入期抛 `REQBOARD_INVALID_INPUT`（与本仓"非法值抛错不回落缺省"口径一致）。

## 2. workprocess 存储域（serves: FR-5, FR-6）

- 文件：`~/.dsh/storages/workprocess.json`（已存在，desktop profile 实况见 01-facts §4.1）；**已有数据不迁移**。
- 归属域键：`scope = 需求 id`（一格一需求，03 §二 #1）。
- 新增/沿用的账（真源 = workprocess 侧）：
  - `rounds.tasks[id] = { rounds, grants }`：逐任务回合账 + 人追加预算份数（resume 一个 blocked 任务 +1 份）；
  - `asked.plan` / `asked.ask`：耐久去重记号（"规划轮/收口确认只问一次"）；
  - `WorkProcess.closedAt`：执行段收口记号；**需求归档仍走 pm 人工门**，closedAt 不等于归档。
- 一致性：投影每拍重建；投影与 pm 台账不一致 ⇒ 对账告警（绝不静默，03 §一理由 4）。

## 3. 不映射清单（防误建字段，serves: FR-5）

| pm 侧 | 不映射到 workprocess 的原因 |
|---|---|
| 需求阶段（`draft…archived`） | workprocess 无需求级阶段（裁定 #5） |
| 子卡依赖 DAG | workprocess 是线性串行；执行顺序由 pm ready 集合定（裁定 #2） |
| pm 三张卡片转移表/子卡角色不变量 | pm 项目面独有，真源留 pm（03 §一理由 2） |

## 4. 版本兼容（serves: FR-7）

- 台账读写双向兼容：旧 pm 读新台账（多两个字段）忽略之；新 pm 读旧台账按默认。
- workprocess 四包版本：收编后以本仓 workspace 版本为唯一事实源；WP 仓不再参与本仓构建。
