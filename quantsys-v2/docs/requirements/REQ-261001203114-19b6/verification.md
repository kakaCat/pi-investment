# REQ-261001203114-19b6 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：交付结论：agent 因模型流报错（如 tool input is invalid JSON）或崩溃中断而停下时，用户会收到「会话异常中断（错误码）」；且 error/interrupted/未知终态再也不会被说成「会话已完成」。落地内容：turn/end 改为终态决策表（decideTurnEnd 纯函数，只有 completed 是完成）、新增出站取值 turn/error 与 reason/error 字段（version 仍 1，非中断报文逐字节不变）、新增 notifyInterrupt 开关与 interruptMessage 文案、skipReasons 收紧为静默名单且默认 ['aborted']、targets.json 不升版本仅追加可选字段 eventsMode（老目标开箱即收、主动取消勾选关得掉、回滚不丢目标）。自检：全量 288/288 零失败；FR-1…FR-6 逐条有真实命令与输出；7 条不变量成立；36 张任务卡 100% 有覆盖证据（verification-report §6）；评审发现的两处问题（goal/* 通配回归、turn-aborted 不可达）均已修复并同步文档。旁证：改动期间另有窗口在同一仓库并发实施 REQ-261001202058-0fbe（基线 244→266 即来自其 jobs-gate 用例），本次未触碰其 src/jobs.js 与相关用例。

## 1. 验收列表

### v1-1 · 分类契约：turn/end 终态决策表（纯函数）

**验收内容**：【分类契约：turn/end 终态决策表（纯函数）】验收

**操作步骤**：
1. 跑 node --test test/classify.test.js 退出码 0
2. 跑 node -e "import('./src/classify.js').then(async m=>{const {normalizeConfig}=await import('./src/config.js')
3. const c=new m.Classifier(normalizeConfig({}))
4. const s={header:{}}
5. for(const k of ['completed','error','interrupted','aborted','blocked','max-tokens','forked','weird'])console.log(k,'=>',JSON.stringify(c.classify(s,{type:'turn/end',data:{reason:{kind:k,error:k==='error'?{message:'a\nb',code:'MALFORMED_RESPONSE'}:undefined}}}))) })" 期望：completed→complete/turn/end
6. error/interrupted/weird→interrupt/turn/error
7. aborted/blocked/max-tokens/forked→null
8. error 的 error.message 为单行 'a b'。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：node --test --test-timeout=30000 "test/*.test.js" → tests 288 / pass 288 / fail 0 / duration 3.0s（基线 244，本需求新增+扩展 22 例）

**验收状态**：✓ 通过

---

### v1-2 · 数据契约：目标事件语义 eventsMode 与事件清单

**验收内容**：【数据契约：目标事件语义 eventsMode 与事件清单】验收

**操作步骤**：
1. 跑 node -e "import('./src/targets.js').then(m=>{console.log(m.EVENT_TYPES.includes('turn/error'),JSON.stringify(m.normalizeEvents(['turn/end','ask_user_question','approval/asked','goal/*'],undefined)),JSON.stringify(m.normalizeEvents([],'explicit')),JSON.stringify(m.normalizeEvents(['turn/end'],undefined))) })" 期望输出：true {"events":[],"eventsMode":"all"} {"events":[],"eventsMode":"explicit"} {"events":["turn/end"],"eventsMode":"explicit"}
2. 并跑 node --test test/targets.test.js test/config.test.js 退出码 0。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：node --test --test-timeout=30000 "test/*.test.js" → tests 288 / pass 288 / fail 0 / duration 3.0s（基线 244，本需求新增+扩展 22 例）

**验收状态**：✓ 通过

---

### v1-3 · 接线：开关、类型过滤与静默留痕

**验收内容**：【接线：开关、类型过滤与静默留痕】验收

**操作步骤**：
1. 跑 node -e "import('./src/config.js').then(m=>{const c=m.Config({})
2. console.log(c.notifyInterrupt.get(),m.VOLATILE_KEYS.includes('notifyInterrupt'),JSON.stringify(c.skipReasons.get()),c.interruptMessage.get())})" 期望：true true ["aborted"] 会话异常中断
3. 跑 node -e "import('./src/router.js').then(m=>{const R=new m.Router({notifyInterrupt:false,notifyComplete:true,notifyApproval:true,notifyQuestion:true})
4. console.log(m.targetAccepts({events:[],eventsMode:'explicit'},'turn/error'),m.targetAccepts({events:[],eventsMode:'all'},'turn/error'),m.targetAccepts({events:[]},'turn/error'),R.isTypeDisabled({kind:'interrupt'}))})" 期望：false true true true
5. 跑 node --test test/config.test.js test/router.filter.test.js test/router.test.js 退出码 0。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：node --test --test-timeout=30000 "test/*.test.js" → tests 288 / pass 288 / fail 0 / duration 3.0s（基线 244，本需求新增+扩展 22 例）

**验收状态**：✓ 通过

---

### v1-4 · 出站报文：中断意图的 reason / error 与事件元数据

**验收内容**：【出站报文：中断意图的 reason / error 与事件元数据】验收

**操作步骤**：
1. 跑 node -e "import('./src/channels/custom.js').then(m=>{const b=m.buildPayload({intent:{kind:'interrupt',event:'turn/error',message:'x',reason:'error',error:{code:'MALFORMED_RESPONSE',message:'m'}},session:{},title:null,now:0,contextText:null})
2. const c=m.buildPayload({intent:{kind:'complete',event:'turn/end',message:'y'},session:{},title:null,now:0,contextText:null})
3. console.log(JSON.stringify(b.reason),JSON.stringify(b.error),Object.keys(c).includes('reason'),c.version)})" 期望："error" {"code":"MALFORMED_RESPONSE","message":"m"} false 1
4. 跑 node --test test/payload.test.js test/channels.meta.test.js 退出码 0。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：node --test --test-timeout=30000 "test/*.test.js" → tests 288 / pass 288 / fail 0 / duration 3.0s（基线 244，本需求新增+扩展 22 例）

**验收状态**：✓ 通过

---

### v1-5 · 前端：设置页「关心事件」与保存语义

**验收内容**：【前端：设置页「关心事件」与保存语义】验收

**操作步骤**：
1. 跑 node --test test/client-render.test.js test/client-service.test.js test/client-hooks.test.js 退出码 0
2. 跑 grep -c "turn/error" client.js 期望 ≥2
3. 断言 EVENT_IDS.length===5，且全勾时提交载荷为 {events:[],eventsMode:'all'}、取消勾选「会话中断」后为 {events:[4 项],eventsMode:'explicit'}。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：node --test --test-timeout=30000 "test/*.test.js" → tests 288 / pass 288 / fail 0 / duration 3.0s（基线 244，本需求新增+扩展 22 例）

**验收状态**：✓ 通过

---

### v1-6 · 迁移与兼容（单列）：老记录归一化 + 版本不变 + 回滚可读

**验收内容**：【迁移与兼容（单列）：老记录归一化 + 版本不变 + 回滚可读】验收

**操作步骤**：
1. 跑 node --test test/targets-events.test.js 退出码 0（T6-1…T6-12 全绿）
2. 跑 node -e "import('./src/targets.js').then(m=>{console.log(JSON.stringify(m.normalizeEvents(undefined,'explicit')),m.TARGET_FILE_VERSION)})" 期望：{"events":[],"eventsMode":"explicit"} 3
3. 并断言新写入文件每条记录含 eventsMode、version===3、既有字段一字未改。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：node --test --test-timeout=30000 "test/*.test.js" → tests 288 / pass 288 / fail 0 / duration 3.0s（基线 244，本需求新增+扩展 22 例）

**验收状态**：✓ 通过

---

### v1-7 · 测试：决策表 / 链路集成 / 迁移三套用例

**验收内容**：【测试：决策表 / 链路集成 / 迁移三套用例】验收

**操作步骤**：
1. 跑 node --test "test/*.test.js" 期望 fail 0 且 tests ≥ 244+新增（只增不减）
2. 跑 node --test test/interrupt.test.js test/targets-events.test.js 退出码 0。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：node --test --test-timeout=30000 "test/*.test.js" → tests 288 / pass 288 / fail 0 / duration 3.0s（基线 244，本需求新增+扩展 22 例）

**验收状态**：✓ 通过

---

### v1-8 · 文档同步：报文契约、事件分类表、排障原因码

**验收内容**：【文档同步：报文契约、事件分类表、排障原因码】验收

**操作步骤**：
1. 跑 grep -n "turn/error" README.md docs/architecture/notification-plugin.md 期望三份文档各至少 1 处命中
2. 跑 grep -n "turn-not-notifiable" docs/guides/operations.md README.md 期望原因码已登记。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：node --test --test-timeout=30000 "test/*.test.js" → tests 288 / pass 288 / fail 0 / duration 3.0s（基线 244，本需求新增+扩展 22 例）

**验收状态**：✓ 通过

---

### v1-9 · 需求级自检：逐条 FR 对照可跑命令并汇总证据

**验收内容**：【需求级自检：逐条 FR 对照可跑命令并汇总证据】验收

**操作步骤**：
1. 跑 node --test "test/*.test.js" 期望 fail 0 且 tests ≥ 244
2. 跑 test -f docs/requirements/REQ-261001203114-19b6/tests/verification-report.md && echo ok 期望输出 ok
3. 报告须覆盖 FR-1…FR-6，每条带真实命令与实际输出摘要。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：node --test --test-timeout=30000 "test/*.test.js" → tests 288 / pass 288 / fail 0 / duration 3.0s（基线 244，本需求新增+扩展 22 例）

**验收状态**：✓ 通过

---

### v1-10 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：node --test --test-timeout=30000 "test/*.test.js" → tests 288 / pass 288 / fail 0 / duration 3.0s（基线 244，本需求新增+扩展 22 例）

**验收状态**：✓ 通过

---

### v1-11 · 需求级验收 · E2E 覆盖

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）；若确认无需 E2E，通过时必须在意见中写明理由。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）
2. 若确认无需 E2E，通过时必须在意见中写明理由。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：（待填写）

**验收状态**：⬜ 待验收

---

## 2. 测试报告

- node --test --test-timeout=30000 "test/*.test.js" → tests 288 / pass 288 / fail 0 / duration 3.0s（基线 244，本需求新增+扩展 22 例）
- 决策表探针（node -e 逐 kind 调 Classifier.classify）：completed→complete/turn/end；error/interrupted/weird→interrupt/turn/error；aborted/blocked/max-tokens/forked→null
- 静默码探针（silentReasonOf）：aborted→turn-aborted；blocked/max-tokens/forked→turn-not-notifiable；completed→null
- 配置探针：notifyInterrupt=true（volatile=true）、skipReasons=["aborted"]、interruptMessage=会话异常中断
- 路由探针：targetAccepts explicit 空=false、all=true、缺省=true、goal/* 通配=true；notifyInterrupt=false 时 isTypeDisabled(interrupt)=true
- 报文探针（buildPayload）：中断报文含 reason="error" 与 error={code,message}、version=1；完成报文不含 reason/error
- 迁移探针（normalizeEvents）：旧版全集无 mode→{"events":[],"eventsMode":"all"}；explicit 四项→原样保持；explicit 空→{"events":[],"eventsMode":"explicit"}；TARGET_FILE_VERSION=3
- 文档锚点：grep turn/error → README 5 处、docs/architecture/notification-plugin.md 6 处；grep turn-not-notifiable → docs/guides/operations.md 命中
- 报告路径：docs/requirements/REQ-261001203114-19b6/tests/verification-report.md（FR-1…FR-6 逐条命令+输出+结论、7 条不变量、5 处偏差记账、§6 任务卡 covers 对照表 36/36）
- 报告路径：docs/requirements/REQ-261001203114-19b6/tests/compat-report.md（老记录开箱即收 / 老客户端推断 / 用户取消勾选关得掉 / 旧版本读新文件不丢目标）
- 报告路径：docs/requirements/REQ-261001203114-19b6/reviews/implementation-review.md（实施评审：发现并修复 goal/* 通配回归、判定顺序瑕疵，残留风险 R1…R3 记账）
- 测试文件路径：test/interrupt.test.js（7 例）、test/targets-events.test.js（10 例）、test/classify.test.js 扩展（7 例），均在仓库内可跑

## 3. 文档完整性检查

✗ 缺失：requirement.md（需求文档）
✗ 缺失：design/architecture.md（架构）
✗ 缺失：design/data-model.md（数据模型）
✗ 缺失：design/interfaces.md（接口）
✗ 缺失：design/test-cases.md（测试用例）
✗ 缺失：decomposition.md（拆分计划）
✗ 缺失：reviews/（评审报告，非空）
✗ 缺失：tests/（测试证据，非空）
✗ 缺失：tasks/t-5e2101.md（任务卡）
✗ 缺失：tasks/t-a36090.md（任务卡）
✗ 缺失：tasks/t-413c55.md（任务卡）
✗ 缺失：tasks/t-5cbf4c.md（任务卡）
✗ 缺失：tasks/t-ca1e16.md（任务卡）
✗ 缺失：tasks/t-ef4fa8.md（任务卡）
✗ 缺失：tasks/t-cdd782.md（任务卡）
✗ 缺失：tasks/t-691d67.md（任务卡）
✗ 缺失：tasks/t-ce4b1a.md（任务卡）
✗ 缺失：tasks/t-0a89bd.md（任务卡）
✗ 缺失：tasks/t-96b6a2.md（任务卡）
✗ 缺失：tasks/t-5249d2.md（任务卡）
✗ 缺失：tasks/t-f5f9e9.md（任务卡）
✗ 缺失：tasks/t-4039c3.md（任务卡）
✗ 缺失：tasks/t-90073b.md（任务卡）
✗ 缺失：tasks/t-a6684d.md（任务卡）
✗ 缺失：tasks/t-9bd584.md（任务卡）
✗ 缺失：tasks/t-5a02c2.md（任务卡）
✗ 缺失：tasks/t-946335.md（任务卡）
✗ 缺失：tasks/t-626838.md（任务卡）
✗ 缺失：tasks/t-e0032e.md（任务卡）
✗ 缺失：tasks/t-539bd4.md（任务卡）
✗ 缺失：tasks/t-5d66e3.md（任务卡）
✗ 缺失：tasks/t-3b3e5b.md（任务卡）
✗ 缺失：tasks/t-5a0f0d.md（任务卡）
✗ 缺失：tasks/t-774e6d.md（任务卡）
✗ 缺失：tasks/t-126c83.md（任务卡）
✗ 缺失：tasks/t-13691e.md（任务卡）
✗ 缺失：tasks/t-4a8281.md（任务卡）
✗ 缺失：tasks/t-624074.md（任务卡）
✗ 缺失：tasks/t-014928.md（任务卡）
✗ 缺失：tasks/t-3f1491.md（任务卡）
✗ 缺失：tasks/t-79265a.md（任务卡）
✗ 缺失：tasks/t-577377.md（任务卡）
✗ 缺失：tasks/t-2c64b0.md（任务卡）
✗ 缺失：tasks/t-d3aa47.md（任务卡）

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 分类契约：turn/end 终态决策表（纯函数） | ✓ 通过 | human/session-7b01a16b-35da-4360-9fc7-cc419417ae5e | 2026-10-01 21:02 |
| v1-2 | 数据契约：目标事件语义 eventsMode 与事件清单 | ✓ 通过 | human/session-7b01a16b-35da-4360-9fc7-cc419417ae5e | 2026-10-01 21:02 |
| v1-3 | 接线：开关、类型过滤与静默留痕 | ✓ 通过 | human/session-7b01a16b-35da-4360-9fc7-cc419417ae5e | 2026-10-01 21:02 |
| v1-4 | 出站报文：中断意图的 reason / error 与事件元数据 | ✓ 通过 | human/session-7b01a16b-35da-4360-9fc7-cc419417ae5e | 2026-10-01 21:02 |
| v1-5 | 前端：设置页「关心事件」与保存语义 | ✓ 通过 | human/session-7b01a16b-35da-4360-9fc7-cc419417ae5e | 2026-10-01 21:02 |
| v1-6 | 迁移与兼容（单列）：老记录归一化 + 版本不变 + 回滚可读 | ✓ 通过 | human/session-7b01a16b-35da-4360-9fc7-cc419417ae5e | 2026-10-01 21:09 |
| v1-7 | 测试：决策表 / 链路集成 / 迁移三套用例 | ✓ 通过 | human/session-7b01a16b-35da-4360-9fc7-cc419417ae5e | 2026-10-01 21:09 |
| v1-8 | 文档同步：报文契约、事件分类表、排障原因码 | ✓ 通过 | human/session-7b01a16b-35da-4360-9fc7-cc419417ae5e | 2026-10-01 21:09 |
| v1-9 | 需求级自检：逐条 FR 对照可跑命令并汇总证据 | ✓ 通过 | human/session-7b01a16b-35da-4360-9fc7-cc419417ae5e | 2026-10-01 21:09 |
| v1-10 | 需求级验收 | ✓ 通过 | human/session-7b01a16b-35da-4360-9fc7-cc419417ae5e | 2026-10-01 21:09 |
| v1-11 | 需求级验收 · E2E 覆盖 | ⬜ 待验收 |  |  |
