# REQ-640a55 拆分清单（decomposition）

> 自动生成于 reqboard_decompose：计划任务表 ↔ 落库任务 id 对照

## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）

| 根编号 | 计划 key | 任务 id | 标题 | 状态 |
|--------|---------|--------|------|------|
| FR-3 | t1 | t-92e0b3 | 修复编号门禁的两处判据（跳号与重复） | todo |
| FR-4 | t1 | t-92e0b3 | 修复编号门禁的两处判据（跳号与重复） | todo |
| FR-2 | t2 | t-c8fb87 | 让拆分骨架直出任务卡三要素节 | todo |
| FR-1 | t3 | t-fb5e66 | 把三要素门禁接上执行链（出口与结单） | todo |
| FR-5 | t4 | t-11e56a | 冻结存量兼容与改卡通道双标题 | todo |
| FR-1 | t5 | t-ad7826 | 端到端回归与反向验证 | todo |
| FR-2 | t5 | t-ad7826 | 端到端回归与反向验证 | todo |
| FR-3 | t5 | t-ad7826 | 端到端回归与反向验证 | todo |
| FR-4 | t5 | t-ad7826 | 端到端回归与反向验证 | todo |
| FR-5 | t5 | t-ad7826 | 端到端回归与反向验证 | todo |

## §2 任务清单

| 计划 key | 任务 id | 标题 | 阶段 | 端侧 | 依赖 | 验收标准 |
|---------|--------|------|------|------|------|---------|
| t1 | t-92e0b3 | 修复编号门禁的两处判据（跳号与重复） | implement | backend | - | npx vitest run tests/clause-numbering.test.ts 全绿：FR-1+FR-3 返回 [FR-2]、两个 FR-1 定义返回「FR-1（出现2次）」、多前缀各自连续与不可解析 id 各返回 []。反向验证：把跳号正则改回 d+ 后该文件 2 条变红；把重复判定改喂去重后的清单后 1 条变红。 |
| t2 | t-c8fb87 | 让拆分骨架直出任务卡三要素节 | implement | backend | - | reqboard_decompose 后读 docs/requirements/<REQ>/tasks/<id>.md：## 在做什么 / ## 解决什么问题 / ## 得到什么结果 三节均在且正文非空；卡文件缺失时 reqboard_task_report 自造的骨架头同样含三节。npx vitest run tests/handoff.test.ts tests/decompose-tools.test.ts 全绿。 |
| t3 | t-fb5e66 | 把三要素门禁接上执行链（出口与结单） | implement | backend | t-c8fb87 | 构造缺三要素节的卡：reqboard_move 从 decomposing 进 implementing 被拒、code=task_card_incomplete 且消息列出卡 id 与节名；reqboard_task_move(to=done) 同样被拒；三节齐备时两条路径均放行；卡文件不存在 / to=testing / 任务不属本窗口绑定 三种情况均不判。新增集成用例全绿。 |
| t4 | t-11e56a | 冻结存量兼容与改卡通道双标题 | implement | backend | t-fb5e66 | tests/amend-acceptance.test.ts 新增两例：卡含 ## 得到什么结果 与卡含 ## 验收标准 各一，改卡后该节正文均被整段替换；存量实测：台账 10 条非终态需求 / 19 张在途卡在新门禁下零拒绝（留痕实测输出与数据时点）；npx vitest run 全绿。 |
| t5 | t-ad7826 | 端到端回归与反向验证 | test | backend | t-fb5e66, t-11e56a | cd packages/pages/dsh-pmboard && npx vitest run 全绿（基线 97 文件 / 1250 测试 + 新增）；三处反向验证各自变红（骨架改回 ## 目标 → 出口拦截命中；重复判定喂去重清单 → 重复用例红；跳号正则改回 d+ → 跳号用例红）；npx tsc --noEmit 无错误。 |
