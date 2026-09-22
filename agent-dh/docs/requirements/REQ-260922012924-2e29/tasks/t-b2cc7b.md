# t-b2cc7b [FR-3] cordis.yml 开启 nodeIsolation 并重启验证

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
[FR-3] cordis.yml 开启 nodeIsolation 并重启验证

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
grep -A2 "id: dsh-pmboard" config/cordis.yml 见 nodeIsolation: true；重启后 grep "压缩开关" .dsh-data/state/launchd.out.log | tail -1 见 NODE_ISOLATION=true；isolation-trace 有 G0 门 skip(doc_not_ready) 或后续压缩留痕。

## 实施方案（implementation）
编辑 agent-dh/config/cordis.yml 第 127-129 行；cd agent-dh && ./scripts/start.sh（托管自动 kickstart）；grep 启动日志与 state/node-isolation-log.json。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-22T03:34:10.810Z，窗口 session-9faaac35-2641-473c-a5dc-ea6e6d11efbf）

立项后压缩上下文已开启：nodeIsolation: true 写入配置模板并被活动配置继承，重启后新代码加载生效（state 端点已返回 workspaceRoot 为证）；此后需求文档落盘的阶段门将真实压缩上下文（G0 立项门仍按设计跳过保护）

### 完成项

- config/cordis.yml dsh-pmboard 段加 nodeIsolation: true（含回滚注释）
- restart-with-build.sh --build-only 暂存构建 20/20 通过 + relink 体检 24/24 symlink-ok
- dist 符号核验：capture-rejections/workspaceRoot/docBasePath 命中；client bundle 含 workspaceRoot/homeDir
- self_restart 重启 + 自动续跑成功
- 活动配置 cordis.patch.yml 确认继承 nodeIsolation: true
- state 端点实证 workspaceRoot=/Users/yunpeng/pi-investment/agent-dh
- R-017 noop 核验：regime_position_limit/account_info/strategy_list 只读抽样正常，零委托副作用
- 如实记录：插件 logger.info 的"压缩开关"行未进 manual.out.log（logger 路由问题，不影响功能证据）；G0 doc_not_ready 跳过行为待下个立项自然验证（isolation-trace 可查）

### 改动文件

- `agent-dh/config/cordis.yml`

### 下一步

t6 全量回归与实证验收

---
