# agent-dh 目录骨架对齐 deepseek-harness 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 agent-dh 的 23 个平铺包 + packages/pages/* 重组为 `packages/{tools,web,client,runtime,core}/` 两级结构，包名全部不变，单一原子提交。

**Architecture:** 纯目录搬迁（git mv 保历史）+ 引用点同步。跨包 import 全走包名（`@pi-investment/*`），源码零改动；需同步的只有 workspace glob、4 个脚本、4 个测试文件、1 个 package.json 字段、CLAUDE.md 结构章节。

**Tech Stack:** pnpm workspace / tsx / vitest / dsh profile（:13080）

**Spec:** [agent-dh/docs/rfcs/015-dsh-structure-alignment.md](../../rfcs/015-dsh-structure-alignment.md)

**包迁移映射（30 个，权威清单）：**

| 目标 | 成员（17 tools / 7 web / 1 client / 4 runtime / 1 core） |
|---|---|
| `packages/tools/` | competition, data-manager, evolution, evolver, factor, genome, intelligence, investment, learning, lifecycle, market, memory, notification, risk, scheduler, strategy, trading |
| `packages/web/` | bulletin, dsh-pmboard, execution, genome, holdings, page-kit, web-liveness |
| `packages/client/` | agent-dh-client |
| `packages/runtime/` | agent-os-manager, investment-agent-loop, quantsys-v2-manager, solve-kit |
| `packages/core/` | core-tool |

---

### Task 0: 前置检查（硬门槛，不满足就停）

**Files:** 无（只读检查）

- [ ] **Step 1: 确认在 main 且 wip 已合并**

```bash
cd /Users/yunpeng/pi-investment
git branch --show-current   # 期望: main
git branch --contains 6c9d45bb | grep -x '\* main\|main'   # 期望有输出（wip 已上岸）
```

- [ ] **Step 2: 确认 pmboard/其他会话无在途改动**

```bash
git status --porcelain
```

期望：完全无输出（工作区干净）。若有输出 → **停**，等对应会话收尾后再来。

---

### Task 1: 建隔离 worktree 并提交 RFC

**Files:**
- Create: `.claude/worktrees/dsh-structure/`（worktree）
- Commit: `agent-dh/docs/rfcs/015-dsh-structure-alignment.md`、`agent-dh/docs/rfcs/015-dsh-structure-alignment-plan.md`

- [ ] **Step 1: 建 worktree（EnterWorktree 基于 origin/main，必须立即 rebase 本地 main）**

```bash
cd /Users/yunpeng/pi-investment
git worktree add .claude/worktrees/dsh-structure -b feat/dsh-structure-alignment main
cd .claude/worktrees/dsh-structure
git log --oneline -1   # 期望: 55ce432b 或更新的本地 main 头
```

- [ ] **Step 2: 把 RFC 和本计划拷进 worktree 并提交**

```bash
cd /Users/yunpeng/pi-investment
cp agent-dh/docs/rfcs/015-dsh-structure-alignment.md .claude/worktrees/dsh-structure/agent-dh/docs/rfcs/
cp agent-dh/docs/rfcs/015-dsh-structure-alignment-plan.md .claude/worktrees/dsh-structure/agent-dh/docs/rfcs/
cd .claude/worktrees/dsh-structure
git add agent-dh/docs/rfcs/015-dsh-structure-alignment.md agent-dh/docs/rfcs/015-dsh-structure-alignment-plan.md
git commit -m "docs(rfc-015): agent-dh 目录骨架对齐 deepseek-harness 提案与实施计划"
```

---

### Task 2: git mv tools 域（17 个包）

**Files:** `packages/<name>/` → `packages/tools/<name>/`（17 个目录）

- [ ] **Step 1: 建目标域目录并逐个 git mv**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh
mkdir -p packages/tools
for p in competition data-manager evolution evolver factor genome intelligence investment learning lifecycle market memory notification risk scheduler strategy trading; do
  git mv "packages/$p" "packages/tools/$p" || echo "FAILED: $p"
done
```

期望：无 FAILED 输出。

- [ ] **Step 2: 验证移动结果**

```bash
ls packages/tools | wc -l        # 期望: 17
ls packages/                     # 期望只剩: agent-dh-client agent-os-manager core-tool investment-agent-loop pages quantsys-v2-manager solve-kit（+ tools）
```

---

### Task 3: git mv pages → web（7 个包）

**Files:** `packages/pages/<name>/` → `packages/web/<name>/`（7 个目录）

- [ ] **Step 1: 移动**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh
git mv packages/pages packages/web
```

- [ ] **Step 2: 验证**

```bash
ls packages/web | sort   # 期望: bulletin dsh-pmboard execution genome holdings page-kit web-liveness
```

---

### Task 4: git mv client/runtime/core 域（6 个包）

**Files:** `packages/{agent-dh-client,agent-os-manager,investment-agent-loop,quantsys-v2-manager,solve-kit,core-tool}/`

- [ ] **Step 1: 移动**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh
mkdir -p packages/client packages/runtime packages/core
git mv packages/agent-dh-client packages/client/agent-dh-client
git mv packages/agent-os-manager packages/runtime/agent-os-manager
git mv packages/investment-agent-loop packages/runtime/investment-agent-loop
git mv packages/quantsys-v2-manager packages/runtime/quantsys-v2-manager
git mv packages/solve-kit packages/runtime/solve-kit
git mv packages/core-tool packages/core/core-tool
```

- [ ] **Step 2: 验证 packages/ 下只剩 5 个域目录**

```bash
ls packages/   # 期望恰好: client core runtime tools web
```

---

### Task 5: workspace glob 同步

**Files:**
- Modify: `agent-dh/pnpm-workspace.yaml`
- Modify: `agent-dh/package.json`（`workspaces` 字段）

- [ ] **Step 1: 改 pnpm-workspace.yaml**

把：

```yaml
packages:
  - 'packages/*'
  - 'packages/pages/*'   # 页面域（dashboard 等子包嵌套在此）
  - 'apps/*'
```

改为：

```yaml
packages:
  - 'packages/*/*'       # 两级技术域：tools/web/client/runtime/core
  - 'apps/*'
```

（`'skills/*'`、`'../agent-os-client'`、`'../quantsys-v2-client'` 三行保持不变）

- [ ] **Step 2: 改 root package.json 的 workspaces 字段**

把：

```json
"workspaces": [
  "apps/*",
  "packages/*",
  "packages/pages/*",
  "profiles/*"
],
```

改为：

```json
"workspaces": [
  "apps/*",
  "packages/*/*",
  "profiles/*"
],
```

---

### Task 6: 路径引用 codemod（scripts/tests/config）

**Files:**
- Modify: `agent-dh/scripts/req47939a-message-inventory.mjs`、`req47939a-lit-diff.mjs`、`req81aabd-restart-and-migrate.sh`、`audit-tool-output-contract.mjs`、`restart-with-build.sh`
- Modify: `agent-dh/tests/plugin-schema.smoke.test.ts`、`tests/m3/m3-3-signal-track.test.ts`、`tests/reqboard-task-execute.test.ts`、`tests/task-retry.test.ts`
- Modify: `agent-dh/packages/web/dsh-pmboard/package.json`（repository.directory 字段）

- [ ] **Step 1: pages→web 机械替换（必须最先跑，避免被 tools 规则误伤）**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh
grep -rl "packages/pages/" scripts tests config --include='*.mjs' --include='*.ts' --include='*.sh' --include='*.yml' --include='*.yaml' \
  | xargs perl -pi -e 's{packages/pages/}{packages/web/}g'
```

- [ ] **Step 2: tools 域逐包替换**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh
for p in competition data-manager evolution evolver factor intelligence investment learning lifecycle market memory notification risk scheduler strategy trading; do
  grep -rl "packages/$p/" scripts tests config --include='*.mjs' --include='*.ts' --include='*.sh' \
    | xargs perl -pi -e "s{packages/$p/}{packages/tools/$p/}g"
done
# genome 单独处理（pages/genome 已被 Step 1 改成 web/genome，此处只命中 host 插件路径）
grep -rl "packages/genome/" scripts tests config --include='*.mjs' --include='*.ts' --include='*.sh' \
  | xargs perl -pi -e "s{packages/genome/}{packages/tools/genome/}g"
```

- [ ] **Step 3: client/runtime/core 域替换**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh
perl -pi -e 's{packages/agent-dh-client/}{packages/client/agent-dh-client/}g' $(grep -rl "packages/agent-dh-client/" scripts tests config 2>/dev/null || true)
for p in agent-os-manager investment-agent-loop quantsys-v2-manager solve-kit; do
  grep -rl "packages/$p/" scripts tests config --include='*.mjs' --include='*.ts' --include='*.sh' \
    | xargs perl -pi -e "s{packages/$p/}{packages/runtime/$p/}g"
done
grep -rl "packages/core-tool/" scripts tests config --include='*.mjs' --include='*.ts' --include='*.sh' \
  | xargs perl -pi -e "s{packages/core-tool/}{packages/core/core-tool/}g"
```

- [ ] **Step 4: audit-tool-output-contract.mjs 的 ROOTS 特判**

把 [audit-tool-output-contract.mjs](agent-dh/scripts/audit-tool-output-contract.mjs) 第 28 行：

```js
const ROOTS = ['packages', 'packages/pages']
```

改为：

```js
const ROOTS = ['packages']
```

- [ ] **Step 5: pmboard 的 repository.directory 字段**

把 [packages/web/dsh-pmboard/package.json](agent-dh/packages/web/dsh-pmboard/package.json) 中：

```json
"directory": "agent-dh/packages/pages/dsh-pmboard"
```

改为：

```json
"directory": "agent-dh/packages/web/dsh-pmboard"
```

- [ ] **Step 6: 全量复核——不允许有漏网的旧路径**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh
grep -rn "packages/pages" scripts tests config package.json pnpm-workspace.yaml 2>/dev/null   # 期望: 无输出
for p in competition data-manager evolution evolver factor intelligence investment learning lifecycle market memory notification risk scheduler strategy trading agent-dh-client agent-os-manager investment-agent-loop quantsys-v2-manager solve-kit core-tool; do
  grep -rn "packages/$p/" scripts tests config package.json 2>/dev/null | grep -v "packages/tools/\|packages/client/\|packages/runtime/\|packages/core/"
done   # 期望: 无输出
```

- [ ] **Step 7: 包内跨包相对 import 检查（应为零，发现即手工修）**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh
grep -rn "from '\.\./\.\./" packages/*/*/src --include='*.ts' 2>/dev/null | grep -v node_modules   # 期望: 无输出
```

---

### Task 7: CLAUDE.md 结构章节更新

**Files:** Modify: `agent-dh/CLAUDE.md`（Project Structure 一节）

- [ ] **Step 1: 把 Project Structure 代码块中的 packages 部分改为**

```
agent-dh/
├── packages/                    # 投资插件包（两级技术域，对齐 deepseek-harness）
│   ├── tools/                  # host 工具插件（17 个：trading/market/risk/strategy/...）
│   ├── web/                    # 页面插件（7 个：bulletin/dsh-pmboard/execution/genome/holdings/page-kit/web-liveness）
│   ├── client/                 # API 客户端库（agent-dh-client）
│   ├── runtime/                # 运行时/管理包（agent-os-manager、investment-agent-loop、quantsys-v2-manager、solve-kit）
│   └── core/                   # core-tool（三段式接口类型规范）
│   ├── (quantsys-v2-client 已迁移至仓库顶层 ../../quantsys-v2-client，插件经 file: 依赖引用)
```

- [ ] **Step 2: 全文检索 CLAUDE.md 里残留的旧路径**

```bash
grep -n "packages/pages\|packages/investment\|packages/trading\|packages/scheduler" /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh/CLAUDE.md
```

命中的行文路径按 Task 6 同规则改（如 `packages/investment/src/index.ts` → `packages/tools/investment/src/index.ts`）。

---

### Task 8: 根目录垃圾清除

**Files:** Delete: `agent-dh/+v).join(n))`、`agent-dh/dist/`、`agent-dh/output/`、`.DS_Store`

- [ ] **Step 1: 先验证 dist/ output/ 无引用**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh
grep -rn "agent-dh/dist\|agent-dh/output\|'\./dist\|\"\./dist" package.json pnpm-workspace.yaml config/cordis.yml scripts/*.sh 2>/dev/null | grep -v node_modules   # 期望: 无输出
ls dist output   # 肉眼确认只是 8 月的 vite 遗留
```

- [ ] **Step 2: 删除**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh
git rm -q -- '+v).join(n))' 2>/dev/null || rm -f -- '+v).join(n))'
git rm -rq dist output 2>/dev/null || rm -rf dist output
rm -f .DS_Store
```

**不碰**：`CLEANUP-PLAN.md`、`MIGRATION-*.md`、`index.html`、`src/`、`public/`、`.env.backup`、根级 `cordis.yml`（均为并行会话在途产物或明确保留项）。

---

### Task 9: 原子提交

- [ ] **Step 1: 全量 add 并提交**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure
git add -A
git status --short | head -20   # 肉眼核对：全是 rename（R）+ 少量 modify（M）+ 少量 delete（D）
git commit -m "refactor(agent-dh): 目录骨架对齐 deepseek-harness——packages/{tools,web,client,runtime,core} 两级域（RFC 015，包名不变）"
```

---

### Task 10: worktree 内重建链接

- [ ] **Step 1: pnpm install（重写所有 node_modules 链接到新路径）**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh
pnpm install 2>&1 | tail -5
```

期望：`Done`。postinstall 会自动跑 build:clients。

- [ ] **Step 2: relink 体检+修复**

```bash
python3 scripts/relink-profile.py 2>&1 | tail -3
python3 scripts/relink-profile.py --check; echo "exit=$?"   # 期望: exit=0
```

- [ ] **Step 3: dsh-tools 单一拷贝不变式复验（09-21 事故回归）**

```bash
readlink node_modules/@deepseek-ai/dsh-tools node_modules/.pnpm/node_modules/@deepseek-ai/dsh-tools packages/tools/*/node_modules/@deepseek-ai/dsh-tools 2>/dev/null | sed 's|.*/.pnpm/||' | sort -u   # 期望: 只有 1 个 .pnpm 条目
grep -rc "TOOL_RUNTIME_SCHEDULER" packages/*/*/dist/*.mjs 2>/dev/null | grep -v ":0"   # 期望: 无输出
```

---

### Task 11: 重建带 dist 的包

- [ ] **Step 1: 重建 intelligence + pmboard（dist 里的 sourcemap 带旧绝对路径）**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh/packages/tools/intelligence && pnpm build 2>&1 | tail -2
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh/packages/web/dsh-pmboard && pnpm build 2>&1 | tail -3
```

pmboard 走完整 `pnpm build`（host + client + wrap + verify，上次事故教训：不许只建 host 半包）。
期望：verify-client-build 通过。

---

### Task 12: vitest 冒烟

- [ ] **Step 1: schema 冒烟**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh
npx vitest run tests/plugin-schema.smoke.test.ts 2>&1 | grep -E "Test Files|Tests "
```

期望：`Test Files  1 passed`、`Tests  20 passed`。

- [ ] **Step 2: 全量测试（区分基线失败）**

```bash
npx vitest run 2>&1 | tail -15
```

期望：无新增失败（对照 memory 里的基线失败清单；搬迁直接相关的 reqboard/m3/task-retry 测试必须全绿）。

---

### Task 13: 隔离实例启动验证（端口 13081，不碰 :13080）

- [ ] **Step 1: 从 worktree 起隔离实例**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/dsh-structure/agent-dh
./scripts/start.sh --port 13081 --no-open > /tmp/dsh-13081.log 2>&1 &
sleep 25
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:13081/   # 期望: 401
```

- [ ] **Step 2: 启动日志检查**

```bash
grep -iE "error|already registered|prepare|missing required" /tmp/dsh-13081.log | head -5   # 期望: 无输出
grep "genome" /tmp/dsh-13081.log   # 期望: [genome] loaded 行（插件装载成功的标志）
```

- [ ] **Step 3: 停掉隔离实例**

```bash
./scripts/stop.sh 13081 2>/dev/null || lsof -ti:13081 -sTCP:LISTEN | xargs kill
```

---

### Task 14: 合并回 main + 主工作区生效

- [ ] **Step 1: 临时 worktree 合并（不碰主工作区 git 写钩子）**

```bash
cd /Users/yunpeng/pi-investment
git worktree add .claude/worktrees/merge-015 main
cd .claude/worktrees/merge-015
git merge --no-ff feat/dsh-structure-alignment -m "merge: agent-dh 目录骨架对齐 deepseek-harness（RFC 015）"
git log --oneline -2   # 核对合并提交
```

- [ ] **Step 2: 主工作区前进到合并头**

```bash
cd /Users/yunpeng/pi-investment
git fetch .claude/worktrees/merge-015 main:main 2>/dev/null || git -C .claude/worktrees/merge-015 rev-parse HEAD
# 若 fetch 拒绝（当前分支检出中），改用：在主工作区 git pull --ff-only .claude/worktrees/merge-015 main
git status --short | head -3   # 期望: 干净（除本计划/RFC 已在分支内）
```

- [ ] **Step 3: 主工作区重建链接（:13080 运行时解析根在主工作区！）**

```bash
cd /Users/yunpeng/pi-investment/agent-dh
pnpm install 2>&1 | tail -3
python3 scripts/relink-profile.py 2>&1 | tail -2
python3 scripts/relink-profile.py --check; echo "exit=$?"   # 期望: 0
```

- [ ] **Step 4: 重启 :13080 并实况验证**

```bash
./scripts/stop.sh && ./scripts/start.sh --no-open &
sleep 25
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:13080/   # 期望: 401
```

随后 10 分钟内观察 `.dsh-data/sessions/` 最新会话落盘：`zstdcat <最新>/session.v3.jsonl.zstd | grep -c '"kind":"error"'` 期望为 0；或等下一个定时任务会话确认工具调用成功。

- [ ] **Step 5: 清理 worktree**

```bash
cd /Users/yunpeng/pi-investment
git worktree remove .claude/worktrees/dsh-structure
git worktree remove .claude/worktrees/merge-015
git branch -d feat/dsh-structure-alignment
```

---

## Self-Review 记录

- **Spec 覆盖**：RFC 的 30 包映射（Task 2-4）、workspace glob（Task 5）、引用点清单（Task 6-7，含执行时 grep 复核）、根垃圾处置（Task 8，在途文件不碰）、原子提交（Task 9）、relink 回潮（Task 10/14.3）、冒烟+重启验证（Task 12-14）、回滚（单提交 revert）。RFC 前置条件 = Task 0。
- **占位符**：无 TBD；所有命令可直接执行。
- **一致性**：包名/域名与 RFC 权威清单逐一核对一致；Task 6 的 tools 清单与 Task 2 的 17 个一致（genome 特判单独列出）。
