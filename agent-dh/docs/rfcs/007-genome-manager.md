# RFC 007: P0-2 genome_manager 工具化（版本快照 / 段更新 / 回滚 / changelog）实现方案

| 字段 | 值 |
|---|---|
| 状态 | 🟡 待评审开工 |
| 创建 | 2026-08-20 |
| 上游 | [RFC 005](005-self-evolving-agent.md) Phase 1 / P0-2；[RFC 006](006-prompt-genome-sections.md)（P0-1，含 6 项审计修订） |
| 依赖 | P0-1 已交付：`packages/genome` 插件、基因组目录、段注册、`reloadSection()`、独立 git 库 |
| 范围 | 基因组**写路径**与版本管理。不做决策打标（P0-3）、不做自动进化（P2 的 prompt_evolver 将调用本方案的工具） |

---

## 1. 目标

让基因组从"只读切分"变为"可安全演进"：

- 可进化段可更新（宪法段**永远拒绝**）
- 每次变更 = 一个版本，git 留痕 + 结构化 changelog
- 变更**热生效**（dispose + 重注册，不重启进程）且自带**渲染金丝雀**：新段渲染失败立即自动还原
- 任意版本可回滚（回滚本身也是一个新版本，历史只增不改）

## 2. 版本模型

```
genome_version（基因组代数）:  g1 → g2 → g3 ...   任何段变更/回滚 +1
section version（段版本）:     principles v1 → v2 ...  仅本段被改时 +1
```

- `genome.json` 增加 `history[]`（封顶 50 条，溢出靠 git log 追溯）：

```json
{
  "version": "g3",
  "section": "principles",
  "section_version": 2,
  "parent": "g2",
  "reason": "蒸馏规则 R-007 纳入：恐慌底+机构吸筹低吸",
  "ts": "2026-08-23T10:00:00+08:00",
  "git_commit": "a1b2c3d",
  "author": "agent",
  "type": "update"        // update | rollback | init
}
```

- git 提交信息结构化：`genome(g3): update principles v1→v2 — <reason>`，使 `git log --oneline` 即是人类可读 changelog
- 同时追加 `genome/CHANGELOG.md`（人类向摘要，含规则 ID 增删清单）

## 3. 新增工具（4 个，均在 `@pi-investment/genome`）

### 3.1 `genome_update` — 更新可进化段

| 参数 | 说明 |
|---|---|
| `section` | 段名（principles / rules / lessons；constitution **硬拒绝**） |
| `content` | 新段全文（markdown） |
| `reason` | 变更理由（**必填**，归因链起点：哪条经验/蒸馏结果驱动） |
| `expected_section_version` | 乐观锁：基于读到的版本改，防止并发覆盖 |
| `force` | 交易时段（9:30-15:00 交易日）默认警告拒改，force=true 才放行（紧急修复通道） |

执行流（**顺序即防线**）：

```
1. 拿写锁（genome.lock，>5min stale 接管）
2. 校验：段存在且 class=evolvable；版本乐观锁匹配；
        content ≤ 8000 字符（token 预算）；花括号安检（A-4）；
        rules 段校验规则 ID 格式（R-\d{3}）并计算 ID 增删清单
3. 备份当前段文件内容（内存快照）
4. 写文件 + genome.json（段版本+1、基因组代数+1、追加 history）
5. git add + commit（结构化 message）
6. reloadSection(section) 热替换
7. 渲染金丝雀：assemble() + renderPrompt() 试渲染
   ├─ 成功 → 追加 CHANGELOG.md，返回新版本信息
   └─ 失败 → 还原文件快照 + git revert + reloadSection 还原 + 返回错误
8. 释放锁
```

返回：新版本号、段版本、git commit、规则 ID 增删、金丝雀结果。

### 3.2 `genome_rollback` — 回滚

| 参数 | 说明 |
|---|---|
| `section` | 要回滚的段 |
| `to_section_version` | 目标段版本（不传 = 上一版本） |
| `reason` | 回滚理由（必填，如"模拟盘 A/B 恶化"） |

- 从 git 历史取目标版本内容 → 走 `genome_update` 同款写入流（含金丝雀）→ 段版本+1，history 记 `type=rollback`
- **回滚不抹历史**：v1→v2→回滚到 v1 内容 = v3（内容同 v1）

### 3.3 `genome_history` — 版本谱系

- 参数：`section?`、`limit?`
- 返回 history 条目 + 每条对应的段版本/代数/理由/commit，供复盘"这轮进化改了什么"

### 3.4 `genome_diff` — 版本对比

- 参数：`section`、`from_version`、`to_version`
- 返回 unified diff，供自我审查与 P2 进化效果分析

## 4. 安全不变量（任何时刻成立）

| # | 不变量 | 保障手段 |
|---|---|---|
| 1 | 宪法段内容永不变 | 写工具硬拒绝 + git 钩不了的人工审计 |
| 2 | 渲染中的提示词永远可渲染 | 金丝雀试渲染 + 失败自动还原 |
| 3 | 历史只增不改 | 回滚=新版本；禁止 git rebase/force-push |
| 4 | 单变量变更 | `genome_update` 一次只改一段；多段进化 = 多次调用各成版本 |
| 5 | 每次变更可归因 | reason 必填，写入 history 与 commit message |
| 6 | 无并发写 | 文件锁 + 乐观锁 |

## 5. 实施步骤

1. 在 P0-1 的 worktree（或新 worktree `feat/genome-p0-2`，基于已合并的 P0-1）上开发
2. `packages/genome/src/` 拆分：`store.ts`（文件+git 读写）、`versioning.ts`（版本模型+history）、`guard.ts`（校验：花括号/大小/规则ID/宪法拒绝/锁）、`index.ts`（Service + 工具注册）
3. git 操作用 `simple-git` 或直接 `node:child_process` 调 git（选依赖更轻的后者，与 lifecycle 的 self-restart 脚本同款）
4. 单元测试：更新/回滚/锁/花括号拒绝/宪法拒绝/金丝雀失败自动还原（mock systemPrompt）
5. schema 冒烟测试已含 genome（P0-1 加入），确认 4 个新工具 schema 通过
6. 合并 main → profile 重启（沿用 RFC 006 A-5 的备份流程）

## 6. 验收标准

| # | 验收 | 方法 |
|---|---|---|
| 1 | `genome_update principles` 后 `self_system_prompt` 可见 v2 新文本，**进程未重启** | 工具调用 + self_system_prompt 对比 |
| 2 | constitution 更新请求被拒且理由明确 | 调 `genome_update section=constitution` |
| 3 | 含 `{{` 的内容被拒/还原，提示词渲染不崩 | 注入坏内容测试 |
| 4 | 金丝雀失败自动还原（构造 renderPrompt 必失败场景） | 单测 + 实测 |
| 5 | `genome_rollback` 后段内容回到目标版本，history 新增 rollback 条目且旧条目仍在 | 工具调用 + genome_history |
| 6 | git log 显示结构化提交；CHANGELOG.md 同步 | `git -C <genomeDir> log --oneline` |
| 7 | 并发/重复调用安全：两把锁都拦得住 | 单测模拟 |
| 8 | 规则 ID 增删清单正确输出 | 修改 rules 段增删 R-xxx 验证 |

## 7. 风险与对策

| 风险 | 对策 |
|---|---|
| 热替换瞬间另一个 agent 正在组装提示词 | 段注册本身原子（dispose→register 极短窗口）；进化纪律上安排在非交易时段，接受此窗口 |
| history 数组膨胀 | 封顶 50 条，完整谱系在 git log |
| git 命令失败（无 git/权限） | 启动时探测 git 可用性，不可用时降级为文件快照版本（versions/ 目录）并告警 |
| 段越改越长 → token 膨胀 | 8000 字符/段硬上限 + genome_list 显示各段字符数便于监控 |
| Agent 在交易时段改基因组 | 默认拒绝，force 通道留痕（history 标 force=true）供复盘问责 |

## 8. 后续衔接

- **P0-3** decision_tagging：读 `genome_version` + 解析 rules 段 R-ID 供交易打标
- **P1** attribution：按规则 ID/基因组代数分组结算盈亏
- **P2** prompt_evolver：LLM 生成新段内容 → 调 `genome_update`（验证门通过后才调）
- 本方案的工具即"基因组的 git"，是 P2 自动进化的**唯一合法写入口**

---

**预计工作量**：2-3 天（store/versioning/guard 拆分 + 4 工具 + 单测 + E2E）。
