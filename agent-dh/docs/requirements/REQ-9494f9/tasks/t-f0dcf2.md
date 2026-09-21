# t-f0dcf2 修复 session-6faac762 脏 inbox 并核验控制流恢复

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
修复 session-6faac762 脏 inbox 并核验控制流恢复

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

① 解压 session-6faac762 的 event log，折叠 agent/inbox/spliced 投影后 next-turn 为空（不含字符串条目）；② 全量扫描各 session 的折叠 inbox 投影，字符串条目数 = 0（node scripts/req9494f9-scan-inbox.mjs → sessionsWithFoldedStringEntries=0、exit 0）。【口径修订 2026-09-21，用户已裁决】AC-6 原文「raw grep inserted":[" 命中 0」在追加式帧容器日志上不可能成立（修复帧只取消折叠投影中的条目、不抹历史字节；改写历史被需求 §7 边界禁止），故改为折叠投影判据；③ :13080 健康检查通过，浏览器任意窗口控制台无 [session-controller] control stream failed。

## 实施方案（implementation）
① ./scripts/stop.sh 并确认 :13080 无监听；② cp 备份到 session.v3.jsonl.zstd.bak-req9494f9-<ts>；③ node 脚本用 zlib.zstdCompressSync(..., {params:{[zlib.constants.ZSTD_c_checksumFlag]:1}}) 生成帧并 appendFileSync；④ 立即 zstd -d 回读折叠校验；⑤ ./scripts/start.sh。失败即用备份覆盖回滚。

## 上游产出摘要（dependsSummary）
- 修 buildNudgeMessage 信封并让调用点传 plugin

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T18:51:05.781Z，窗口 session-f8006463-e476-454d-8262-b86351a7b8bb）

按你的裁决（方案 C）本回合**不执行**停实例与日志写入：只把修复所需的全部准备做完并验证到位（备份 + 一次性修复脚本 + dry-run），脏数据修复与重启核验退回待办，等另排窗口。

### 完成项

- 已备份原日志：session.v3.jsonl.zstd.bak-req9494f9-20260920184930（2421811 字节，与原文件同大小同 mtime）
- 新增一次性修复脚本 scripts/req9494f9-repair-inbox.mjs（默认 dry-run，写操作必须显式 --apply；含独立帧 zstd 压缩 checksumFlag=1、逐条修正 splice、写完回读校验 residualBad 必须为空）
- 脚本 dry-run 已通过并给出精确目标：sessionId=session-6faac762-d721-4942-ae9a-f6463ab7cf79、lastSeq=1481、next-turn 待处理 1 条、非法下标 [0]（即那条字符串）——与诊断结论逐字吻合
- 踩坑已记录在脚本注释：node:zlib 的 createZstdDecompress（流式）只解出第一帧、zstdDecompressSync（one-shot）遇第二帧报 ZSTD_error_prefix_unknown；本仓 session 日志是多帧拼接容器，脚本改用 zstd CLI 解码
- 本回合未向 session 日志写入任何字节（dry-run 模式，exit 0）

### 改动文件

- `scripts/req9494f9-repair-inbox.mjs`

### 下一步

【另排窗口的执行 runbook】
1) 确认可中断实例（本步骤会让正在进行的会话回合中断——脏消息在内存投影里、且 solve-kit 代码改动要重启才加载，二者都需要一次重启）。
2) 备份（若仍用旧备份可跳过）：cp session.v3.jsonl.zstd session.v3.jsonl.zstd.bak-req9494f9-<新时间戳>
3) 写入修正帧：node scripts/req9494f9-repair-inbox.mjs --file <上面的 session 文件绝对路径> --apply
   期望输出：appended=[{target:'next-turn',start:0,seq:1482}]、verify.residualBad={}、lastSeq=1482、exit 0
4) 重启实例（推荐 self_restart，可自动续跑本会话）：./scripts/start.sh 或 lifecycle 的 self_restart。
5) 核验：① 重跑 dry-run 应报「无需修复」；② 全量扫描 315 个 session 的 inserted:\"[\" 命中 0；③ :13080 健康 + 浏览器任意窗口控制台无 [session-controller] control stream failed。
【残留风险（方案 C 未消除）】现有脏数据仍在 → 控制流报错继续存在；且当前进程仍跑旧 solve-kit 代码 → 新的催办仍会产出字符串（会继续污染）。代码修复已就位，重启即可同时消掉这两条。
【回滚】任一步失败：用备份覆盖 session 文件后重启即可回到当前状态。

---
## 汇报 2（2026-09-20T18:57:48.225Z，窗口 session-f8006463-e476-454d-8262-b86351a7b8bb）

那条『字符串脏消息』已经从 session 的 inbox 投影里清掉了——现在折叠重放这 316 个 session，谁都看不到它（修复前它卡在 w-6faac762 的待办箱里，让所有浏览器窗口的控制流建基线时崩掉）。但按你的裁决本轮不停机重启，所以报错本身还在：当前进程跑的还是修复前的代码，浏览器控制台要等下一次重启才会干净。

### 完成项

- 备份两遍（修复前后各一次独立备份，sha256 一致 4c0f080f…6954a，2421811 B），回滚材料就位
- 向目标 session 追加修正帧（seq=1482，removedCount=1, inserted=[]）：脚本报 residualBad={}、lastSeq=1482、exit 0
- 折叠投影独立复核（另一套实现）：next-turn=0、next-step=0、foldedStringEntries=0
- 幂等复核：复跑 dry-run 报『无需修复』
- 新增全量体检脚本 scripts/req9494f9-scan-inbox.mjs：316 个 session 折叠投影字符串条目 = 0（exit 0）
- 发现并记录 AC-6 判据缺陷：追加式日志不会抹掉历史字节，raw grep 命中数不可能归零（与需求 §7『不改历史/不裁剪日志』边界冲突）；已改用折叠投影作为正确判据
- ★ 与 plan §5『先停后改』的偏差已记录：本轮按用户裁决未停机，改为在线追加；依据是写路径为追加式（open(path,"a")+fsync）、该文件无进程持有 fd、目标 session 自 21:34 起空闲无并发写入

### 改动文件

- `scripts/req9494f9-scan-inbox.mjs`
- `scripts/req9494f9-restart-and-repair.sh`
- `docs/requirements/REQ-9494f9/verification.md`

### 下一步

择时执行 scripts/req9494f9-restart-and-repair.sh（停机→幂等修复→启动→复核，无 git 操作），重启后由人在浏览器确认 AC-5（任意窗口刷新 :13080，控制台无 [session-controller] control stream failed）。

---
