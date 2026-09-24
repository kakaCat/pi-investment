# t-9abb40 复核记录（父卡 t-6cfab3 / T-7「打零参绑定 patch」· 阶段 review）

- 复核时间：2026-09-24T23:28+0800
- 复核环境：node v22.23.2 · vitest 2.1.9（以 `npx vitest run` 运行 banner 为准）· darwin-arm64 · 工作目录 `agent-dh`
- 复核对象（接口 I-5 / FR-4）：`patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch`
  + 根 `package.json` 的 `pnpm.patchedDependencies` + `packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts`
- 复核方式：**只读复核**（不修改任何实现/补丁/测试），逐条比对设计文档与实物，并独立复现关键命令与运行时探针。
- 总裁决：**实现与设计的契约逐条一致，均「无偏离」**；另发现 1 处**设计文档符号引用不准**（M-1：文档级、无功能影响、不阻断）。

> 说明：本卡为 review 阶段，依据卡验收「对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据」，
> 下节对每条设计约定给出显式结论；另发现的问题在「偏离清单」单列并标注性质与是否阻断。

---

## 0. 设计基线（判定依据）

| 依据 | 位置 | 关键约定 |
|---|---|---|
| 需求 | `requirement.md`（FR-4） | 零参调用等价于传 `{}`，正常返回 |
| 架构 | `design/architecture.md:103` | 绑定工厂 `value: (args) => …` 改为 `value: (args = {}) => …`（**唯一改动**） |
| 架构 | `design/architecture.md:49,228,248` | 新增该 patch + 根 `package.json`；只加最小 patch、不改上游仓库；`pnpm install` 更新 lockfile |
| 接口 | `design/interfaces.md:18,127`（I-5 / E-9） | 输出与显式 `{}` 完全一致；零参由「拒绝」变「接受」；不再产生 `binding arguments must be lossless JSON` |
| 测试 | `design/test-cases.md:36,109`（TC-9） | 测试落点 `packages/web/dsh-pmboard/tests/zero-arg-binding.test.ts` |
| 任务 | `decomposition.md:116`（T-7 验收） | vitest 全绿且断言 `(args = {})`；run_code 零参 `tools.reqboard_status()` 正常返回无错误 |

## 1. 逐条对照（设计 → 实现 → 结论）

| # | 设计条目 | 实测实现 | 结论 |
|---|---|---|---|
| 1 | FR-4：零参等价 `{}` 并正常返回 | 绑定工厂缺省参数生效，零参调用返回与显式 `{}` 逐字符相同 | **无偏离**（依据：I-5 探针，`deepEqual=true`、键集合一致，见第 2 节） |
| 2 | architecture.md:103 唯一改动 `value: (args = {})` | patch 只有 1 个 hunk、1 行 `-`/1 行 `+`，且只碰 `lib/process.js` | **无偏离**（依据：patch 行统计 `+`=2/`-`=2 含文件头；hunk 仅 `@@ -952,7 +952,7 @@`，见第 3 节） |
| 3 | architecture.md:49 落点 = 新增 patch + 根 `package.json` | patch 文件存在；根 `package.json:338` 登记该键值 | **无偏离**（依据：`grep -n -A6 patchedDependencies package.json`） |
| 4 | architecture.md:228 只加最小 patch、不改上游仓库 | 改动只落在本仓 `patches/` + 根清单，无上游包源码提交 | **无偏离**（`git status` 未见上游包改动） |
| 5 | architecture.md:248 `pnpm install` 应用 patch 并更新 lockfile | `pnpm-lock.yaml` 增 patch 条目（hash/path）与全量 `patch_hash=ancxltpwmrosis3cqkonlvi6xu`、`patched: true` | **无偏离**（依据：`git diff -- pnpm-lock.yaml`） |
| 6 | I-5：零参与显式 `{}` 完全一致 | 运行时 A/B 探针 `JSON.stringify(A)===JSON.stringify(B)` → `true` | **无偏离**（见第 2 节） |
| 7 | I-5/E-9：不再产生绑定层旧错误 | 零参返回体不含 `binding arguments must be lossless JSON`；已安装产物含补丁后签名 | **无偏离**（探针 `bindingErrorInZero=false` + 第 3 节） |
| 8 | architecture.md:239 零参 → 缺省 `{}`、正常派发 | 行为与「处置」列一致 | **行为无偏离**；该行「检测方式」列符号名与本包实物不符 → 见 M-1 |
| 9 | test-cases.md:36/109（TC-9）落点与断言 | 测试文件存在；`npx vitest run tests/zero-arg-binding.test.ts` 4/4 绿 | **无偏离**（测试在被打补丁的同一绑定层用合成绑定验证；具体 `tools.reqboard_status()` 零参由本卡运行时探针覆盖，属口径细化） |
| 10 | T-7 验收① vitest 全绿 + 断言 `(args = {})` | 4 例全过（登记 / patch 文本 / 已安装产物 / 跨进程 wire 帧） | **无偏离**（见第 4 节） |
| 11 | T-7 验收② run_code 零参 `tools.reqboard_status()` 正常返回 | 本卡 `run_code` 内只调 `tools.reqboard_status()`（零参）→ 正常返回 | **无偏离**（见第 2 节） |
| 12 | 落点范围（patch / package.json / 测试文件，无越界） | git 变更 = 上述 3 项 + `pnpm-lock.yaml`（第 5 条设计已预期） | **无偏离**（无越界文件） |
| 13 | patch 命名/格式与既有先例一致（architecture.md:228「已有 2 个 patch 先例」） | 命名 `@scope__name@version.patch`，与既有 2 个 patch 同构 | **无偏离**（`ls patches/` 三份同构） |

## 2. 独立复现：接口 I-5 运行时探针（核心验收）

复核方式：在 `run_code` 内对**同一工具**发两次调用——A 零参、B 显式 `{}`——逐字符比较，并检查是否出现绑定层拒绝错误。

| 项 | 内容 |
|---|---|
| 请求样例 A | `await tools.reqboard_status()`（省略 args） |
| 请求样例 B | `await tools.reqboard_status({})` |
| 期望响应 | A 与 B 完全一致；不抛错；输出不含 `binding arguments must be lossless JSON` |
| 实际返回 | `zeroArgOk=true`；`deepEqual=true`；`bindingErrorInZero=false`；键集合 `board_link,bound,clause_receive_status,next_actions,note,open_count,open_requirements,unreceived_clauses,window_key` |
| 判定 | **一致 → 无偏离** |

实测输出（节选）：

```
zeroArgOk: true
deepEqual: true
bindingErrorInZero: false
zeroArgSnippet: {"window_key":"adc13f3d-4d00-4627-b4f1-cf5515c2fe83","bound":false,"open_count":0,...,"board_link":"/dashboard#pmboard"}
```

## 3. 独立复现：补丁链路与最小性

| 环节 | 命令 | 实际结果 |
|---|---|---|
| 登记 | `grep -n -A6 patchedDependencies package.json` | `338: "@deepseek-ai/dsh-ptc-runtime-node@0.1.6-alpha.2": "patches/@deepseek-ai__dsh-ptc-runtime-node@0.1.6-alpha.2.patch"` |
| 最小性 | `grep -n "^[+-][^+-]" <patch>` | 仅 `-value: (args) => {` / `+value: (args = {}) => {`；1 个 hunk |
| 已安装产物 | `grep -n "value: (args" node_modules/.pnpm/.../lib/process.js` | 提升层与虚拟店副本均命中 `955: value: (args = {}) => {`；两处均无未打补丁的 `value: (args) => {` |
| patch 可逆性 | `cd <包目录> && patch -p1 --dry-run -R -i <patch>` | `checking file lib/process.js`，退出码 `0`（已安装产物 == patch 后像） |
| lockfile | `git diff -- pnpm-lock.yaml` | 增 `hash/path` 条目 + 全量 `patch_hash=...` + `patched: true` |

## 4. 目标命令：绑定守护测试

```bash
cd packages/web/dsh-pmboard
npx vitest run tests/zero-arg-binding.test.ts
```

实测输出：

```
 RUN  v2.1.9 /Users/yunpeng/pi-investment/agent-dh/packages/web/dsh-pmboard
 ✓ tests/zero-arg-binding.test.ts (4 tests) 33ms
 Test Files  1 passed (1)
      Tests  4 passed (4)
```

- 退出码：`0`（全绿）——与 T-7 验收①一致。

## 5. 偏离清单

### 无实现偏离

除下述 M-1（文档级）外，T-7 / FR-4 / I-5 / TC-9 的全部约定与实现逐条一致，**实现层面无偏离**。

### M-1（设计文档级 · 非实现偏离 · 不阻断）

- **位置**：`design/architecture.md:239`「失败点 = 零参调用 | 检测方式 = 绑定层 `decodeWorkerJson(undefined)` | 处置 = 缺省 `{}`」。
- **实测**：在**被补丁包** `@deepseek-ai/dsh-ptc-runtime-node` 全包内 grep `decodeWorkerJson` → **无该符号**；
  该符号只存在于**另一个运行时包** `@deepseek-ai/dsh-code-runtime-worker-thread`（`lib/index.js` 等）。
  被补丁包的真实拒绝点在同包 `lib/process.js`：`snapshotPtcJsonValue(args)`（958 行）→ `detached === void 0`
  → `bindingFailure(errorClass, name, "binding arguments must be lossless JSON")`（962 行）。
- **判定**：设计文档符号引用不准（疑似与其他 runtime 包混淆）；但**同行「处置 = 缺省 `{}`」与实现一致**，
  且 `architecture.md:103` 已给出准确签名、`interfaces.md` E-9 的错误串亦被实物佐证 ——
  **无功能影响，不阻断，不作为实现返工项**。
- **建议（后续文档维护，可不在本卡执行）**：将该行「检测方式」改为 `snapshotPtcJsonValue(undefined)`。

## 6. 复核结论

1. **无实现偏离**：FR-4 契约（零参等价 `{}`、正常返回、不再产生旧错误）与 T-7 验收（vitest 4/4 + 运行时零参探针）均实测成立；补丁严格为「一行一文件」的最小改动。
2. 补丁链路四层（根清单登记 / patch 文件 / 已安装产物 / 跨进程 wire 帧）均可独立复现；`patch -R --dry-run` 退出 0 证明已安装产物恰为 patch 后像。
3. 唯一发现是 **M-1（设计文档符号名不准，文档级、无功能影响）**，不构成实现偏离，不阻断父卡收尾。
4. 本卡为 review 阶段，只读复核 + 落本记录；**未修改任何实现、补丁或测试源码**，本轮新增产物仅本文件。
