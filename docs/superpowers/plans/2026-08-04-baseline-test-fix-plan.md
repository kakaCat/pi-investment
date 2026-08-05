# 基线失败测试分批修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 清零 2026-07-28 记录的预存在测试失败（jest 36 套件 + pytest collection error 22 文件），恢复"全量测试红=真回归"的信号价值。

**Architecture:** 按根因分 6 批，每批独立 worktree、独立合并：① TS 编译级速修 + 1 个生产潜伏 bug；② pytest collection error（stale import/缺依赖/marker）；③ jest 模块不存在类（删过时测试 + 修 mock 路径/契约）；④ jest vitest/ESM 类；⑤ jest 断言漂移类（逐个判断新旧行为对错）；⑥ evolution-service 网络 mock 化。

**Tech Stack:** agent-ts（jest ESM，必须 `npm test`）、quantsys-v2（pytest，venv，自动切 quant_test 库）

**根因分类依据**（2026-08-04 实测，32 jest 套件 + pytest 全量调查）：

| 类 | 数量 | 根因 |
|---|---|---|
| A 网络依赖 | 1 | evolution-service 零 mock 直连 5001 |
| B 模块/编译 | 13+3(P0) | 模块被删/改名、mock 路径错、契约漂移 |
| C vitest/ESM | 8 | 6 个测试 `import {vi} from 'vitest'`；1 个 ESM jest.mock 不提升+挂住 |
| D 断言漂移 | 10 | 文案/契约/行为变更，测试没跟上（逐个判断对错） |
| pytest | 22 文件 | stale import 14、缺依赖 5、asyncio marker 3；另有评分断言漂移 5 |

**通用规则：**
- 每批一个 worktree（`git worktree` 经 EnterWorktree），合并用 update-ref+cp 流程（update-ref 前必须重新核对 main 基点）
- agent-ts 测试必须 `npm test -- <path>`（裸 npx jest 误报 TS1378）
- 每步：跑失败 → 修 → 跑过 → commit
- 删测试文件前必须确认被测源码已不存在（`ls` 验证），并在 commit message 写明依据

---

## Batch 1：TS 编译级速修 + Python 生产潜伏 bug

**预估：** 1 小时内。**风险：** 极低（全是机械修复）。

### Task 1.1: experience-write-tool.test.ts 的 content0 未定义

**Files:**
- Modify: `agent-ts/src/infrastructure/tools/agent/experience-write-tool.test.ts:163`

**根因：** 第 148 行的测试把结果存进 `result`，但第 163 行直接用 `content0`（只在第 89 行的另一个测试里定义过），TS2304。

- [x] **Step 1: 复现失败**

Run: `cd agent-ts && npm test -- src/infrastructure/tools/agent/experience-write-tool.test.ts 2>&1 | grep "error TS"`
Expected: `TS2304: Cannot find name 'content0'`（163 行）

- [x] **Step 2: 修复——在第 163 行前补上提取（仿照第 89-91 行的写法）**

找到第 162-163 行：

```typescript
      const text = content0.text;
      const data = JSON.parse(text);
```

改为：

```typescript
      const content0 = result.content[0];
      if (!content0 || !("text" in content0)) {
        throw new Error("unexpected tool result shape");
      }
      const text = content0.text;
      const data = JSON.parse(text);
```

- [x] **Step 3: 验证通过**

Run: `npm test -- src/infrastructure/tools/agent/experience-write-tool.test.ts`
Expected: PASS（套件下所有测试）

- [x] **Step 4: Commit**

```bash
git add agent-ts/src/infrastructure/tools/agent/experience-write-tool.test.ts
git commit -m "fix(test): experience-write-tool 第163行 content0 未定义——补提取（TS2304）"
```

### Task 1.2: session-memory-saver.test.ts mock 路径少一级 agent/

**Files:**
- Modify: `agent-ts/src/services/intelligence/session-memory-saver.test.ts:44`

**根因：** 被测文件实际从 `../../infrastructure/tools/agent/memory-tool.js` import（session-memory-saver.ts:8），测试却 mock `../../infrastructure/tools/memory-tool.js`（缺 `/agent`），模块解析失败。

- [x] **Step 1: 复现失败**

Run: `cd agent-ts && npm test -- src/services/intelligence/session-memory-saver.test.ts 2>&1 | grep "Could not locate"`
Expected: `Could not locate module ../../infrastructure/tools/memory-tool.js`

- [x] **Step 2: 修复 mock 路径**

第 44 行：

```typescript
jest.unstable_mockModule("../../infrastructure/tools/memory-tool.js", () => ({
```

改为：

```typescript
jest.unstable_mockModule("../../infrastructure/tools/agent/memory-tool.js", () => ({
```

- [x] **Step 3: 验证通过**

Run: `npm test -- src/services/intelligence/session-memory-saver.test.ts`
Expected: PASS。若仍有失败，检查 mock 的导出形状（`memoryWriteTool`/`memorySearchTool`）与被测文件使用方式是否一致，按报错对齐。

- [x] **Step 4: Commit**

```bash
git add agent-ts/src/services/intelligence/session-memory-saver.test.ts
git commit -m "fix(test): session-memory-saver mock 路径补 /agent 一级——对齐真实 import"
```

### Task 1.3: fx-rate-service.test.ts jest.fn 类型推断 never

**Files:**
- Modify: `agent-ts/src/services/fx-rate-service.test.ts:11-12`

**根因：** @jest/globals 严格类型下 `jest.fn()` 推断为 `never`，`mockResolvedValue(null as any)` 报 TS2345。

- [x] **Step 1: 复现失败**

Run: `cd agent-ts && npm test -- src/services/fx-rate-service.test.ts 2>&1 | grep "error TS"`
Expected: 2 处 `TS2345: Argument of type 'any' is not assignable to parameter of type 'never'`

- [x] **Step 2: 修复——用实现体替代链式 mock（类型自然推断）**

第 10-13 行：

```typescript
    getInstance: jest.fn(() => ({
      get: jest.fn().mockResolvedValue(null as any),
      set: jest.fn().mockResolvedValue(undefined as any),
    })),
```

改为：

```typescript
    getInstance: jest.fn(() => ({
      get: jest.fn(async () => null),
      set: jest.fn(async () => undefined),
    })),
```

- [x] **Step 3: 验证通过**

Run: `npm test -- src/services/fx-rate-service.test.ts`
Expected: PASS

- [x] **Step 4: Commit**

```bash
git add agent-ts/src/services/fx-rate-service.test.ts
git commit -m "fix(test): fx-rate-service jest.fn 链式 mock 改实现体——消 TS2345"
```

### Task 1.4: 【生产 bug】experience_accumulator.py stale import

**Files:**
- Modify: `quantsys-v2/application/services/experience_accumulator.py:14`
- Test: `quantsys-v2/tests/services/test_strategy_weight_adjuster.py`

**根因：** ORM 重构把 `StrategyPerformanceRepository` 改名为 `StrategyPerformanceORMRepository`，`adapters/outbound/repositories/__init__.py` 只导出新名。**生产代码** experience_accumulator.py:14 仍 import 旧名——实测 `import experience_accumulator` 直接 ImportError（潜伏 bug，路径被触发即 500）。

- [x] **Step 1: 复现**

Run: `cd quantsys-v2 && source venv/bin/activate && python -c "import application.services.experience_accumulator"`
Expected: `ImportError: cannot import name 'StrategyPerformanceRepository'`

- [x] **Step 2: 修复 import**

第 14 行：

```python
from adapters.outbound.repositories import StrategyPerformanceRepository
```

改为：

```python
from adapters.outbound.repositories import StrategyPerformanceORMRepository as StrategyPerformanceRepository
```

（用 `as` 别名保留模块内所有引用点不动；若想彻底，全局替换类名引用为新名亦可，二选一，别混用。）

- [x] **Step 3: 验证 import 恢复 + 同根因测试转绿**

Run: `python -c "import application.services.experience_accumulator" && echo OK`
Run: `python -m pytest tests/services/test_strategy_weight_adjuster.py --no-header -q`
Expected: import OK；weight_adjuster 的 `test_get_weight_dynamic_mode` / `test_get_weight_fallback_on_error` 若也 import 旧名则同法修（该测试文件 import 旧名是同一改名事故）。最终 5 passed。

- [x] **Step 4: Commit**

```bash
git add quantsys-v2/application/services/experience_accumulator.py quantsys-v2/tests/services/test_strategy_weight_adjuster.py
git commit -m "fix: experience_accumulator stale import（ORM 改名遗留，import 即 ImportError 潜伏 bug）+ weight_adjuster 测试同步"
```

### Task 1.5: Batch 1 收尾验证

- [x] 跑 4 个修复目标套件全绿后，全量 jest 失败套件数应从 36 降到 ~33：`npm test 2>&1 | grep -E "^(FAIL|Test Suites:)"`（FAIL 清单中不得再出现本批 3 个文件）
- [x] pytest：`python -m pytest tests/services/test_strategy_weight_adjuster.py tests/test_multi_account_domain.py --no-header -q` 全绿
- [x] 合并回 main（update-ref 前核对 main 基点）并推送

---

## Batch 2：pytest collection error 清零（22 文件）

**预估：** 半天。**风险：** 低（机械替换 + 装包）。

### Task 2.1: 安装 pytest-asyncio（一石三鸟：消 3 文件错误）

**Files:**
- Modify: `quantsys-v2/requirements.txt`

**根因：** pytest.ini 有 `--strict-markers` 但未注册 asyncio marker 且未装 pytest-asyncio。装插件后自动注册 marker，同时消 `No module named 'pytest_asyncio'`——覆盖 test_async_kline_repository、daemon/test_data_handlers、test_registry 共 3 文件。

- [x] **Step 1: 复现**

Run: `cd quantsys-v2 && source venv/bin/activate && python -m pytest tests/ --collect-only -q 2>&1 | grep -B2 asyncio | head -10`
Expected: marker / module 缺失错误

- [x] **Step 2: 安装并补录 requirements**

```bash
source venv/bin/activate
pip install pytest-asyncio
pip freeze | grep -i asyncio   # 拿到版本号
```

把 `pytest-asyncio==<版本>` 追加到 `requirements.txt`。

- [x] **Step 3: 验证 3 文件 collection 恢复**

Run: `python -m pytest tests/adapters/outbound/repositories/test_async_kline_repository.py --collect-only -q`
Expected: 能 collect（async 测试若报"async def 不被支持"，在 pytest.ini 加 `asyncio_mode = auto`）

- [x] **Step 4: Commit**

```bash
git add quantsys-v2/requirements.txt quantsys-v2/pytest.ini
git commit -m "fix(test): 安装 pytest-asyncio——消 asyncio marker 未注册/模块缺失 3 个 collection error"
```

### Task 2.2: 批量修复 ORM 改名 stale import（14 文件）

**根因：** `adapters/outbound/repositories/__init__.py` 只导出 `*ORMRepository` 新名，14 个测试文件 import 旧名：`StrategyPerformanceRepository`×5、`FinancialRepository`×2、`SignalExecutionLogRepository`×2、`AgentKnowledgeRepository`/`MarketStyleRepository`/`StockPoolRepository`/`StrategyWeightRepository`/`RiskConfigRepository` 各 1。

- [x] **Step 1: 列出全部 stale import**

Run: `cd quantsys-v2 && grep -rn "from adapters.outbound.repositories import" tests/ | grep -v ORM`

- [x] **Step 2: 确认新旧名映射**（以 `adapters/outbound/repositories/__init__.py` 实际导出为准）

Run: `grep "ORMRepository\|Repository" adapters/outbound/repositories/__init__.py`

- [x] **Step 3: 逐文件替换为新类名**（sed 批量 + 人工抽查）

```bash
# 示例（实际映射以 Step 2 输出为准）：
grep -rl "StrategyPerformanceRepository" tests/ | xargs sed -i '' \
  's/\bStrategyPerformanceRepository\b/StrategyPerformanceORMRepository/g'
# 对其余 6 个类名重复
```

- [x] **Step 4: 验证 collection error 从 22 降到 ~5**

Run: `python -m pytest tests/ --collect-only -q 2>&1 | tail -5`
Expected: 只剩缺依赖类错误

- [x] **Step 5: Commit**

```bash
git add quantsys-v2/tests/
git commit -m "fix(test): 批量修复 ORM 改名遗留 stale import（14 文件，旧名→*ORMRepository）"
```

### Task 2.3: 补装缺失依赖（5 文件）

**根因：** venv 缺 aiohttp（daemon/test_factor_handlers、test_model_handlers）、psutil（e2e/test_factor_analysis_e2e）、backtrader、dependency_injector。

- [x] **Step 1: 安装并补录 requirements.txt**

```bash
source venv/bin/activate
pip install aiohttp psutil backtrader dependency_injector
```

逐一核对这些包是否生产也需要（grep 生产代码 import）：生产也用 → requirements.txt；仅测试用 → 仍记入 requirements.txt（本仓库不区分 dev-requirements）。

- [x] **Step 2: 验证 collection error 清零**

Run: `python -m pytest tests/ --collect-only -q 2>&1 | tail -3`
Expected: 0 errors

- [x] **Step 3: Commit**

```bash
git add quantsys-v2/requirements.txt
git commit -m "fix(test): 补装 aiohttp/psutil/backtrader/dependency_injector——消 5 个 collection error"
```

### Task 2.4: 评分服务断言更新为新契约（5 失败）

**Files:**
- Modify: `quantsys-v2/tests/services/test_opportunity_scoring_service.py`

**根因（2026-08-04 逐个核实，全是测试漂移非代码 bug）：**
- 评分已从"阶跃式/中性 50"改为"连续灰度 + 无条件用默认实分"（opportunity_scoring_service.py:515,607，07-28 91a21b1 引入）
- `test_score_stocks_parallel_processing` 是 symbol 格式漂移：`_normalize_symbol`（kline_repository.py:204）按无后缀查，测试 INSERT 带 `.SH` 后缀

- [x] **Step 1: 逐条更新断言为新契约值，并在注释中引用新契约**

| 测试 | 旧断言 | 新断言 | 依据 |
|---|---|---|---|
| test_calculate_technical_score_no_conditions | 50 | 65.0 | 无条件走 `_calculate_default_technical_score`，rsi=25 超卖 +15 |
| test_calculate_fundamental_score_no_conditions | 50 | 58.0 | 同上（默认基本面实分） |
| test_calculate_capital_score | 100 | 91.0 | 连续灰度：基础50+量比线性6+递增15+vs_ma20 10+ma5_vs_ma20 10 |
| test_score_stocks_with_insufficient_klines | 50 | 45 | 新契约不足 K 线给 45 |
| test_score_stocks_parallel_processing | scored=10 | INSERT 改无后缀 symbol（如 `600000`）后 scored=10 | `_normalize_symbol` 剥后缀 |

**注意：** 上表"新断言"是 2026-08-04 实测值；执行时必须重跑一次确认数值未再漂移，如漂移以最新实测为准并查原因。

- [x] **Step 2: 验证**

Run: `python -m pytest tests/services/test_opportunity_scoring_service.py tests/services/test_opportunity_radar_integration.py --no-header -q`
Expected: 全绿（radar 的 test_batch_query_efficiency / test_invalid_stock_codes 如同文件连带修复）

- [x] **Step 3: Commit**

```bash
git add quantsys-v2/tests/services/test_opportunity_scoring_service.py quantsys-v2/tests/services/test_opportunity_radar_integration.py
git commit -m "fix(test): 评分断言对齐连续灰度新契约（5个）+ symbol 改无后缀对齐 _normalize_symbol"
```

### Task 2.5: Batch 2 收尾

- [x] `python -m pytest tests/ --collect-only -q` 0 error
- [x] 合并回 main 并推送

---

## Batch 2.5：仓储契约裁决（Batch 2 暴露的深层问题）

**背景：** Batch 2 只解决了 collection error（22→0）。改名后测试能跑了，但暴露出与 Batch 1.4 同源的 ORM 重构契约破坏——以下文件运行时失败，每个都需要按"旧测试 vs 当前 ORM 表面 vs 生产调用方"三方对账裁决（恢复旧 API / 重写测试 / 删除）：

| 文件 | 现状 | 待裁决点 |
|---|---|---|
| tests/test_order_pnl_tracking.py | 4F | PortfolioORMRepository.get_signal_by_id 被清空；positions 表 avg_cost 列 schema 漂移 |
| tests/test_financial_repository.py | 4F | 测试用 .db/ save_income_statement（旧 psycopg2 API），ORM 是 upsert_income_statements |
| tests/repositories/test_financial_repository_polars.py | 4F | 同上 |
| tests/repositories/test_market_style_repository.py | 7F | 旧 API 漂移 |
| tests/repositories/test_stock_pool_repository.py | 12E | create(dict) 契约漂移（ORM create 不收 dict） |
| tests/repositories/test_strategy_weight_repository.py | 11F | 旧 API 漂移 |
| tests/test_async_kline_repository.py | 4F+25E | 旧 API 漂移 + async fixture 问题 |
| tests/test_signal_execution_integration.py | 1F | 契约漂移 |
| tests/repositories/test_agent_intelligence_repository.py | 3F | update_evaluation 返回 bool 非 dict；StockPool create 契约 |
| tests/test_signal_execution_log_repository.py | 2F | 小漂移（7/9 已过） |
| tests/test_risk_config_repository.py | 2F | 小漂移（4/6 已过） |
| tests/test_multi_account_domain.py | 5F（时间敏感） | 49d0b2b 交易时段护栏致非交易时段必挂——mock 时钟或 allow_off_hours |

**注意：** PortfolioORMRepository 很可能是继 StrategyPerformance 之后又一个被清空的仓（order_pnl 的 get_signal_by_id 缺失 + order-service.test.ts 的 TradeService 引用），优先裁决。

**修复原则（继承 Batch 1.4 经验）：**
- 先查归档仓库 /Users/mac/Documents/ai/quantsys-v2.git.archive 的旧实现
- 生产调用方丢功能 → 恢复实现（别名兼容新名）；仅测试漂移 → 改测试
- 每个仓独立 commit，message 写明三方对账结论

---

## Batch 3：jest B 类——删过时测试 + 修 mock 路径/契约（13 套件）

**预估：** 一天。**风险：** 中（含删除判断，每个删除都要人工核对）。

### Task 3.1: 删除被测源码已不存在的过时测试（6 套件）

**删除候选（执行时逐一 `ls` 复核源码确实不存在）：**

| 测试文件 | 依据（2026-08-04 侦查） |
|---|---|
| `src/services/quant/signal-generator.test.ts` | 源码 import 的 ./factor-library.js 已不存在 |
| `src/services/quant/integration.test.ts` | import 的 ./quant-service.js 已删/改名 |
| `src/services/quant/backtest-engine.test.ts` | 同上（quant-service） |
| `src/services/quant/factor-library.test.ts` | import 的 infrastructure/quant/stock-query-cli-adapter.js 不存在 |
| `src/services/intelligence/market-data-collector.test.ts` | import 的 market-query-cli-adapter.js 不存在 |
| `src/infrastructure/tools/test_tool-tool.test.ts` | 被测模块 ./test_tool-tool.js 不存在 |

- [x] **Step 1: 逐一验证**（示例）

```bash
cd agent-ts
ls src/services/quant/           # 确认 quant-service/factor-library 是否存在
ls src/infrastructure/quant/ 2>/dev/null  # 确认 cli-adapter 是否整体移除
```

**判断规则：** 源码文件不存在 → 删测试；源码存在但 import 断裂 → 停手，这属于生产代码 bug，升级处理（查 git log 找改名目标修复 import）。

- [x] **Step 2: 同时检查被删能力是否有替代测试覆盖**（如 quant-service 的能力是否已由 StrategyService 测试覆盖），在 commit message 里写明结论

- [x] **Step 3: 删除并验证**

Run: `npm test 2>&1 | grep -cE "^FAIL"`
Expected: 失败套件数减少对应数量

- [x] **Step 4: Commit（每个文件独立 commit 或一个 commit 列清依据）**

```bash
git commit -m "chore(test): 删除 6 个被测源码已不存在的过时套件（quant-service/factor-library/cli-adapter/test_tool-tool 已移除）"
```

### Task 3.2: 修相对 mock/import 路径（5 套件）

**逐一修复（模式相同：相对路径层级错）：**

| 测试文件 | 错 | 对 |
|---|---|---|
| `utils/strategy-helpers.test.ts` | `../../../src/infrastructure/...`（逃出包根） | 相对测试文件位置重算层级 |
| `strategy/batch-validate-tool.test.ts` | mock `../../quant/quant-v2-client.js` | `../../adapters/quant/quant-v2-client.js` |
| `data/fetch-stock-tool.test.ts` | 同上 | 同上 |
| `shared/notification-tools.test.ts` | `../services/notification/notification-service.js` | 相对实际位置（src/services/notification/） |
| `agent/memory-tool.test.ts` | `../../services/...` 少一级 | `../../../services/...` |

- [x] 每个文件：改 → `npm test -- <path>` 验证 → 5 个一起 commit

```bash
git commit -m "fix(test): 修 5 个套件 mock/import 相对路径（模块迁移后层级漂移）"
```

### Task 3.3: 修契约/签名漂移（3 套件）

| 测试文件 | 根因 | 修法 |
|---|---|---|
| `data/fetch-macro-tool.test.ts` | mock 用旧 {success,data}，RunQuantV2 已改 {ok,command} | mock 形状改 {ok,command}（参考 [[apiclient-envelope-unwrap]] 的契约教训，先看 quant-v2-client 当前真实返回类型） |
| `core/agent/error-handler.test.ts` | withErrorHandling 第 4 参类型变 undefined | 测试调用去掉 'default' 实参或改传 undefined，先看函数当前签名 |
| `services/order-service.test.ts` | 引用已删除的 TradeService 名（TS2304） | 查 git log 找替代类名重写引用；若能力已迁移且无替代测试，删该测试 |

- [x] 每个文件：先读被测源码当前签名 → 改测试 → 验证 → commit

```bash
git commit -m "fix(test): 3 个套件契约/签名漂移——{ok,command} 新契约、withErrorHandling 签名、TradeService 引用"
```

### Task 3.4: Batch 3 收尾

- [x] 全量 jest FAIL 清单中 B 类 13 套件清零
- [x] 合并回 main 并推送

---

## Batch 4：jest C 类——vitest 清除 + ESM 修复（8 套件）

**预估：** 半天。**风险：** 低（机械转换）。

### Task 4.1: 8 个 vitest 混入文件转 jest

**文件：** trade-monitor-tool、risk-controller-tool、performance-analyzer-tool、portfolio-optimizer-tool、verify-judgments-tool、data-manager-tool、factor-academic-tool、signal-arbiter

- [x] **Step 1: 机械替换模式**

```typescript
// 删：
import { vi } from 'vitest';
// 改（文件头 import 合并进现有 @jest/globals）：
import { jest } from '@jest/globals';
// vi.fn() → jest.fn()；vi.mock() → jest.mock()；vi.spyOn → jest.spyOn
```

**注意类型：** @jest/globals 严格类型下 `jest.fn()` 推断 never——链式 `mockResolvedValue` 可能触发 TS2345，统一用实现体写法 `jest.fn(async () => ...)`（同 Task 1.3 模式）。

- [x] **Step 2: 批量找出所有 vitest 引用确保无遗漏**

Run: `grep -rln "from 'vitest'" src/`

- [x] **Step 3: 逐文件转换 + 验证 + 一次 commit**

```bash
git commit -m "fix(test): 8 个套件 vitest 转 jest——消 Symbol(\$\$jest-matchers-object) 冲突"
```

### Task 4.2: timeseries-analyzer-tool ESM mock 修复 + 挂住问题

**Files:**
- Modify: `agent-ts/src/infrastructure/tools/timeseries/timeseries-analyzer-tool.test.ts`

**根因：** ESM 下 `jest.mock()` 不提升，mock 未生效（`mockResolvedValue is not a function`）；真实 client 句柄导致 jest 跑完挂住不退。

- [x] **Step 1: `jest.mock()` 改 `jest.unstable_mockModule()` + 动态 import 被测模块**（项目已有范例：session-memory-saver.test.ts:44、model-switcher.test.ts 的 `await import`）

- [x] **Step 2: 验证套件通过且进程正常退出（不加 --forceExit）**

Run: `npm test -- src/infrastructure/tools/timeseries/timeseries-analyzer-tool.test.ts`
Expected: PASS 且命令正常结束

- [x] **Step 3: Commit**

```bash
git commit -m "fix(test): timeseries ESM mock 改 unstable_mockModule——mock 生效 + 修 jest 挂住不退"
```

### Task 4.3: Batch 4 收尾

- [x] `grep -rln "from 'vitest'" src/` 无结果
- [x] 合并回 main 并推送

---

## Batch 5：jest D 类——断言漂移逐个裁决（8 套件）

**预估：** 一天。**风险：** 高（每个都要判断"新行为对不对"，可能揪出真 bug）。

**裁决规则：** 读源码当前实现 → 判断新行为是"有意变更"还是"事故"：
- 有意变更（有注释/commit 依据、行为合理）→ 更新测试
- 存疑 → 查引入变更的 commit（`git log -p -- <源码文件>`），仍存疑 → 标记出来找用户确认，**不要擅自改测试迁就**

| 套件 | 漂移点 | 初步判断（执行时复核） |
|---|---|---|
| factor/calculate-tool | 错误文案 "因子计算失败"→"执行失败：Network timeout" | 疑似网络错误泄漏进文案，查是否该 mock |
| data/fetch-kline-tool | 工具改返回人类可读文本，测试仍 JSON.parse | 契约有意改（对齐其他 data 工具），更新测试 |
| monitor/alert-tool | 文案+"买入/卖出信号已发送"；mock 形状 | 更新测试 + 修 mock |
| pool/pool-optimization | 测试 grep 源码断言实现细节 | 脆弱测试，改断言行为而非源码文本 |
| intelligence/evolution-executor | 返回 error、rollbackData 缺字段、jsonl 不再写 | **重点审查**，可能是真回归 |
| intelligence/skill-guard | deep-analysis 白名单不再含 data_fetch_stock | **查是否 07-28 工具清理的有意结果** |
| agent/claude-code-tool | spawn 'claude-code --json'→'claude -p --output-format json' | CLI 改名有意，更新测试 |
| utils/result-persister | 清理阈值/逻辑漂移 | 读 cleanup 实现对齐 |

- [x] 逐套件：裁决 → 修（测试或上报 bug）→ `npm test -- <path>` 验证 → 每套件独立 commit（message 写明裁决依据）
- [x] 合并回 main 并推送

---

## Batch 6：网络依赖套件 mock 化（2 套件）

### Task 6.1: evolution-service 网络 mock 化

**Files:**
- Modify: `agent-ts/src/services/intelligence/evolution-service.test.ts`

**根因：** 测试零 mock，`runWeeklyEvolution` 直连 127.0.0.1:5001 被生产 FastAPI 拒（account_name is required）——既是测试问题，也暴露"测试打生产端口"的风险。

- [x] **Step 1: 读 evolution-service 的外部依赖面**（QuantV2Client？直接 fetch？），用 `jest.unstable_mockModule` mock 掉 HTTP 层
- [x] **Step 2: 验证** `npm test -- src/services/intelligence/evolution-service.test.ts` PASS
- [x] **Step 3: Commit**

```bash
git commit -m "fix(test): evolution-service mock 化——消除测试直连生产 5001"
```

### Task 6.2: quant-v2-client 网络 mock 化

**Files:**
- Modify: `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.test.ts`

**根因：** 直连 127.0.0.1:5001（全量跑时耗时 41s 等超时）。这是 client 自身的测试，应 mock fetch/HTTP 层验证请求构造与响应解析，而不是真连服务。

- [x] **Step 1: mock 全局 fetch（或 client 使用的 HTTP 层），断言请求 URL/方法/载荷与响应解析**
- [x] **Step 2: 验证** `npm test -- src/infrastructure/adapters/quant/quant-v2-client.test.ts` PASS 且秒级结束
- [x] **Step 3: Commit + 合并推送**

```bash
git commit -m "fix(test): quant-v2-client mock fetch——消 41s 超时与 5001 依赖"
```

---

## 收尾：更新基线记忆

- [x] 全部批次合并后，全量 jest `npm test` 应 0 FAIL（或仅剩新发现问题），全量 pytest 可跑完且 collection 0 error
- [x] 更新 memory `baseline-failing-tests.md`：记录清零日期；**修正两条已过时记录**（多账户 5 失败实为 a7ec439 已修复；weight_adjuster 挂起已不复现，实为 stale import 2 失败并在 Batch 1 修复）

## 批次依赖与顺序

```
Batch 1（速修+生产bug）──┐
Batch 2（pytest）────────┼── 互不依赖，可任意顺序，但每批独立 worktree 独立合并
Batch 3（jest B）────────┤
Batch 4（jest C）────────┘
Batch 5（jest D）── 建议最后做（裁决最重，可能产生新 bug 单）
Batch 6（A）────── 独立，任意顺序
```
