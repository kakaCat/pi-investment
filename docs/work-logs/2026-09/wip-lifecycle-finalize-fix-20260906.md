# agent-self WIP 生命周期修复：收尾必达 main（2026-09-06）

- 日期：2026-09-06（周日）
- 执行窗口：w-856b64ef（investor）｜分支：feat/lifecycle-wip-finalize（worktree：.claude/worktrees/lifecycle-wip-finalize）
- 触发：用户要求审计"agent-self 是怎么创建分支、完成后应合并 main 并切回 main 的工作流，检查一下"
- 对象：agent-dh/packages/lifecycle（self_restart / self_finalize 自修复闭环）
- 最终提交：`92f884da fix(lifecycle): wip 收尾三机制修复 + 测试 30/30`（已 ff 合并进 main，feat 分支与 worktree 已清理）

## 一、审计结论（前置，已获用户批准实施）

机制级 3 处断点，导致**完成的任务可能永不回到 main**：

1. **finalize 是"提示"不是"强制"**：restarter 成功路径从不把 HEAD 交还 base——成功重启后仍停在 agent-self/* wip 分支上继续开发，后续提交全部落在 wip 链上；main 分支永不含成果。收尾依赖 agent 自觉调 self_finalize，缺机器兜底。
2. **mergeFfOnly 过于脆弱**：wip 期间 main 前进（其他会话并行提交）⇒ 快进失败 ⇒ wip 分支滞留，收尾只能抛"请人工处理"。实证：wips 143233/143443/143536 独立于 main@952b1d30，其内容以 cherry-pick 等价形式到达 main，但分支因旧 mergeFfOnly 永久滞留。
3. **潜伏 wip-on-wip 链风险**：在 agent-self/X 上再触发 restart ⇒ 新 wip 以 X 为 base 记录 ⇒ 链式 wip 永不归入 main。

## 二、修复内容（4 处改动，全在 git.ts / index.ts）

| # | 文件 | 改动 | 语义 |
|---|---|---|---|
| 改动1 | index.ts scheduleRestart | wip-on-wip（当前已在 agent-self/*）时 commitOnCurrent 续提交（无改动则 no-op）+ 复用当前分支作 checkpoint，不再建链 | wip 在 wip 上不再 null、不再新建子链，收尾仍把停靠的 wip 合回干线 |
| 改动2 | git.ts finalizeMerge（新）+ index.ts scheduleFinalize | 收尾合并策略化：branch 缺失→already-merged；isMerged→already-merged；cherryPatchMissing===0→already-cherried（合并哈希=main 头，等价内容视为已并入）；否则先 mergeFfOnly→ff-merged；main 前进导致 ff 失败时 3-way --no-ff merge→merged；真冲突→merge --abort + 抛错（wip 保留、消息指名 wip 等人工）。删除权按 outcome：already-cherried 用 -D，其余 -d | 替换脆弱 mergeFfOnly：绝不静默滞留——等价并入与可 3-way 合并的 wip 都能自动收尾 |
| 改动3 | index.ts 私有 resolveTrunkBase（新 3 步）+ git.ts cleanupWipChain / resolveChainBase | base 解析：① pending.base_branch 非 agent-self → 直接用它；② 是 agent-self/* → git 侧沿 first-parent 上溯找父提交所在真实分支（resolveChainBase，跳过 agent-self 前缀）；③ 兜底 main/master；全不可溯→抛错。收尾后 cleanupWipChain 整链清理同前缀下已并入/等价分支（isMerged 或 cherry 等价），未并入分支保留 | 链式 wip 与历史残留（143233/… 型）一并收口；不误删未并入内容（144904 内容在 feat/genome-explain-execution，绝不删） |
| 改动4 | index.ts setupStrandedWipWatchdog（构造期接线） | 启动时发现停在 agent-self/* 且无 pending 记录 ⇒ 记日志 + 向 investor 根 followup 建议收尾；纯建议不自动执行；有任一 pending 时跳过（避免打断在途收尾） | 断点①的机器兜底：重启后若停在 wip 链上至少有人提醒 |

支撑设计：git.ts 公开方法承载策略（测试打真代码，杜绝复刻漂移）；GitRepo 构造新增可注入时钟（默认真实时间，语义不变；测试注入递增时钟避免同秒建 wip 撞名）。

## 三、验证

- vitest 全量 **30/30 绿**（基线 20：cron 10 + finalize 4 + git 6；新增 10：git.test.ts +8 策略化收尾用例、finalize.test.ts +2 回归用例）：
  - commitOnCurrent（返回 head/无改动 null/停在 main）
  - finalizeMerge 五路径：clean-ff→ff-merged 分支保留；already merged；already-cherried（审计实证场景：wip 等价并入 + main 前进 ⇒ 不再抛错、merged_hash=main 头、v3 内容保留、-D 删除）；3-way merged（main 前进加新文件）；真冲突→抛错/中止/保留 wip
  - cleanupWipChain：物理并入+等价并入清掉、未并入保留
  - resolveChainBase：独立 wip→main；链式 wip→链根 main；不存在分支→null（守卫）
  - finalize 回归：等价并入+main 前进 end-to-end 正常收尾；整链清理（收尾主 wip 时同链残留一并清、未并入保留）
- 合并回 main：先 git merge main 同步 4cd2d7d8 进展（快进，15 文件未触碰 lifecycle），提交后主仓 ff 合并 4cd2d7d8..92f884da；git worktree remove + git branch -d 清理；主仓 git status 干净。

## 四、生效提示

lifecycle 代码随 main 已落盘，但**运行中的 DSH profile（:13080）仍加载旧构建**——需在用户知情下重启 profile（self_restart 或手动 start.sh）后新逻辑才生效。本修复发布不自动重启，避免干扰在途会话。
