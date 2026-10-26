# t-f9a9b3 回归与生产只读核查

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
回归与生产只读核查

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
venv/bin/python -m pytest tests -k "watch or fill or todo or trading" -q 退出码 0（存量 2 例失败先定性并记录）；三条只读 SQL 均返回结果且与设计预期一致。

## 实施方案（implementation）
在仓库根跑 watch/fill/todo/trading 相关回归并记录结果；用三条只读 SQL 核查生产证据（成交回写明细、盘后扫描轮次、统计与台账对账），结果写入交付说明。

## 上游产出摘要（dependsSummary）
- 补挂止损/止盈写持仓状态
- 执行闭环统计端点
- 新闻与政策扫描接入消息桥
- sidecar 拆盘中/盘后，盘后消息可扫
- 成交收敛端到端场景
- 组合根装配与降级开关

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T12:53:49.055Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

回归 1195 例通过；仅 2 例存量基线失败。生产只读核查完成，执行统计可读、成交回写待重启生效。

### 完成项

- 全量回归 pytest -k watch/fill/todo/trading → 1195 passed，2 failed 均为存量基线（test_watch_t12 市场级路由未同步，非本次改动）
- 生产只读：exec_stats 可读（executed=0 / declined=22 / unresolved=2 / timeout=146；时延样本 0，尚无 agent 成交回写）
- 生产只读：watch_triggers 含 exec 明细 0 行（新链路待重启生效）
- 生产只读：watch_todos evidence 尚 0 行（消息待办尚未产生）
- 失败定性：2 例存量失败与本次三条接缝无关（实现前已复现）

### 下一步

复核与收尾：确认基线失败定性、准备验收材料

---
## 汇报 2（2026-10-21T12:54:01.335Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

测试通过：回归 1195 例与生产只读核查完成；2 例存量失败已定性，生产生效需重启。

### 完成项

- 回归读数量化：1195 passed / 2 failed（均为 test_watch_t12 存量基线，实现前已复现）
- 生产统计只读：executed=0、declined=22、unresolved=2、timeout=146；时延样本 0（待重启后真实成交回写）
- 生产明细只读：watch_triggers 含 exec 明细 0 行、evidence 0 行（新链路待进程重启生效）
- 结论：代码侧证据齐备；生产生效依赖一次服务重启（launchctl kickstart）

### 下一步

复核：确认验收材料与重启口径

---
## 汇报 3（2026-10-21T12:54:06.767Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

复核结论：基线、重启与遗留口径均如实登记；证据齐备可交验收。

### 完成项

- 基线定性复核：2 例失败与本次三条接缝无关（市场级路由未同步旧用例），实现前已复现
- 重启口径：生产 5001 进程仍跑旧代码，需 launchctl kickstart -k 后新链路生效（未擅自重启）
- 遗留登记：既有 due_at naive 写入口径未在本期修；执行期限链已绕开该口径
- 验收材料清单：8 张卡汇报 + 迁移两库回执 + 1195 例回归读数

### 下一步

本卡关闭后需求进入验收，提交验收材料

---
## 汇报 4（2026-10-21T12:55:05.317Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

补齐验收证据文件（回归 + 生产只读 + 生效条件），作为本卡的结单凭证。

### 完成项

- 新增验收证据文件：全量回归读数、专项命令读数、生产只读核查、生效条件与遗留登记
- 证据文件路径 docs/requirements/REQ-261021194640-69b8/verification-evidence.md

### 改动文件

- `docs/requirements/REQ-261021194640-69b8/verification-evidence.md`

### 下一步

关闭本卡，需求进入验收

---
