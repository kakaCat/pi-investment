# t-cdb919 摘除外部三处记忆消费方·复核

> 需求：REQ-261004202231-bb99 quantsys-v2 记忆子系统下线：清引用后删除端点/领域/仓储/测试

## 在做什么
摘除外部三处记忆消费方·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对照 `docs/requirements/<REQ>/design/` 逐条核对；`npx vitest run <相关测试文件>` → 全绿；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-10-05T02:09:02.521Z，窗口 session-ebe42d9f-2797-48c7-b069-3d24d1da6184）

复核完成：这一轮不是「看起来没变」，而是逐条对照需求与实测证据核对——15 个端点全 404、残留符号 0、启动日志无记忆注册、测试总数差可解释、分层违规只降不升、数据先备份后删除，六条需求全部有据。

### 完成项

- 端点面：15 个 /api/memory* 全量 curl 全 404；非记忆端点 200 且形状不变
- 代码面：记忆符号 grep 0 命中；启动日志无 memory 注册、无导入失败告警
- 测试面：收集数 6565 → 6488（−77 可解释）；分层纯净性 322 → 319 且 memory 相关 0；漂移门禁 6 passed
- 数据面：dump 5,693 字节在手；两库 DROP 后查询均报 relation does not exist
- 跨仓面：agent-dh 产物无 memory_recall_audit、其余 4 工具在；agent-ts 无 v2 记忆残留且 5 个测试套件全绿
- 反向核对：共发现并登记 3 处遗留（子卡台账门禁、agent-os schema 漂移、.env 不再跟踪），未做静默降级

### 改动文件

- `quantsys-v2/docs/requirements/REQ-261004202231-bb99/reviews/self-review.md`
- `quantsys-v2/docs/requirements/REQ-261004202231-bb99/tests/verification-evidence.md`
- `quantsys-v2/docs/requirements/REQ-261004202231-bb99/design/test-cases.md`
- `quantsys-v2/docs/requirements/REQ-261004202231-bb99/design/interfaces.md`
- `quantsys-v2/docs/requirements/REQ-261004202231-bb99/design/data-model.md`

### 下一步

交付材料齐备后提交验收；台账遗留由人工裁决。

---
