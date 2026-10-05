# t-b17dec [重做] 摘除外部三处记忆消费方

> 需求：REQ-261004202231-bb99 quantsys-v2 记忆子系统下线：清引用后删除端点/领域/仓储/测试

## 在做什么
[重做] 摘除外部三处记忆消费方

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
① grep -rn 'api/memory' quantsys-v2-client web-frontend agent-dh/packages → 返回 0 命中；② web-frontend 执行 npm run build → 通过；③ agent-dh 重启后工具清单不包含 memory_recall_audit，其余 4 个记忆工具仍在。

---
## 汇报 1（2026-10-05T02:01:44.095Z，窗口 session-ebe42d9f-2797-48c7-b069-3d24d1da6184）

三处外部记忆消费方摘除完成：客户端库不再有召回审计方法、监控前端不再有「记忆面板」、agent-dh 不再有 memory_recall_audit 工具；删完后 web 前端仍能构建、agent-dh 其余 4 个记忆工具照旧在。

### 完成项

- 客户端库删两个召回审计方法
- 监控前端摘 /memory 路由与菜单项、删记忆页与 api
- agent-dh 删 RecallAuditTool 与注册/再导出、同步删其验收用例
- 自测：web 构建 exit 0；agent-dh 产物 memory_recall_audit=0、其余 4 工具在

### 改动文件

- `quantsys-v2-client/src/client.ts`
- `web-frontend/src/router/index.ts`
- `agent-dh/packages/tools/memory/src/index.ts`

### 下一步

v2 侧注册点/端点/领域/测试/文档/数据按序收尾；agent-ts 迁移见 t9（无独立卡，证据在需求文档）。

---
