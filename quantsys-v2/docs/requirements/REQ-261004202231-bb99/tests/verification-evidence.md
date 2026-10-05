---
req_id: REQ-261004202231-bb99
title: 验证证据（命令与实测输出摘要）
doc: tests/evidence
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
---

# 验证证据（2026-10-05 实测）

## v2 侧

```
# 端点（15 个全量）：全 404；非记忆端点仍 200
memory 抽样: 404 404 404 404 | 非记忆: 200 200
# 残留符号
grep -rn 'MemoryService|MemoryRepository|domain.memory|IMemoryRepository' domain/ application/ adapters/ infrastructure/ tests/ → 0
# 启动日志
Registered: memory → 0 次；Failed to import memory → 0 次
# 测试
collect-only → 6488 tests collected（基线 6565）
test_layer_purity → 319 条违规（基线 322），其中 memory 相关 0 条
test_orm_db_drift → 6 passed
# 数据
select count(*) from quant.memory_entries → relation does not exist（两库）
ls -l /tmp/memory_entries_pre_drop.sql → 5,693 字节
```

## agent-dh 侧

```
# 重建（20/20 包）+ 四层体检全过；产物里：
memory_recall_audit=0  memory_search=7  memory_write=5  experience_write=7  experience_stats=3
# 看板 M6 口径（agent-os）：?category=experience&limit=100 → 条数 1 / 今日新增 1
```

## agent-ts 侧

```
grep -rn 'api/memory' src → 0
provider-manager: new AgentOSMemoryProvider()（首选）
jest：provider / integration / distill-task / audit-adapters / recall-audit-tool 5 套全绿（26 条）
（其余失败套件为既有 TS1378 top-level await 编译问题，仓库自带 monitor 样例同样失败）
```

## agent-os 侧

```
curl :8080/health → {"status":"ok"}
launchctl print gui/501/com.pi-investment.agent-os → state = running, pid = 56899
POST /api/v1/memory → 成功；GET /api/v1/memory?category=experience&limit=100 → 1 条
```

## 提交

```
824bc960  refactor(memory): 下线 quantsys-v2 记忆子系统（89 文件 / +3,631 −5,029）
313111a6  refactor(memory): agent-ts 记忆消费迁 agent-os（15 文件 / +360 −1,322）
cf9c8549  docs(REQ-261004202231-bb99): 补 t9 实施结果与测试写法备忘
```

## 任务覆盖对照（covers）

> 验收门禁要求测试文档标注任务覆盖。下面每条把「任务」对到「可复核证据」；
> 其中 t-211fd3…t-02c0a2 是首版被作废的卡（回退重报计划时取消），t-b17dec…t-8a0060 是重报后的活卡，
> t-3b3641 / t-cdb919 是它们的研发与复核子卡——两者覆盖同一批证据，故并列。

- covers: t-211fd3, t-3b3641, t-b17dec — 外部三处记忆消费方摘除：客户端库两个方法、监控前端记忆页与路由菜单、agent-dh 的 recall_audit 工具均删；web-frontend 构建 exit 0；agent-dh 重建产物 memory_recall_audit=0、其余 4 个记忆工具仍在。
- covers: t-1d33ee, t-c54cfc — 注册点摘除：重启日志 Registered: memory 0 次、Failed to import memory 0 次（刻意不留宽容导入分支）。
- covers: t-5c8b1b, t-3a0393 — 端点与仓储：15 个 /api/memory* 全量 curl 全 404；非记忆端点 /api/health 200/163B、/api/simulation/accounts 200/1398B 形状不变。
- covers: t-e64f6e, t-fdbc2a — 领域实现：domain/memory 六文件与空壳端口 IMemoryRepository 删除后，全仓记忆符号 grep 0 命中；v2 重启 /api/health 200。
- covers: t-cc1a66, t-611597 — 测试：collect-only 6565 → 6488（−77 可解释）；分层纯净性 322 → 319 且 memory 相关违规 0 条。
- covers: t-3d3ef2, t-789e83 — 文档：架构页 memory-subsystem-retired.md 落盘并登记索引；agent-dh 记忆页旧口径改掉；wiki_probe 无点名。
- covers: t-02c0a2, t-8a0060 — 数据：dump 5,693B/16 行在手；两库 DROP 后查询报 relation does not exist；4 个迁移脚本标作废；test_orm_db_drift 6 passed。
- covers: t-cdb919 — 复核：reviews/self-review.md 逐条对照六条需求，登记 3 处遗留（子卡台账门禁、agent-os schema 漂移、.env 不再跟踪）。

