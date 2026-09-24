# t-2c7e2e 测试记录（父卡 t-216224 / T-8「设计提示词写明登记命令」· 阶段 test）

- 测试时间：2026-09-25T01:00+0800（本轮执行内）
- 测试环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· 仓库工作目录 `agent-dh`，测试工作目录 `packages/web/dsh-pmboard`；HEAD = `9e5ebf60`（branch `main`）
- 被测对象（FR-5；实现改动为工作区未提交状态，本卡只读不改）：
  - **覆盖条目 1** —— `packages/web/dsh-pmboard/src/domain/prompt/fragments/design/light/overrides.md`（工作区修改 +9/−15）与 `.../design/heavy/overrides.md`（工作区修改 +9/−3）：写明登记命令 `reqboard_submit(kind=design)` + 触发者「本窗口 agent 自己」+「不要猜 kind」（点名 `requirement/plan/verification/archive` 属别的阶段产物）。
  - **构建期产物** —— `packages/web/dsh-pmboard/src/domain/prompt/generated/fragments.ts`（工作区修改 +2/−2）：重跑生成器后的内联分片（`design/heavy/overrides` 在 L119、`design/light/overrides` 在 L127）。
  - **P1 基线** —— `packages/web/dsh-pmboard/tests/fixtures/stage-prompts-baseline-p1.json`（工作区修改 +2/−2）：design 两档快照随文本同步。
  - 用例文件：`packages/web/dsh-pmboard/tests/design-prompt-registration.test.ts`（新增，untracked，112 行 / 10 例；头部第 2 行带 `serves: FR-5`）。
- 测试结论：**目标命令全绿** —— ① 源/产物同步门禁 `node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs` → **exit 0**；② `npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts` → **2 files / 25 tests 通过，exit 0**。父卡三条业务口径（design/light 与 heavy 文本含 `reqboard_submit(kind=design)`、含触发者、不含「落盘即产物」旧断言）均由用例逐条锁定并复跑通过。验收标准「目标命令输出全绿」达成。

---

## 1. 目标命令 ①：源/产物同步门禁（生成器刷新核验）

```bash
node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs
```

实际输出：

```
[check-prompt-fragments] OK: src/domain/prompt/generated/fragments.ts 与 fragments/**.md 一致；heavy.md ↔ vendor 原文逐字节一致
```

- 退出码：**0**（全绿）
- 判定：`generated/fragments.ts` 与 `fragments/**.md` **逐字节一致** —— 改 overrides 后确实重跑了生成器，未出现「只改源/只改产物」的漂移。

## 2. 目标命令 ②：设计提示词登记口径 + P1 基线回归

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts --reporter=verbose
```

实际输出（逐例）：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard

 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > P1 基线含 6 节点 × 2 难度 = 12 键
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > brainstorming/light 与 P1 基线逐字一致（含空白与换行）
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > brainstorming/heavy 与 P1 基线逐字一致（含空白与换行）
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > design/light 与 P1 基线逐字一致（含空白与换行）
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > design/heavy 与 P1 基线逐字一致（含空白与换行）
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > decomposing/light 与 P1 基线逐字一致（含空白与换行）
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > decomposing/heavy 与 P1 基线逐字一致（含空白与换行）
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > implementing/light 与 P1 基线逐字一致（含空白与换行）
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > implementing/heavy 与 P1 基线逐字一致（含空白与换行）
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > accepting/light 与 P1 基线逐字一致（含空白与换行）
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > accepting/heavy 与 P1 基线逐字一致（含空白与换行）
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > archived/light 与 P1 基线逐字一致（含空白与换行）
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > archived/heavy 与 P1 基线逐字一致（含空白与换行）
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > 六节点 light 与 heavy 解析出的文本彼此不同（难度轴已生效）
 ✓ tests/prompt-baseline.test.ts > P1 基线：六节点 light/heavy 解析结果逐字一致 > P0 历史快照仍在且未被覆盖（6 个 stage key，字样为 P0 常量直取文本）
 ✓ tests/design-prompt-registration.test.ts > TC-10 设计提示词写明登记命令与触发者（design/light 与 design/heavy） > design/light 注入文本含 reqboard_submit(kind=design)、触发者与「不要猜 kind」
 ✓ tests/design-prompt-registration.test.ts > TC-10 设计提示词写明登记命令与触发者（design/light 与 design/heavy） > design/light 注入文本不含旧断言（落盘即产物 / 目录自动发现登记）
 ✓ tests/design-prompt-registration.test.ts > TC-10 设计提示词写明登记命令与触发者（design/light 与 design/heavy） > design/light/overrides 分片是命令的承载处（防只改正文/只改注释）
 ✓ tests/design-prompt-registration.test.ts > TC-10 设计提示词写明登记命令与触发者（design/light 与 design/heavy） > design/heavy 注入文本含 reqboard_submit(kind=design)、触发者与「不要猜 kind」
 ✓ tests/design-prompt-registration.test.ts > TC-10 设计提示词写明登记命令与触发者（design/light 与 design/heavy） > design/heavy 注入文本不含旧断言（落盘即产物 / 目录自动发现登记）
 ✓ tests/design-prompt-registration.test.ts > TC-10 设计提示词写明登记命令与触发者（design/light 与 design/heavy） > design/heavy/overrides 分片是命令的承载处（防只改正文/只改注释）
 ✓ tests/design-prompt-registration.test.ts > TC-10 设计提示词写明登记命令与触发者（design/light 与 design/heavy） > 六种类型档 × 两档难度的路由壳都带上登记命令（不是只在缺省档生效）
 ✓ tests/design-prompt-registration.test.ts > TC-10 设计提示词写明登记命令与触发者（design/light 与 design/heavy） > 登记命令是 reqboard_submit 的 design 种类（不是别的阶段种类）
 ✓ tests/design-prompt-registration.test.ts > TC-17 故障注入回归：提示词改动不放松拆分内容硬门禁 > design/*.md 含 depends_on 表头 → 仍被 design_contains_decomposition 拒
 ✓ tests/design-prompt-registration.test.ts > TC-17 故障注入回归：提示词改动不放松拆分内容硬门禁 > 干净设计文档（散文提及 depends_on）→ 放行（门禁不误伤）

 Test Files  2 passed (2)
      Tests  25 passed (25)
   Start at  01:00:06
   Duration  299ms (transform 99ms, setup 0ms, collect 183ms, tests 8ms, environment 0ms, prepare 78ms)
```

- 退出码：**0**（全绿）
- 判定：与父卡 t-216224 验收命令「`npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts` 全绿」一致。

## 3. 父卡业务口径逐条核对

| 父卡验收口径 | 对应用例 / 源码证据 | 结果 |
|---|---|---|
| design/light 文本含 `reqboard_submit(kind=design)` | 用例「design/light 注入文本含 …」+「…/overrides 分片是命令的承载处」；源码 `light/overrides.md:3-4`；产物 `generated/fragments.ts:127` | ✅ |
| design/heavy 文本含 `reqboard_submit(kind=design)` | 用例「design/heavy 注入文本含 …」+「…/overrides 分片是命令的承载处」；源码 `heavy/overrides.md:6-7`；产物 `generated/fragments.ts:119` | ✅ |
| 不含「落盘即产物」旧断言 | 两档各一条 `not.toContain`；全 prompt 源树 grep `落盘即产物\|目录自动发现登记` → **0 命中** | ✅ |
| 触发者写明「本窗口 agent 自己」 | 用例断言 `toContain('agent 自己')`；`light:4`、`heavy:6` | ✅ |
| 「不要猜 kind」+ 四类别阶段产物点名 | 用例「登记命令是 reqboard_submit 的 design 种类」逐一点名 `requirement/plan/verification/archive` | ✅ |

补充锁定（同批用例，非父卡必答项）：六种类型档 × 两档难度的路由壳都带 `design/<difficulty>/overrides` 分片与登记命令（不是只在缺省档生效）；TC-17 故障注入回归 —— 本次只改提示词文本，`design_contains_decomposition` 拆分内容硬门禁不放宽（含 `depends_on` 表头仍拒、散文提及仍放行）。

## 4. 补充回归（相邻提示词门禁，非父卡验收命令）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/prompt-baseline.test.ts tests/prompt-gates.test.ts tests/stage-prompts.test.ts
```

实际输出：

```
 ✓ tests/prompt-baseline.test.ts (15 tests) 5ms
 ✓ tests/prompt-gates.test.ts (13 tests) 50ms
 ✓ tests/stage-prompts.test.ts (37 tests) 10ms

 Test Files  3 passed (3)
      Tests  65 passed (65)
```

- 退出码：**0**。`prompt-gates.test.ts`（分片门禁/生成产物存在性）、`stage-prompts.test.ts`（六节点取词与结构）均未因本次提示词文本变更而回归。

## 5. 改动归属（本卡未改任何源码/用例）

```bash
git status --porcelain -- <T-8 四文件> <本卡用例>
git diff --numstat  -- <T-8 四文件>
```

实际输出：

```
 M agent-dh/packages/web/dsh-pmboard/src/domain/prompt/fragments/design/heavy/overrides.md
 M agent-dh/packages/web/dsh-pmboard/src/domain/prompt/fragments/design/light/overrides.md
 M agent-dh/packages/web/dsh-pmboard/src/domain/prompt/generated/fragments.ts
 M agent-dh/packages/web/dsh-pmboard/tests/fixtures/stage-prompts-baseline-p1.json
?? agent-dh/packages/web/dsh-pmboard/tests/design-prompt-registration.test.ts

9	3	agent-dh/packages/web/dsh-pmboard/src/domain/prompt/fragments/design/heavy/overrides.md
9	15	agent-dh/packages/web/dsh-pmboard/src/domain/prompt/fragments/design/light/overrides.md
2	2	agent-dh/packages/web/dsh-pmboard/src/domain/prompt/generated/fragments.ts
2	2	agent-dh/packages/web/dsh-pmboard/tests/fixtures/stage-prompts-baseline-p1.json
```

- 以上 4 处改动 + 1 处新增用例均为**父卡 t-216224（T-8，doc 阶段）的待提交工作区改动**；本卡（test 阶段）**只读不改**，本轮新增产物仅本证据文件 `docs/requirements/REQ-260924213231-b1c4/evidence/t-2c7e2e-test.md`。
- HEAD = `9e5ebf60`（branch `main`），与上游 T-8 联调记录 t-e80e8b / 复核记录 t-e897e0 一致。

## 6. 测试结论

1. 目标命令 ① `node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs`：**exit 0** —— 源与产物逐字节一致，生成器已刷新。
2. 目标命令 ② `npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts`：**2 files / 25 tests 全绿，exit 0** —— 验收标准「目标命令输出全绿」达成。
3. 父卡三条业务口径（含 `reqboard_submit(kind=design)` / 不含「落盘即产物」旧断言 / 含触发者与「不要猜 kind」）均由用例逐条锁定且通过。
4. 补充回归 `prompt-baseline + prompt-gates + stage-prompts` **65/65 绿**，相邻提示词门禁无回归。
5. 本卡为 test 阶段，只执行上述命令并落本记录；未修改任何实现、分片、产物或测试源码。
