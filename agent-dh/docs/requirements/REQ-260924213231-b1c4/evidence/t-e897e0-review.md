# t-e897e0 复核记录（父卡 t-216224 / T-8「设计提示词写明登记命令」· 阶段 review）

- 复核时间：2026-09-25T≈00:58+0800（本轮执行内）
- 复核环境：node v22.23.2 · vitest 2.1.9（darwin-arm64）· HEAD `9e5ebf60`
- 复核对象（T-8 计划落点，仅 4 个文件）：
  - `packages/web/dsh-pmboard/src/domain/prompt/fragments/design/light/overrides.md`（覆盖 1 改写为登记命令）
  - `packages/web/dsh-pmboard/src/domain/prompt/fragments/design/heavy/overrides.md`（覆盖 1 并入登记命令+触发者+不要猜 kind）
  - `packages/web/dsh-pmboard/src/domain/prompt/generated/fragments.ts`（重跑生成器后的产物）
  - `packages/web/dsh-pmboard/tests/design-prompt-registration.test.ts`（新增，TC-10 / TC-17）
- 设计依据（比对基线）：`requirement.md` FR-5（L101-104）/ §10 验收汇总 FR-5（L169）、`design/test-cases.md` TC-10（L37）/ TC-17（L44）/ 落点表（L110）、`decomposition.md` T-8（L117）/ 覆盖对照（L156）、任务卡 `tasks/t-216224.md` 验收标准
- 复核方式：读 `git diff` 逐点比对设计契约 + 独立复跑父卡验收命令 + 用 tsx 直接解析 `resolveStagePrompt` 读实际注入文本（不采信上游自述）

---

## 1. 逐条复核结论（设计与实现）

| 编号 | 设计点（出处） | 实现 | 结论 |
|---|---|---|---|
| R1 | 覆盖条目 1 写明登记命令 `reqboard_submit(kind=design)`（requirement.md FR-5 L103 / decomposition.md T-8 L117 / TC-10 L37） | light/overrides.md:3-6、heavy/overrides.md:5-11 均以覆盖 1 承载该命令；生成产物 fragments.ts:119/:127 与源 .md 逐字一致 | **无偏离**。依据：两覆盖条目原文；`check-prompt-fragments.mjs` 退出 0；tsx 实测 `resolveStagePrompt({stage:'design',difficulty:'light'/'heavy'}).text.includes('reqboard_submit(kind=design)')` 均为 true。 |
| R2 | 写明**触发者**（提交者=本窗口 agent 自己，不是等人/等目录）（FR-5 L103 / 事故根因 requirement.md §2.1） | light:"由**本窗口 agent 自己**调"；heavy:"由**本窗口 agent 自己**调"、"登记不是自动发生的（…也不是等人打开看板）" | **无偏离**。依据：light/overrides.md:3-4、heavy/overrides.md:5-7；test L37 断言 `text.toContain('agent 自己')` 绿。 |
| R3 | 明说「**不要猜 kind**」，且点名 `requirement/plan/verification/archive` 属别的阶段（FR-5 L102「没说不要尝试 reqboard_submit(kind=design)…诱发 3 次无效尝试」） | light:"**不要猜 kind**：设计文档只认 `design`，`requirement/plan/verification/archive` 传错必被拒"；heavy:同义且更详细（"传错会被工具枚举挡下""也别因为被拦就盲试别的 kind"） | **无偏离**。依据：light/overrides.md:5-6、heavy/overrides.md:8-10；test L38/L53 断言「不要猜 kind」、L71-80 逐 kind 点名断言，全绿。 |
| R4 | light 与 heavy 两档、且六种类型档路由壳都要覆盖到（TC-10 L37 / test 自设） | 两覆盖条目 priority=floor、difficulty=light/heavy、category=`*`，生成产物里每个 `design/{light,heavy}/<category>` 的 include 均含对应 overrides | **无偏离**。依据：fragments.ts:119/:127 与各 category 行 include；test L33-69（含 6×2 路由壳断言）绿。 |
| R5 | 「不含『落盘即产物』旧断言」（T-8 验收 L16 / TC-10 L37） | 字面旧串 `落盘即产物`、`目录自动发现登记` 已从两 overrides 移除（grep 全 prompt 目录 0 命中）；**但** design 主分片 `light.md:9-11` 与 `heavy.md:12-13` 仍逐字保留同义异形断言「落盘后会被自动登记为 design 产物…触发自动登记」 | **部分偏离**（见 §2 D-1）。字面验收门通过，但注入文本仍同时出现「登记不是自动发生的」与「落盘后会被自动登记」，light 档未被覆盖条目显式否定。 |
| R6 | 重跑生成器刷新 `generated/fragments.ts`（T-8 实施方案 / RISK-6） | 生成器重跑：产物 diff 仅 2 行（design/heavy/overrides、design/light/overrides），与源 .md 逐字节一致 | **无偏离**。依据：`check-prompt-fragments.mjs` 输出 OK 退出 0；`git diff --stat` = 3 files / 4 insertions / 4 deletions（含 fragments.ts 2 行）。 |
| R7 | 新增 `tests/design-prompt-registration.test.ts`；TC-10 + TC-17；父卡验收命令全绿（T-8 验收 L16 / TC-10 L37 / TC-17 L44） | 新增文件 112 行，含 TC-10（8 例：两档×命令/无旧断言/分片承载 + 路由壳 + kind 点名）与 TC-17（2 例：depends_on 表头仍被拒 / 散文提及放行） | **无偏离**。依据：独立复跑 `vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts` → 2 文件 25 用例全绿（见 §3.1）。 |
| R8 | TC-17 故障注入：提示词只改文本，G2 拆分内容硬门禁不得放宽（TC-17 L44） | test L97-111 直接调 `checkDesignDecompositionGate`：含 `depends_on` 表头 → `design_contains_decomposition`；散文提及 → 放行 | **无偏离**。依据：test 两例均通过；被测 `design-gates.ts` 本卡未改（不在 T-8 落点）。 |
| R9 | light 档旧版本回落说明（FR-5 L103「若跑在没有登记入口的版本上，明说『落盘后需打开看板详情页触发登记』」） | heavy 覆盖条目末尾写明旧版本回落句；**light 覆盖条目未写旧版本回落**（仅 design/light.md:10-11 保留看板触发句，但挂在「会被自动登记」的措辞下） | **观察项 O-1**（见 §2）：两档不对称；light 的回落句存在但表述相反，不阻塞（TC/T-8 未要求该句）。 |
| R10 | 范围锁定：只动计划列出的 4 个文件（T-8 实施方案 L19 / RISK-3 文件冲突） | `git status --short` 在 prompt 目录仅 3 改 + 1 新增；无越界文件 | **无偏离**。依据：`git status --short -- src/domain/prompt tests/design-prompt-registration.test.ts`（工作区其他改动属并行卡，与本卡无关）。 |

---

## 2. 偏离与观察项

- **D-1（部分偏离，非阻塞但建议处理）：旧断言只删了字面串，同义断言仍在注入文本里且 light 档未被否定。**
  - 事实：用 tsx 直接解析实际注入文本，两档均为
    `cmd=true trigger=true noGuess=true staleAutoReg=true negation=true` —— 即同一段注入里**既**有新覆盖条目「登记不是自动发生的」**又**有主分片「落盘后会被自动登记为 design 产物」。
  - 后果：heavy 档的覆盖 1 已显式否定（heavy/overrides.md:5-6「上文『落盘后自动登记』在此不成立」），冲突可被读解；**light 档的覆盖 1 没有这句否定**，且 `design/light.md` 是**本仓可改**文件（非 vendor 镜像）——事故根因（提示词宣称登记自动发生）在 light 档只是被并列而非被纠正。
  - 为何测试没拦住：`tests/design-prompt-registration.test.ts:24` 的 `STALE_CLAIMS = ['落盘即产物', '目录自动发现登记']` 只做**字面**匹配，而主分片用的是同义异形串「落盘后会被自动登记」，故 10 例全绿却漏检。
  - 为何**不判本卡失败**：T-8 验收（tasks/t-216224.md:16）与 TC-10 的措辞是「不含『落盘即产物』旧断言」，字面门已过；heavy.md 受 `check-prompt-fragments.mjs` 的 vendor 逐字节约束**不可改**。
  - 建议（供父卡/返工卡取舍）：① 把 `design/light.md:9-11` 的「落盘后会被自动登记…」改为「**不会**自动登记，落盘后需本窗口调 `reqboard_submit(kind=design)`」；② light 覆盖 1 补一句与 heavy 同款的旧版本回落；③ 把 `STALE_CLAIMS` 扩为含 `自动登记`（正则/子串）以锁死，避免再漂移。
- **O-1（文档/一致性观察）**：见 R9——light 覆盖条目缺旧版本回落句，light.md 的看板回落句被包在「会被自动登记」语义里；与 FR-5 括号句不完全对齐，改动极小。
- **O-2（实现范围观察，非偏离）**：light/overrides.md 为把登记放进「覆盖 1」，把原覆盖 1/2（serves 标注 + 语言强度表）重排为覆盖 2/3，并把原语言强度表格压成散文。语义保留、无契约要求，属可接受；仅提示 baseline 快照随之更新（已更新，见 §3.3）。

---

## 3. 独立复核证据（命令 + 输出摘要）

### 3.1 父卡验收命令（复跑）

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/design-prompt-registration.test.ts tests/prompt-baseline.test.ts
```

实际输出：

```
 ✓ tests/prompt-baseline.test.ts (15 tests) 5ms
 ✓ tests/design-prompt-registration.test.ts (10 tests) 3ms

 Test Files  2 passed (2)
      Tests  25 passed (25)
```

判定：**2/2 文件、25/25 用例通过，退出码 0** —— 与 T-8 验收期望一致。

### 3.2 生成器同步门禁（复跑）

```bash
node packages/web/dsh-pmboard/scripts/check-prompt-fragments.mjs
```

实际输出：

```
[check-prompt-fragments] OK: src/domain/prompt/generated/fragments.ts 与 fragments/**.md 一致；heavy.md ↔ vendor 原文逐字节一致
EXIT=0
```

判定：产物与源 .md 逐字节一致、heavy.md 与 vendor 镜像未漂移，退出码 0。

### 3.3 diff 性质确认

```bash
git -C /Users/yunpeng/pi-investment diff --stat -- agent-dh/packages/web/dsh-pmboard/src/domain/prompt
#  heavy/overrides.md | 12 +++++++++---
#  light/overrides.md  | 24 ++++++++--------------
#  generated/fragments.ts | 4 ++--
#  3 files changed, 20 insertions(+), 20 deletions(-)
```

- `generated/fragments.ts` 的 4 行 diff **全部**落在 `design/{heavy,light}/overrides` 两条，无其他分片被误改。
- `tests/fixtures/stage-prompts-baseline-p1.json` 同步更新 2 行（design/light、design/heavy 基线），与 `prompt-baseline.test.ts` 15 例全绿一致。
- `tests/design-prompt-registration.test.ts` 为新增（未跟踪）。

### 3.4 注入文本直读（tsx，绕过测试自述）

```bash
npx tsx -e "import('…/src/domain/prompt/index.ts').then(m=>{for(const d of ['light','heavy']){const t=m.resolveStagePrompt({stage:'design',difficulty:d}).text;
console.log('['+d+'] ids='+m.resolveStagePrompt({stage:'design',difficulty:d}).fragmentIds.filter(x=>x.startsWith('design/'+d)).join(',')
+' cmd='+t.includes('reqboard_submit(kind=design)')+' trigger='+t.includes('agent 自己')+' noGuess='+t.includes('不要猜 kind')
+' staleAutoReg='+t.includes('落盘后会被自动登记为 design 产物')+' negation='+t.includes('登记不是自动发生的'))}})"
```

实际输出：

```
[light] ids=design/light/feature,design/light,design/light/overrides cmd=true trigger=true noGuess=true staleAutoReg=true negation=true
[heavy] ids=design/heavy/feature,design/heavy,design/heavy/overrides cmd=true trigger=true noGuess=true staleAutoReg=true negation=true
```

判定：命令/触发者/不要猜 kind 三要素在**实际注入文本**中成立（R1-R4 无偏离）；同时暴露 D-1——两档注入都仍含「落盘后会被自动登记为 design 产物」。

### 3.5 旧字面串清扫

```bash
grep -rn "落盘即产物\|目录自动发现登记" packages/web/dsh-pmboard/src/domain/prompt/
#  NO exact stale strings
```

判定：旧字面串已在全 prompt 目录清零；同义异形串残留见 D-1（由 3.4 直读暴露）。

---

## 4. 结论

1. T-8 相对 `requirement.md` FR-5、`design/test-cases.md` TC-10/TC-17、`decomposition.md` T-8 与任务卡验收：**R1-R4、R6-R8、R10 逐条无偏离并给出依据**；R7 父卡验收命令独立复跑 25/25 全绿；R6 生成器门禁退出 0。
2. **R5 为部分偏离 D-1**：T-8 的字面验收购过（`落盘即产物` 清零），但注入文本仍含同义异形旧断言「落盘后会被自动登记为 design 产物」，且 light 档未像 heavy 那样被覆盖条目显式否定；现行测试的 `STALE_CLAIMS` 只做字面匹配，构成漏检。属**非阻塞**（heavy.md 受 vendor 镜像约束不可改；light 档为可改残留），建议按 §2 D-1 三条之一跟进。
3. 观察项 O-1（light 缺旧版本回落句）、O-2（cover 条目重排/表格压散文，baseline 已同步）均无行为影响，**不阻塞**。
4. **复核结论：通过（带 1 项非阻塞待跟进 D-1）**——T-8 可进入收尾；D-1 是否返工由父卡/人工裁决。
