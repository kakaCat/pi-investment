---
id: REQ-31e11f-retro
title: REQ-31e11f 复盘：节点详情面板
updated: 2026-09-17
tags: [retro, REQ-31e11f]
---

# 复盘：会话进度流程节点可点击查看详情（REQ-31e11f）

## 交付了什么

会话框流程条 8 节点可点击查看工作记录（产物文档/拆分 DAG/实施进度/执行者追溯），
与看板同源同渲染器；任务卡含提示词+执行记录；文档弹窗 markdown 渲染。

## 踩了什么坑（按损失排序）

1. **设计没对齐就动手，返工三轮**：v1 手风琴全览（否决"太丑"）→ v4 纯文字工作记录
   （方向对但执行粗糙）→ 逐轮修。教训：**UI 类需求先出 ASCII 设计稿让用户拍板再写代码**，
   用户确认稿在 stage-detail-design.md。
2. **"修了但用户看不到"的时间线错位**（最大坑）：页面插件 bundle 由服务启动时读入内存，
   改完必须重启；期间 launchd 作业从 domain 消失、端口被孤儿进程占着，用户多次测试
   都在看旧 bundle。教训：bundle 里放**版本戳**，诊断先看戳；launchd 作业丢失时用
   bootstrap 重注册而不是反复 kickstart。
3. **两套弹窗两套类名**：会话框 .dsh-pm-doc-body 有 markdown 样式，看板
   .dsh-pm-doc-modal-body 没有 → 看板打开全裸奔。教训：**同款 UI 元素必须共享样式类**
   （已统一为 .dsh-pm-md），改样式时全仓扫同类组件。
4. **marked 的 breaks:true 不能乱开**：会把列表延续行拆散、缩进误判为代码块。
   只开 gfm:true。
5. **write 工具覆盖并发改动**：t7 用 write 全量覆盖 styles.ts 撞掉未提交的 t6 改动，
   恢复时又丢了 3 个 CSS 闭合括号 → 构建静默失败供旧包。教训：有并发改动的文件用
   edit 定向改；构建后有 verify-client-build.mjs 门禁兜底。
6. **数据补登记要带正确署名**：backfill 产物时 confirmedBy 误写 human（实为 system），
   被用户当场抓住。审计字段不许伪造。

## 哪些做对了

- 双端共享 StageDetail shape（domain 单一定义），看板与会话框从此不可能脱节；
- DAG 拓扑分层展示拆分方案，比平铺列表直观；
- 393 个测试全绿 + verify-client-build 门禁（括号配对+关键符号）；
- 用户驱动的设计迭代虽然慢，但最终形态（纯文字工作记录）比最初方案好得多。
