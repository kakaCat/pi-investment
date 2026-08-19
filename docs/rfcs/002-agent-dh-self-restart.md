# RFC 002: Agent-DH 自修复重启工具（self-restart）

- 状态：设计已确认，待实施
- 日期：2026-08-19
- 作者：Claude + yunpeng
- 涉及项目：agent-dh（pi-investment monorepo）

## 背景

agent-dh 是 DSH profile（14 插件 / 48 工具），以 tsx 模式跑在 :13080，是全体系唯一没有进程托管的常驻服务（v2-api/web/pg 均有 launchd KeepAlive）。当前重启只能靠人工 `kill + ./start.sh`。

目标场景（用户确认的三个）：

1. **代码修复后生效**：agent 修改自己的插件代码（tsx 模式重启即加载新代码），重启后验证修改
2. **卡死/异常自恢复**：工具失效、上下文污染时重启清空状态
3. **定期维护性重启**

核心风险：agent 改错代码（如语法错误）→ 重启起不来 → 永久变砖。因此重启机制必须带 **git 安全网**：检查点、启动失败自动回滚、验证通过才合并。

## 关键调研结论

- DSH 框架提供会话持久化（`~/.dsh/sessions/**/session.jsonl.zstd`），CLI 支持 `--resume`
- **`AgentLoop` 服务暴露编程式唤醒接口**：`agent.send(message, target, wakeup)`（`vendor/dsh/agent-loop/lib/types/agent.d.ts:32`）。插件可在启动后直接向 agent 注入消息，实现无人工干预的自动续跑
- 现成参考：`~/.dsh/restart-web-ui.sh`（kill → nohup → 轮询端口验证）与 `scripts/ops/pi-services.sh`
- tsx 模式：重启即加载最新 TS 源码，无需构建

## 总体流程

```
【修改阶段】agent 修改插件代码（tsx 模式，落盘即新代码）
     ↓
【检查点】agent 调用 self_restart(reason, resume_task)
  ① git checkout -b agent-self/yyyymmdd-hhmmss（改动随工作区带到新分支）
  ② git add -A agent-dh/ && git commit -m "wip(agent-self): <reason>"
  ③ 记录 checkpoint（wip 分支名）、last_known_good（main 当前 HEAD）
  ④ 落盘 state/pending-resume.json
  ⑤ spawn detached 重启器，工具立即返回"重启已安排"
     ↓
【重启阶段】（agent 进程已死，重启器兜底）
  ⑥ sleep 5s → kill 旧 PID → 等退出 → start.sh 拉起新进程
  ⑦ 健康检查：轮询 :13080 最多 120s
     ├─ 成功 → 写 state/restart-result.json {status: "ok"}
     └─ 失败 → git checkout main（工作区回滚到 last_known_good）
              → 保留失败的 wip 分支（供 agent 复盘 diff，不删）
              → 再次拉起 → 写 {status: "rolled_back", failed_branch, log}
              → 第二次也失败 → 写 {status: "dead"} 并停止（防循环）
     ↓
【续跑阶段】新进程 ready，lifecycle 插件读 pending-resume.json
  ⑧ 通过 AgentLoop.send() 向 investor agent 注入唤醒消息：
     - ok 路径：「重启成功（checkpoint=<分支>）。请执行验证：<resume_task>。
       验证通过后调用 self_finalize(merge) 合并回 main；
       失败则修复后再次 self_restart，或 self_finalize(rollback) 放弃修改」
     - rolled_back 路径：「上次修改导致启动失败，已自动回滚到 main(<hash>)。
       失败分支 <分支名> 已保留，日志在 <path>。请 diff 复盘后重新修复」
  ⑨ agent 自动继续，闭环完成
```

## 组件设计

### 1. `packages/lifecycle/` 插件（新，第 15 个插件包）

cordis Service 模式，与现有插件一致（`static inject = ['tools', 'agent_loop']`，构造函数注册工具）。三个工具：

| 工具 | 参数 | 作用 |
|---|---|---|
| `self_restart` | `reason: string`, `resume_task: string` | 建 wip 分支检查点 → 落盘 pending-resume.json → spawn 重启器 → 立即返回 |
| `self_finalize` | `action: 'merge' \| 'rollback'` | 验证完成后调用。merge：`git checkout main && git merge --ff-only <wip>` 并更新 last_known_good；rollback：checkout main 并保留 wip 分支。注意：checkout main 会瞬间把工作区文件改回 main 内容、merge 后立即恢复为 wip 内容，运行中进程不受影响（代码已在内存），无需再重启 |

**实现注意**：cordis 服务名 `agent_loop` 需在实现时对 `cordis.patch.yml` 里的实际插件 id 核实；所有 git 操作由 DSH 进程内的插件执行，不经过 Claude Code 会话的 worktree 钩子。
| `self_status` | 无 | 返回当前分支、pending 任务、last_known_good、重启计数、上次重启结果（agent 自检用） |

**启动续跑**：插件在 `ctx.on('ready')` 检查 `state/pending-resume.json`，存在则注入 `agent_loop` 服务获取 investor agent，调用 `send()` 注入续跑消息，然后把文件改名为 `pending-resume.done.json`（防重复触发）。若 agent 尚未就绪则重试（最多 10 次，间隔 3s）。

### 2. `scripts/self-restart.ts`（重启器，TS 单文件）

- 运行方式：`node --import tsx/esm scripts/self-restart.ts`（tsx 已在 DSH 启动链中，零新增依赖）
- spawn 时 `detached: true + stdio: 'ignore' + unref()`，脱离 agent 进程组，agent 死后继续执行
- **铁律：自包含，只准用 node 内置模块（child_process/fs）+ git CLI，禁止 import `packages/*` 任何代码**——它的职责是在插件崩掉时兜底回滚，自身不能依赖可能崩掉的东西
- 职责：kill 旧进程 → 拉起 → 健康检查 → 失败自动回滚重拉 → 写 restart-result.json

### 3. `profiles/investment/start.sh`（不变）

仍由重启器调用。若 agent 当前是手动启动的，重启后变为重启器 nohup 托管，行为一致。

## 状态文件

统一放 `~/.dsh/profiles/investment/state/`：

| 文件 | 写入方 | 内容 |
|---|---|---|
| `pending-resume.json` | self_restart | `{reason, resume_task, checkpoint_branch, last_known_good, attempt, ts}` |
| `restart-result.json` | self-restart.ts | `{status: ok\|rolled_back\|dead, failed_branch?, log_path, ts}` |
| `last-known-good` | self_finalize | 上次验证通过的 main commit hash |
| `restart-counter.json` | self_restart | `{window_start, count}` 速率限制计数 |

## 护栏

1. **速率限制**：每小时最多 3 次 self_restart（计数落盘），超限拒绝执行
2. **防重入**：存在 `state/restarting.lock` 时拒绝新的 self_restart
3. **attempt 上限**：同一 resume_task 连续启动失败 2 次 → 回滚后停止自动重试，续跑消息注明「已回滚且不再自动重试」，防止死循环
4. **main 保护**：wip 提交只进 `agent-self/*` 分支；只有 `self_finalize(merge)` 才动 main
5. **失败现场保留**：启动失败的 wip 分支不删除，重启器输出写 `state/restart-<ts>.log`

## 错误处理矩阵

| 场景 | 行为 |
|---|---|
| 插件语法错误，进程起不来 | 重启器端口轮询超时 → 回滚 main → 重拉 → agent 收到 rolled_back 消息 |
| 进程起来但 120s 内端口不通 | 同上（视同启动失败） |
| 回滚后也起不来 | 写 status=dead，停止重试，等待人工 |
| agent 验证不通过 | agent 选择：修复后再 self_restart，或 self_finalize(rollback) |
| 重启器自身崩了 | agent 进程已被 kill，服务停止；last_known_good 未损坏，人工 `./start.sh` 即可恢复（代码在 main 上是好的） |

## 测试

1. **vitest 单测**：git 操作封装（建分支/提交/合并/回滚）、状态文件读写、速率限制、attempt 计数（git 操作抽到 `packages/lifecycle/src/git.ts`，用临时仓库测）
2. **手动 E2E 验收**：
   - 正常路径：改一个插件的描述文案 → self_restart → 确认续跑消息注入 → self_finalize(merge) → main 历史干净
   - 崩溃路径：故意在插件里写语法错误 → self_restart → 确认自动回滚、agent 复活、收到 rolled_back 消息、失败分支保留
   - 限流：连续调用 4 次 self_restart，第 4 次被拒

## 非目标（本期不做）

- launchd 托管（com.pi-investment.agent-dh.plist）：作为后续加固项，与本设计不冲突（续跑机制可直接复用）
- 定期维护性重启的 cron 触发：工具就绪后由调度配置驱动，无需额外开发
- quantsys-v2 / web 等其他服务的重启

## 实施清单

1. `packages/lifecycle/`：package.json、src/index.ts（插件+三工具+ready 续跑）、src/git.ts、src/state.ts
2. `scripts/self-restart.ts`：自包含重启器
3. `~/.dsh/profiles/investment/cordis.patch.yml`：注册 lifecycle 插件；profile package.json 加 file: 依赖
4. 测试：packages/lifecycle 单测 + 手动 E2E
5. 文档：agent-dh/CLAUDE.md 增补 lifecycle 插件说明与 port/状态文件约定
