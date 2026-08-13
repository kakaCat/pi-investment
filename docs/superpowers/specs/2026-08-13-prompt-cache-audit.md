# Prompt Cache 窄腰审计报告（T7 / W2.5）

> 审计：2026-08-13 · 主抓会话 · 数据源：生产 agent 会话 jsonl（`agent:main:wake:default`，173 轮真实用量）
> 结论一句话：**交互轮次缓存已接近最优（中位命中 98.8%），全部损失集中在两类"整前缀失效"场景——W1.4 已修的召回注入（待重启生效）+ 每日 cron 冷启动的 40K 静态信封。**

## 1. 8 层提示词静态/动态清单

`agent-ts/src/services/intelligence/system-prompt-builder.ts` → `buildSystemPrompt()`：

| 层 | 内容 | 变化频率 | cache 友好性 |
|---|---|---|---|
| 1 Identity | IDENTITY.md | 进程级静态 | ✅ |
| 2 Soul | SOUL.md | 进程级静态 | ✅ |
| 3 Tools | TOOLS.md + **121 工具 name+description 全量** + promptGuidelines | 进程级静态（~10K token，估算） | ✅ 但体积大（T8 削减对象） |
| 4 Skills | skills 列表 + 强制路由指令 | 进程级静态 | ✅ |
| 5 Memory | MEMORY.md + USER.md + dailyMemory + recalledMemory | **曾按轮动态（已修，见 §2-A）** | 修复后 ✅ |
| 6 Bootstrap | BOOTSTRAP/PORTFOLIO/AGENTS/HEARTBEAT | 进程级静态 | ✅ |
| 7 Runtime | date（日粒度，当日稳定）+ cwd + model + 启动健康报告（进程缓存） | 日粒度 | ✅ |
| 8 Channel | terminal/api 提示 | 静态 | ✅ |

构建时机：`agent-loop.ts` 以 `systemPrompt: () => ...` 回调交给 SDK，**每 session 构建一次**（2026-08-12 注释明示窄腰原则），不是每轮重建。符合 Hermes 原则。

另外 SDK 层面每请求还携带 121 个工具的完整 JSON schema（不进 system prompt 文本，但计入每请求的 prefix tokens）——首轮冷启动 input=43,032 token 即"system prompt + 全量 schema + 首条消息"的总信封。

## 2. 实测数据（173 轮，wake 会话 2026-08-10~08-12）

| 指标 | 值 |
|---|---|
| 总轮次 | 173 |
| 命中率中位数 | **98.8%**（cacheRead / 总 input） |
| 典型交互轮 | input 400~1,800 + cacheRead 127K~136K（命中 98.6~99.7%） |
| 整前缀失效轮（input>20K 且 cacheRead=0） | **33 轮（19%）** |
| 总未缓存 input | 2,272,208 token |
| 总 cacheRead | 13,205,376 token |
| 总体未缓存占比 | 14.7%（但高度集中） |

整前缀失效轮的时间分布（实证）：

```
2026-08-10T02:00:39  input=43,032  ← cron 02:00 任务冷启动
2026-08-12T02:00:43  input=51,263  ← 次日 cron 冷启动
2026-08-12T02:02:51 ~ 03:10:20  input 56K→91K 全程 cacheRead=0  ← 同一次运行内每轮全 miss
```

## 3. 损失点（按严重度）

### A. 召回注入曾嵌进系统提示词，每轮全量失效【双路径均已修，待重启生效】

08-12 02:00 那次自主运行**每一轮** cacheRead=0（51K→91K 全价支付约 30 轮）。
根因经 git 考古确认：旧代码 `buildSystemPromptForContext(ctx, userMessage)` 把
`prefetch(userMessage)` 的召回结果嵌进系统提示词——用户消息每轮不同 → 系统提示词每轮变 →
64-token 块前缀从第 0 位即断裂 → 整轮零命中。

修复分两路径（CLI 路径 W1.4 已修；**gateway 路径是本次审计新发现的残留**）：
- CLI 路径（W1.4，1bea2b4）：召回注入移到 session-factory prompt 包装层（追加到最新用户消息尾部）。
- **gateway 路径（wake/feishu——线上零命中的真正事发地，本次审计发现）**：
  `gateway/session-factory.ts` 的 `beforePrompt` 每轮 `autoRecall(text)` + `readDailyMemory`
  重建系统提示词并 `setSystemPrompt`——W1.4 只修了 CLI 包装层，gateway 这条每轮重建链仍在。
  已修复（与 T8 同批提交）：系统提示词只在 createSession 构建一次（dailyMemory 创建时快照），
  召回内容改为 `addMessage` 追加到消息流尾部（append-only 保前缀）。

**但 agent 进程未重启，线上仍是旧行为——每轮全价。**
预估损失：一次 90 分钟的 cron 运行 ≈ 2M 未缓存 input，按 DeepSeek 缓存价差约等于多付 ~5 倍该段费用。

### B. 每日 cron/首会话冷启动信封 ~40-50K token【T8 削减对象】

DeepSeek 磁盘缓存 TTL 为小时级，每日 02:00/09:00 等首批任务必然冷启动，全价支付静态信封。
信封 = system prompt（含 ~10K 工具描述块）+ 121 个工具 JSON schema + bootstrap 文件。
**T8（Tool Search 三段式）把 schema 面从 121 全量压到 ~20 core + 3 元工具**，
预估静态信封 40K+ → 10-15K，每次冷启动省 ~25-30K token，每日多次冷启动累计可观；
且交互轮的 cacheWrite/前缀也更短。

### C. 压缩重建（compaction）后历史全部重付【可接受，暂不优化】

input 40K 级 + 部分 cacheRead 的轮（69.5%、34-36% 命中）对应压缩后首轮——摘要替换历史，
后半前缀断裂。T3 四件套已优化压缩安全性；频次低（长会话才触发），优先级最低。

## 4. 重构建议（按 ROI）

1. **立即：重启 agent 进程**——让 W1.4 的召回移位生效，消灭损失点 A（当前线上每轮全价）。
2. **T8 执行（已随本报告同批落地）**：core 常驻 25 + `tool_search/tool_describe/tool_call` 三件套，
   schema 面 53,871 → 14,057 字符（-74%），描述面 30,995 → 10,960（-65%），
   估算每请求省 ~20K token。3 任务实测通过（pool 查询/缠论分析/持仓查询），
   缓存命中正常（cacheRead 36K-236K）。kill-switch：`PI_TOOL_SEARCH=off`。
3. **监控**：在 attachLogger 里对 `cacheRead=0 且 input>20K` 的轮次打 warn 日志，
   让"整前缀失效"未来可见（目前只有事后扒 jsonl 才能发现 A 类事故）。
4. **不做**：为压缩重建做缓存优化（频次低）；把 date 从 Runtime 层移除（日粒度已足够稳定）。

## 5. 验收核对（工单要求）

- [x] 8 层静态/动态清单（§1 表）
- [x] prompt cache 命中证据（DeepSeek usage 的 cacheRead 字段，10+ 轮采样 → §2 表，173 轮全量统计）
- [x] 报告含数据表、现状/损失点/重构建议/预估收益
