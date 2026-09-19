# REQ-81aabd 验收（verification）

> 自动生成于 reqboard_verify_submit

## 验收结论
交付结论：需求流水线的「设计」节点名正式从 planning 改为 design（中文「设计」，替代原「技术设计」），并对设计阶段做文档建模——看板设计节点逐份列出四份设计文档的已交/未交，与磁盘实际文件一致。改动同时落到代码（RequirementStatus / protocol / ArtifactSpec / ArtifactSync / 客户端）、文档（workflow-stages.md、stage-naming-final.md）与持久化台账（schemaVersion 6→7，旧键 planning / reviewing 一次性改写）。全流程实测：停旧进程 → 台账迁移 → launchctl 起新进程 → 起后复核未被回写；设计节点接口返回 4/4 已交；客户端产物重建后 grep planning 计数为 0；回归 97 文件 / 1250 用例全绿。

## 证据清单
- 命令 pnpm build:client（工作目录 packages/pages/dsh-pmboard，2026-09-19 17:54）→ 输出 Build complete in 557ms 与 wrapped dsh-pmboard；产物 packages/pages/dsh-pmboard/lib/client.js = 229219 字节、packages/pages/dsh-pmboard/lib/client.cjs = 228962 字节
- 命令 node packages/pages/dsh-pmboard/scripts/verify-client-build.mjs → [verify-client] OK bundle=229219 bytes, 关键符号齐全, styles.ts 括号配对（退出码 0）
- 命令 grep -c planning packages/pages/dsh-pmboard/lib/client.js → 0；命令 grep -c designDocs packages/pages/dsh-pmboard/lib/client.js → 1（旧键名在客户端产物中已归零）
- 命令 npx vitest run（工作目录 packages/pages/dsh-pmboard，2026-09-19 17:55）→ Test Files 97 passed (97) / Tests 1250 passed (1250)
- 重启与迁移编排日志 .dsh-data/req81aabd-restart.log：[2/8] SIGTERM 旧进程 pid 3956 → 17:44:49 端口 13080 释放；[3/8] migrate --apply 由 v6 到 v7，差异 81 条全部命中白名单（C3 状态改名 26 条 / C11 产物阶段改名 24 条）；[5/8] launchctl bootstrap 成功，新进程 pid 24494（state=running）；[7/8] 起后复核 schemaVersion 仍为 7（revision 1587 到 1593）
- 迁移前备份与回滚路径：.dsh-data/dsh-reqboard.json.bak-req47939a-1789811089（回滚须连文件与进程一起回，v6 读路径无法读 v7 文件）
- 台账 .dsh-data/dsh-reqboard.json：schemaVersion=7、revision=1593；REQ-81aabd 产物含 4 条 design/design（架构、数据模型、接口、测试用例四份 md）与 1 条 design/plan（plan.md）
- 设计节点接口实测：curl http://127.0.0.1:13080/dashboard/api/reqboard/requirements/REQ-81aabd/stage/design → HTTP 200，返回体 body.designDocs 四份 submitted 全为 true
- 磁盘实际文件（命令 ls docs/requirements/REQ-81aabd/design/）→ architecture.md、data-model.md、interfaces.md、test-cases.md，与接口返回逐份一致（证明「已交」判定非写死）
- R-017 部署后空操作核验（审计编号 DEC-20260919175701-bb814ea2）：只读抽样 regime_position_limit（regime=risk_off、verdict=compliant、熔断未触发）、account_info（agent_brain，总资产 500143 元、现金 485920 元）、strategy_list（101 条）均正常；rules 段版本 23、共 19 条规则编号 R-001 到 R-020 无重复，R-006 三重钳制 / R-007 回撤熔断 / R-016 样本门槛均在位；零委托副作用
- 文档交付：docs/architecture/workflow-stages.md（七节点中英文对照表 + 旧键迁移 v6 到 v7 + 停机窗口迁移时序硬约束）、packages/pages/dsh-pmboard/docs/stage-naming-final.md（改名范围、理由与禁止做法）
