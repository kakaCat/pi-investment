# REQ-283168 复盘：项目看板双视图代码丢失

## 发生了什么

用户发现项目看板丢失「列表+泳道」双视图切换。追查根因：双视图实现当年被 `git stash`
暂存（stash@{0}，描述"暂存主工作区更改以便合并 feat/pmboard-node-diff"），合并完成
（728a77b0）后**忘了 pop**；后续 P0/P1/P2 提交在该工作区上继续开发并提交，stash 里的
view.ts / board-mount.ts / styles.ts 改动就此沉没，board-mount.ts 只留下一处悬空调用
`buildBoard(state, Date.now(), boardView, listOpts(), archivedSids())`。
`conversation-progress.ts` 当时是 untracked 文件，侥幸存活但也一直没入库。

## 被证伪的假设

1. **"stash 是安全的暂存"**——stash 不含 untracked 文件，且 `git log --all` 看不到
   stash/reflog/悬空提交；暂存后没有任何机制提醒"你还有没 pop 的 stash"，丢失是静默的。
2. **"页面正常 = 代码没丢"**——泳道视图一直可用，双视图的缺失没有报错、没有测试拦住，
   直到用户肉眼发现。预存测试 client-view.test.ts:501 甚至已随 P2 改动脱节（断言过期），
   没能充当护栏。
3. **"untracked 文件会一直在"**——conversation-progress.ts 存活纯属运气（没有任何 checkout
   覆盖它），这类文件一旦遇上 clean/切分支就消失。

## 下次怎么做（防回归）

1. **stash 即负债**：暂存后必须当会话内 pop 或转成 wip 分支；跨会话的暂存一律落
   `git stash branch` 或正式分支，不留裸 stash。
2. **合并非本窗口工作前先 `git stash list` + `git status`**：有 stash 先查清来历再动手。
3. **untracked 源码文件视同未完成**：功能交付时 `git status` 里的 ?? 文件必须全部入库
   或明确删除，验收时检查。
4. **dist 包功能验证要拿线上证据**：bundle 符号 grep + 页面实测，不拿源码级绿灯替代。
5. **清理 stash 前先备份**：导出 patch + 记录 hash（本次备份在 ~/.dsh/stash-backup-20260915/），
   git 对象库约 30 天可恢复。

## 关联

- 恢复提交：b8ea13cf；需求档案：docs/requirements/REQ-283168/
- 排查手册新增条目：docs/guides/troubleshooting.md §E（本复盘的三行结论）
