# REQ-283168 验证记录

## 修复内容

从 stash@{0}（"暂存主工作区更改以便合并 feat/pmboard-node-diff"）提取并合并：

| 文件 | 恢复内容 |
|------|----------|
| `packages/pages/dsh-pmboard/src/client/view.ts` | buildBoard 增加 view/listOpts/archived 参数；buildListView（排序/分页/done 沉底）、renderListToolbar、renderListCard；NO_ARCHIVED、sessionChipHtml；archived 参数贯穿 renderReqCard/renderWindowChip/renderSessionChip/buildReqDetail/buildTaskDetail/renderCommonContent |
| `packages/pages/dsh-pmboard/src/client/board-mount.ts` | boardView/listSortKey/listSortDir/listPageSize/listPage 状态、sessionStorage 偏好（dsh-pmboard:view / dsh-pmboard:list）、case 'switch-view' / 'list-sort'、list-size onChange、[data-pmpage] 分页 |
| `packages/pages/dsh-pmboard/src/client/styles.ts` | viewswitch/list/toolbar/grouphead/pager 样式 + .dsh-pm-cprog* / .dsh-pm-flow*（会话头部进度条）+ .dsh-pm-window.is-archived |
| `packages/pages/dsh-pmboard/src/client/conversation-progress.ts` | 327 行，原 untracked 未入库，本次随 wip 合并入库 |
| `packages/pages/dsh-pmboard/lib/client.js` | 重建（149060 bytes），12 个关键符号全部验证存在 |

## 证据

1. `git show b8ea13cf --stat`：恢复合并提交，含上述全部文件；
2. `grep -c 'buildListView\|renderListCard\|NO_ARCHIVED\|sessionChipHtml\|dsh-pm-cprog' lib/client.js`：12 符号命中（已逐符号核验）；
3. 服务 :13080 已经 launchctl kickstart 重启，新 bundle 生效；
4. 连带修复：intelligence / scheduler 两包 dist 陈旧（src 新于 dist）已 rebuild；signal_track(source='manual') 实测通过（信号 ID 50）；
5. 善后：stash 全清（备份于 ~/.dsh/stash-backup-20260915/）、quantsys-v2 自动生成 config 已 gitignore（e2d13a06）、全仓 git status 干净。

## 遗留（不在本需求边界内）

- client-view.test.ts:501 断言过期（P2 把甘特图移到任务页后未更新断言）——属 P2 工作线，待其 owner 决策：更新断言或恢复节点内甘特。
- 用户侧最终验收：刷新 :13080 看板页，确认视图切换控件出现、列表可排序分页、会话头部进度条恢复，然后在项目看板点「验收通过」。
