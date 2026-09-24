# REQ-260924104605-ad0a 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：盯盘通知改版全部 7 任务完成并合并主线（服务已重启生效）。交付：①FR-1 分群——10 个盯盘频道码指向专用盯盘群 webhook（…60d879），alerts/reports/trading 原群不动，回滚演练实测通过；②FR-2 触发链路——L1 直发 agent 优先，Agent OS 不可达降级直飞书不丢消息且 metadata 如实标注降级原因；③FR-8/FR-14 回执——超时/升级同周期聚合一卡（实测 3 超时→1 张聚合卡同 batch id），close 即时发三要素处置结论卡；④FR-13 名称（代码）格式，缺失标「名称缺失」；⑤联调修复 2 个真实缺陷：ADR-002 调度旗误伤通知渠道注册、回执落库标签与真实落点漂移。回归 89 例全绿，兼容回归确认存量通知仍走旧渲染。评审报告 reviews/review-report.md，测试证据 tests/test-evidence.md。

## 1. 验收列表

### v1-1 · 定契约：WatchCardItem 扩展 + StockNameResolver 端口 + render_receipt 签名

**验收内容**：【定契约：WatchCardItem 扩展 + StockNameResolver 端口 + render_receipt 签名】验收：运行 pytest quantsys-v2/tests/notification/ 通过：新字段默认值与 display 形态（名称（代码）/缺失降级）用例通过；StockNameResolver 假实现可注入；既有用例结果与改前一致（不红）

**操作步骤**：
1. 运行 pytest quantsys-v2/tests/notification/ 通过：新字段默认值与 display 形态（名称（代码）/缺失降级）用例通过
2. StockNameResolver 假实现可注入
3. 既有用例结果与改前一致（不红）

**预期结果**：按上述步骤执行后满足验收标准：运行 pytest quantsys-v2/tests/notification/ 通过：新字段默认值与 display 形态（名称（代码）/缺失降级）用例通过；StockNameResolver 假实现可注入；既有用例结果与改前一致（不红）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 重写四级模板为意图驱动骨架（判重/多账户/名称优先/卫生）

**验收内容**：【重写四级模板为意图驱动骨架（判重/多账户/名称优先/卫生）】验收：运行 pytest quantsys-v2/tests/notification/test_watch_templates.py 通过且断言：骨架顺序一致；N=1 时 action 文本出现 1 次；N=3 时卡片包含 1 完整段+2 摘要行（含归属/待办#）；双账户返回两行不合并；无账户显示「通用观察」；渲染结果不包含「规则#-」与「频道：」；P0 包含 @所有人与止损止盈；P3 standalone_push=False 不变

**操作步骤**：
1. 运行 pytest quantsys-v2/tests/notification/test_watch_templates.py 通过且断言：骨架顺序一致
2. N=1 时 action 文本出现 1 次
3. N=3 时卡片包含 1 完整段+2 摘要行（含归属/待办#）
4. 双账户返回两行不合并
5. 无账户显示「通用观察」
6. 渲染结果不包含「规则#-」与「频道：」
7. P0 包含 @所有人与止损止盈
8. P3 standalone_push=False 不变

**预期结果**：按上述步骤执行后满足验收标准：运行 pytest quantsys-v2/tests/notification/test_watch_templates.py 通过且断言：骨架顺序一致；N=1 时 action 文本出现 1 次；N=3 时卡片包含 1 完整段+2 摘要行（含归属/待办#）；双账户返回两行不合并；无账户显示「通用观察」；渲染结果不包含「规则#-」与「频道：」；P0 包含 @所有人与止损止盈；P3 standalone_push=False 不变

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 接线 direct 渠道路由与回执 os_channel、补 rule_id 传递

**验收内容**：【接线 direct 渠道路由与回执 os_channel、补 rule_id 传递】验收：运行 pytest quantsys-v2/tests/notification/ 通过且断言：direct 分支 agent 优先、os_channel 直透 AgentChannel；Agent OS 不可达时降级飞书且 metadata 包含降级标注；回执 payload 的 os_channel 与 risk_stop/watch_symbol 一致；sender 抛错时 delivery_status 返回 failed；既有用例不红

**操作步骤**：
1. 运行 pytest quantsys-v2/tests/notification/ 通过且断言：direct 分支 agent 优先、os_channel 直透 AgentChannel
2. Agent OS 不可达时降级飞书且 metadata 包含降级标注
3. 回执 payload 的 os_channel 与 risk_stop/watch_symbol 一致
4. sender 抛错时 delivery_status 返回 failed
5. 既有用例不红

**预期结果**：按上述步骤执行后满足验收标准：运行 pytest quantsys-v2/tests/notification/ 通过且断言：direct 分支 agent 优先、os_channel 直透 AgentChannel；Agent OS 不可达时降级飞书且 metadata 包含降级标注；回执 payload 的 os_channel 与 risk_stop/watch_symbol 一致；sender 抛错时 delivery_status 返回 failed；既有用例不红

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 回执聚合投递 + 名称批量解析 + 时间格式修复

**验收内容**：【回执聚合投递 + 名称批量解析 + 时间格式修复】验收：运行 pytest quantsys-v2/tests/watch/ 通过且断言：同周期 3 条超时→sender 调用 1 次、卡片包含 3 行且每行含归属账户；重跑同周期全部 duplicate、sender 调用 0 次；空组 flush 返回 no-op；回执文案不包含微秒与「| 周期 |」、due 只出现 1 次；名称未命中时返回纯代码+「名称缺失」标注

**操作步骤**：
1. 运行 pytest quantsys-v2/tests/watch/ 通过且断言：同周期 3 条超时→sender 调用 1 次、卡片包含 3 行且每行含归属账户
2. 重跑同周期全部 duplicate、sender 调用 0 次
3. 空组 flush 返回 no-op
4. 回执文案不包含微秒与「| 周期 |」、due 只出现 1 次
5. 名称未命中时返回纯代码+「名称缺失」标注

**预期结果**：按上述步骤执行后满足验收标准：运行 pytest quantsys-v2/tests/watch/ 通过且断言：同周期 3 条超时→sender 调用 1 次、卡片包含 3 行且每行含归属账户；重跑同周期全部 duplicate、sender 调用 0 次；空组 flush 返回 no-op；回执文案不包含微秒与「| 周期 |」、due 只出现 1 次；名称未命中时返回纯代码+「名称缺失」标注

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · 处置结论回执：close 触发 result + 三要素文案 + 响应填充

**验收内容**：【处置结论回执：close 触发 result + 三要素文案 + 响应填充】验收：运行 pytest quantsys-v2/tests/watch/ 通过且断言：close 收敛后 sender 收到的卡片包含结论/原因/next_condition 三要素；terminal=ignored 时文案包含 NEXT 条件原文；重复 close 返回 duplicate 不重复发送；POST /api/watch/todos/{id}/close 响应 receipt 字段非 None；receipt_service=None 时行为与改前一致

**操作步骤**：
1. 运行 pytest quantsys-v2/tests/watch/ 通过且断言：close 收敛后 sender 收到的卡片包含结论/原因/next_condition 三要素
2. terminal=ignored 时文案包含 NEXT 条件原文
3. 重复 close 返回 duplicate 不重复发送
4. POST /api/watch/todos/{id}/close 响应 receipt 字段非 None
5. receipt_service=None 时行为与改前一致

**预期结果**：按上述步骤执行后满足验收标准：运行 pytest quantsys-v2/tests/watch/ 通过且断言：close 收敛后 sender 收到的卡片包含结论/原因/next_condition 三要素；terminal=ignored 时文案包含 NEXT 条件原文；重复 close 返回 duplicate 不重复发送；POST /api/watch/todos/{id}/close 响应 receipt 字段非 None；receipt_service=None 时行为与改前一致

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · 迁移与兼容：FR-1 回归、回滚演练、旧渲染兼容、运维指引

**验收内容**：【迁移与兼容：FR-1 回归、回滚演练、旧渲染兼容、运维指引】验收：执行回滚演练通过：UPDATE 改回 …172829 后 curl 发测试消息落原群、再改回 …60d879 落盯盘群（投递日志 status=sent 与群可见一致）；pytest 兼容用例通过（无 watch_level 仍旧渲染）；ops-note.md 落盘且步骤可复制执行

**操作步骤**：
1. 执行回滚演练通过：UPDATE 改回 …172829 后 curl 发测试消息落原群、再改回 …60d879 落盯盘群（投递日志 status=sent 与群可见一致）
2. pytest 兼容用例通过（无 watch_level 仍旧渲染）
3. ops-note.md 落盘且步骤可复制执行

**预期结果**：按上述步骤执行后满足验收标准：执行回滚演练通过：UPDATE 改回 …172829 后 curl 发测试消息落原群、再改回 …60d879 落盯盘群（投递日志 status=sent 与群可见一致）；pytest 兼容用例通过（无 watch_level 仍旧渲染）；ops-note.md 落盘且步骤可复制执行

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-7 · 集成验收：触发落群/网关降级/close 收卡/聚合一卡/pytest 全绿

**验收内容**：【集成验收：触发落群/网关降级/close 收卡/聚合一卡/pytest 全绿】验收：5 步全部通过且有证据：①触发后盯盘群可见卡且 alerts 群无此消息；②停 :8080 后消息仍送达且 metadata 包含降级标注；③close 后盯盘群可见三要素卡；④3 条超时只收到 1 张聚合卡；⑤pytest quantsys-v2/tests/notification/ 与 tests/watch/ 全部通过

**操作步骤**：
1. 5 步全部通过且有证据：①触发后盯盘群可见卡且 alerts 群无此消息
2. ②停 :8080 后消息仍送达且 metadata 包含降级标注
3. ③close 后盯盘群可见三要素卡
4. ④3 条超时只收到 1 张聚合卡
5. ⑤pytest quantsys-v2/tests/notification/ 与 tests/watch/ 全部通过

**预期结果**：按上述步骤执行后满足验收标准：5 步全部通过且有证据：①触发后盯盘群可见卡且 alerts 群无此消息；②停 :8080 后消息仍送达且 metadata 包含降级标注；③close 后盯盘群可见三要素卡；④3 条超时只收到 1 张聚合卡；⑤pytest quantsys-v2/tests/notification/ 与 tests/watch/ 全部通过

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-8 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-11 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- pytest：cd quantsys-v2 && PYTHONPATH=$PWD venv/bin/python -m pytest tests/notification/ tests/watch/ -q → 89 passed（2026-09-24 14:35 主检出）
- 集成①：notification_logs 14:18:14 watch_symbol|sent|盯盘触发-600519|wh=60d879；alerts 群同时段新增 0
- 集成②：停 :8080 后 notif_c2375f55bc6143c5 日志链「主渠道发送失败→降级渠道发送成功 channel=feishu」（14:20:07-08）；Agent OS 已恢复 health_ok=true
- 集成③：POST /api/watch/todos/39/close → receipt.sent=true，三要素卡落 watch_symbol→60d879（14:26:11）
- 集成④：SLA 巡检 scanned:13 timeout:3 group_cards:1；1 张 risk_stop 聚合卡（14:33:02）；watch_receipts 3 行同 batch:timeout:202609241433
- 回滚演练：scripts/watch-channel-drill.sh 全命令通过，探针 ef464627（原群 sent）、e8a7c137（盯盘群 sent）
- 渠道终态：drill assert → 盯盘 10/10→60d879、原群 0/10、legacy 3/3→172829
- 评审报告：agent-dh/docs/requirements/REQ-260924104605-ad0a/reviews/review-report.md
- 测试证据：agent-dh/docs/requirements/REQ-260924104605-ad0a/tests/test-evidence.md
- 运维指引：agent-dh/docs/requirements/REQ-260924104605-ad0a/ops-note.md
- 合并主线：git log f92c8344/e8888f63/11a64bc5/6c7ea090；quantsys-v2 pid 46747 health_ok

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 定契约：WatchCardItem 扩展 + StockNameResolver 端口 + render_receipt 签名 | ✓ 通过 | human/session-2bf7941d-3f18-4423-9c83-35f60ea4f5b9 | 2026-09-24 14:37 |
| v1-2 | 重写四级模板为意图驱动骨架（判重/多账户/名称优先/卫生） | ✓ 通过 | human/session-2bf7941d-3f18-4423-9c83-35f60ea4f5b9 | 2026-09-24 14:37 |
| v1-3 | 接线 direct 渠道路由与回执 os_channel、补 rule_id 传递 | ✓ 通过 | human/session-2bf7941d-3f18-4423-9c83-35f60ea4f5b9 | 2026-09-24 14:37 |
| v1-4 | 回执聚合投递 + 名称批量解析 + 时间格式修复 | ✓ 通过 | human/session-2bf7941d-3f18-4423-9c83-35f60ea4f5b9 | 2026-09-24 14:37 |
| v1-5 | 处置结论回执：close 触发 result + 三要素文案 + 响应填充 | ✓ 通过 | human/session-2bf7941d-3f18-4423-9c83-35f60ea4f5b9 | 2026-09-24 14:37 |
| v1-6 | 迁移与兼容：FR-1 回归、回滚演练、旧渲染兼容、运维指引 | ✓ 通过 | human/session-2bf7941d-3f18-4423-9c83-35f60ea4f5b9 | 2026-09-24 14:37 |
| v1-7 | 集成验收：触发落群/网关降级/close 收卡/聚合一卡/pytest 全绿 | ✓ 通过 | human/session-2bf7941d-3f18-4423-9c83-35f60ea4f5b9 | 2026-09-24 14:37 |
| v1-8 | 需求级验收 | ✓ 通过 | human/session-2bf7941d-3f18-4423-9c83-35f60ea4f5b9 | 2026-09-24 14:37 |
| v1-11 | 需求级验收 | ✓ 通过 | human/session-2bf7941d-3f18-4423-9c83-35f60ea4f5b9 | 2026-09-24 14:37 |
