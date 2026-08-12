# T+1 可卖数量透出与卖出拦截反馈 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 agent 事前知道每持仓的 T+1 可卖数量（portfolio_status 透出 shares_available），卖出超额时被后端 422 拦截并收到结构化的"可卖 X 股"反馈，同时统一 T+1 话术为正确语义。

**Architecture:** 后端 quantsys-v2 保持唯一权威校验（已有 `shares_available` 校验逻辑不动），只做两件事：`TradingError` 携带 `details`、FastAPI 路由把 details 放进 422 响应体。agent-ts 侧做三层：`fetchV2` 解析 JSON 错误体挂到 `QuantV2Error`、`portfolio_status` 透出 `shares_available`、`portfolio_trade` 把 T+1 拦截翻译成 agent 可自我修正的结构化结果。

**Tech Stack:** Python 3.13 + FastAPI + pytest（quantsys-v2，测试自动切 quant_test 库）；TypeScript + Jest（agent-ts，**必须 `npm test`**，裸 `npx jest` 会误报 TS1378）。

**Spec:** `docs/superpowers/specs/2026-08-12-t1-sellable-visibility-design.md`

**Worktree:** 所有改动在 `/Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility`（分支 `worktree-t1-sellable-visibility`）内进行。

**已知基线：** agent-ts 存在 37 个预存在失败的 jest 套件（见项目 memory baseline-failing-tests）；只要求本计划触碰的测试文件全绿 + 不新增失败。

---

### Task 1: 后端 TradingError 携带 details，T+1 拦截两处透出 sellable_shares

**Files:**
- Modify: `quantsys-v2/application/services/account_trading_service.py:14-17`（TradingError 类）、`:206-208` 与 `:235-237`（两处 T+1 拦截）
- Test: `quantsys-v2/tests/test_multi_account_domain.py`（TestAccountTradingService 类内追加）

注意：该测试文件头部有 autouse fixture `_fixed_trading_clock`（固定 2026-08-03 周一 10:00 + 常真日历），新测试自动继承，无需处理交易时段。

- [ ] **Step 1: 写失败测试**

在 `quantsys-v2/tests/test_multi_account_domain.py` 的 `TestAccountTradingService` 类中（`test_sell_t1_blocked_same_day` 之后）追加：

```python
    def test_sell_t1_blocked_carries_details(self, repo, trading):
        repo.create_account('test_acc_a', initial_capital=100000)
        trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                              reason='测试买入：技术面突破+放量', price=10.0)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'sell', '600519', shares=100,
                                  reason='测试卖出：当日卖出应被T+1拦截', price=11.0)
        assert exc.value.status_code == 422
        assert exc.value.details == {'sellable_shares': 0, 'symbol': '600519'}

    def test_sell_t1_partial_available_details(self, repo, trading):
        """部分可卖：昨日买入 100（已结转可卖）+ 今日买入 100（不可卖），卖 200 被卡"""
        repo.create_account('test_acc_a', initial_capital=100000)
        trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                              reason='测试买入：第一笔建仓', price=10.0)
        repo.settle_t1('test_acc_a', today=date(2099, 1, 1))  # 模拟次日结转
        trading.execute_trade('test_acc_a', 'buy', '600519', shares=100,
                              reason='测试买入：次日加仓部分不可卖', price=10.0)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'sell', '600519', shares=200,
                                  reason='测试卖出：超出可卖数量应被拦截', price=11.0)
        assert exc.value.details == {'sellable_shares': 100, 'symbol': '600519'}

    def test_non_t1_error_has_no_details(self, repo, trading):
        """向后兼容：非 T+1 的 TradingError details 为 None"""
        repo.create_account('test_acc_a', initial_capital=1000)
        from application.services.account_trading_service import TradingError
        with pytest.raises(TradingError) as exc:
            trading.execute_trade('test_acc_a', 'buy', '600519', shares=1000,
                                  reason='测试买入：资金不足应被拒绝', price=10.0)
        assert exc.value.status_code == 422
        assert exc.value.details is None
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility/quantsys-v2
source venv/bin/activate
python -m pytest tests/test_multi_account_domain.py -k "carries_details or partial_available or no_details" -v
```

预期：3 个测试 FAIL，`AttributeError: 'TradingError' object has no attribute 'details'`。

- [ ] **Step 3: 实现**

修改 `quantsys-v2/application/services/account_trading_service.py`：

TradingError 类（14-17 行）改为：

```python
class TradingError(Exception):
    def __init__(self, message: str, status_code: int = 422, details: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details
```

第一处 T+1 拦截（206-208 行）改为：

```python
            if shares > pos.shares_available:
                raise TradingError(
                    f'T+1 可卖数量不足: 可卖 {pos.shares_available} 股，委托 {shares} 股', 422,
                    details={'sellable_shares': pos.shares_available, 'symbol': symbol})
```

第二处锁内复核（235-237 行）改为：

```python
                if shares > pos.shares_available:
                    raise TradingError(
                        f'T+1 可卖数量不足: 可卖 {pos.shares_available} 股，委托 {shares} 股', 422,
                        details={'sellable_shares': pos.shares_available, 'symbol': symbol})
```

- [ ] **Step 4: 跑测试确认通过 + 本文件无回归**

```bash
python -m pytest tests/test_multi_account_domain.py -v
```

预期：全部 PASS（含原有测试）。

- [ ] **Step 5: Commit**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility
git add quantsys-v2/application/services/account_trading_service.py quantsys-v2/tests/test_multi_account_domain.py
git commit -m "feat(trading): TradingError 携带 details——T+1 拦截透出 sellable_shares/symbol"
```

---

### Task 2: FastAPI 交易路由 422 响应体输出 details

**Files:**
- Modify: `quantsys-v2/adapters/inbound/fastapi_app/routes/simulation_async.py:89-91`（manual_trade 的 TradingError 分支）
- Test: Create `quantsys-v2/tests/api/test_simulation_trade_route.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/api/test_simulation_trade_route.py`：

```python
"""simulation 账户交易路由：T+1 拦截响应携带 details"""
import pytest
from datetime import datetime
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.simulation_async import router

ACCOUNT = 'test_route_t1_acc'


@pytest.fixture(autouse=True)
def _fixed_trading_clock(monkeypatch):
    """固定交易时段时钟（同 test_multi_account_domain.py）：交易时段护栏是生产行为，
    非本文件测试目标，统一注入固定交易时间 + 常真日历。"""
    from application.services import account_trading_service as ats
    real_init = ats.AccountTradingService.__init__

    def patched_init(self, repo=None, calendar=None, now_fn=None):
        real_init(self, repo=repo, calendar=calendar, now_fn=now_fn)
        if now_fn is None:
            self.now_fn = lambda: datetime(2026, 8, 3, 10, 0)  # 周一 10:00，交易时段内
        if calendar is None:
            self.calendar = SimpleNamespace(is_trading_day=lambda d: True)

    monkeypatch.setattr(ats.AccountTradingService, '__init__', patched_init)


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def account_partial_sellable():
    """持仓 200 股，其中仅 100 股可卖（模拟昨日 100 + 今日 100）"""
    from adapters.outbound.repositories import SimulationORMRepository
    repo = SimulationORMRepository()
    if repo.get_account(ACCOUNT) is None:
        repo.create_account(ACCOUNT, initial_capital=100000)
    repo.upsert_position(ACCOUNT, '600519', shares_total=200, avg_cost=10.0,
                         shares_available=100, current_price=11.0)
    return ACCOUNT


def test_t1_block_response_has_details(client, account_partial_sellable):
    resp = client.post(f'/api/simulation/accounts/{ACCOUNT}/trade', json={
        'action': 'sell', 'symbol': '600519', 'shares': 200,
        'price': 11.0, 'reason': '测试卖出：超出可卖数量应被拦截',
    })
    assert resp.status_code == 422
    body = resp.json()
    assert body['success'] is False
    assert body['details'] == {'sellable_shares': 100, 'symbol': '600519'}


def test_non_t1_error_has_no_details_key(client, account_partial_sellable):
    """向后兼容：非 T+1 错误响应体不输出 details 键"""
    resp = client.post(f'/api/simulation/accounts/{ACCOUNT}/trade', json={
        'action': 'sell', 'symbol': '000001', 'shares': 100,
        'price': 11.0, 'reason': '测试卖出：无持仓应被拒绝',
    })
    assert resp.status_code == 422
    body = resp.json()
    assert body['success'] is False
    assert 'details' not in body
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility/quantsys-v2
source venv/bin/activate
python -m pytest tests/api/test_simulation_trade_route.py -v
```

预期：`test_t1_block_response_has_details` FAIL（KeyError: 'details'）；`test_non_t1_error_has_no_details_key` PASS。

- [ ] **Step 3: 实现**

修改 `quantsys-v2/adapters/inbound/fastapi_app/routes/simulation_async.py` manual_trade 的 TradingError 分支（89-91 行）为：

```python
    except TradingError as e:
        body = {'success': False, 'error': str(e)}
        if getattr(e, 'details', None) is not None:
            body['details'] = e.details
        return JSONResponse(status_code=e.status_code, content=body)
```

注意：只改 `manual_trade`（71-93 行）这一处。`cancel_pending_order` 等其他路由的 TradingError 分支不动（YAGNI）。

- [ ] **Step 4: 跑测试确认通过**

```bash
python -m pytest tests/api/test_simulation_trade_route.py tests/test_multi_account_domain.py -v
```

预期：全部 PASS。

- [ ] **Step 5: Commit**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility
git add quantsys-v2/adapters/inbound/fastapi_app/routes/simulation_async.py quantsys-v2/tests/api/test_simulation_trade_route.py
git commit -m "feat(api): 账户交易路由 422 响应输出 details——agent 可读到结构化可卖数量"
```

---

### Task 3: QuantV2Error 增加 apiError/details，fetchV2 解析 JSON 错误体

**Files:**
- Modify: `agent-ts/src/infrastructure/adapters/quant/types.ts:342-351`（QuantV2Error 类）
- Modify: `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts:696-703`（fetchV2 的 !response.ok 分支）
- Test: `agent-ts/src/infrastructure/adapters/quant/quant-v2-client-accounts.test.ts`

注意：`quant-v2-client.ts` 里 `runQuantV2`（562-568 行）有另一个 !ok 抛出分支，**不要改**——账户端点走的是 `fetchV2`，runQuantV2 改动超出本次范围（YAGNI）。

- [ ] **Step 1: 写失败测试**

在 `agent-ts/src/infrastructure/adapters/quant/quant-v2-client-accounts.test.ts` 的 import 块追加 `QuantV2Error`：

```ts
import { QuantV2Error } from "./types.js";
```

在 `describe("QuantV2Client 账户方法", ...)` 内追加：

```ts
  test("executeAccountTrade 422 时解析出 apiError 与 details", async () => {
    mockFetch.mockResolvedValue(jsonResponse({
      success: false,
      error: "T+1 可卖数量不足: 可卖 600 股，委托 1000 股",
      details: { sellable_shares: 600, symbol: "600519" },
    }, 422));
    const err: any = await executeAccountTrade("agent_virtual", {
      action: "sell", symbol: "600519", shares: 1000, reason: "测试卖出理由：不少于十个字",
    }).catch((e) => e);
    expect(err).toBeInstanceOf(QuantV2Error);
    expect(err.apiError).toContain("可卖 600");
    expect(err.details).toEqual({ sellable_shares: 600, symbol: "600519" });
    expect(err.message).toContain("HTTP 422");  // message 格式不变，向后兼容
  });

  test("executeAccountTrade 非 JSON 错误体保持原文行为", async () => {
    mockFetch.mockResolvedValue(new Response("Bad Gateway", { status: 502 }));
    const err: any = await executeAccountTrade("agent_virtual", {
      action: "sell", symbol: "600519", shares: 100, reason: "测试卖出理由：不少于十个字",
    }).catch((e) => e);
    expect(err).toBeInstanceOf(QuantV2Error);
    expect(err.message).toContain("HTTP 502");
    expect(err.apiError).toBeUndefined();
    expect(err.details).toBeUndefined();
  });
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility/agent-ts
npm test -- --runTestsByPath src/infrastructure/adapters/quant/quant-v2-client-accounts.test.ts
```

预期：新增 2 个测试 FAIL（`err.apiError` 为 undefined）。

- [ ] **Step 3: 实现**

修改 `agent-ts/src/infrastructure/adapters/quant/types.ts` 的 QuantV2Error（342-351 行）为：

```ts
export class QuantV2Error extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public endpoint?: string,
    /** 后端 JSON 错误体中的 error 字段（非 JSON 响应时为 undefined） */
    public apiError?: string,
    /** 后端 JSON 错误体中的 details 字段（如 T+1 拦截的 sellable_shares） */
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'QuantV2Error';
  }
}
```

修改 `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts` fetchV2 的 !response.ok 分支（696-703 行）为：

```ts
    if (!response.ok) {
      const text = await response.text().catch(() => '');
      // 后端错误体为 { success: false, error, details? } 时解析出结构化字段，
      // 供调用方（如 portfolio_trade 的 T+1 反馈翻译）使用；message 保持原格式不动。
      let apiError: string | undefined;
      let details: Record<string, unknown> | undefined;
      try {
        const body = JSON.parse(text);
        if (body && typeof body === 'object') {
          if (typeof body.error === 'string') apiError = body.error;
          if (body.details && typeof body.details === 'object') {
            details = body.details as Record<string, unknown>;
          }
        }
      } catch { /* 非 JSON 响应，保持纯文本行为 */ }
      throw new QuantV2Error(
        `HTTP ${response.status}: ${text || response.statusText}`,
        response.status,
        url,
        apiError,
        details,
      );
    }
```

- [ ] **Step 4: 跑测试确认通过 + 相关文件无回归**

```bash
npm test -- --runTestsByPath src/infrastructure/adapters/quant/quant-v2-client-accounts.test.ts src/infrastructure/adapters/quant/quant-v2-client.test.ts
```

预期：全部 PASS。

- [ ] **Step 5: Commit**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility
git add agent-ts/src/infrastructure/adapters/quant/types.ts agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts agent-ts/src/infrastructure/adapters/quant/quant-v2-client-accounts.test.ts
git commit -m "feat(client): QuantV2Error 解析后端 JSON 错误体——apiError/details 结构化透出"
```

---

### Task 4: portfolio_status 透出 shares_available

**Files:**
- Modify: `agent-ts/src/infrastructure/tools/portfolio/portfolio-status-tool.ts:17-30`（PortfolioHolding 接口）、`:100-110`（holdings 映射）
- Test: `agent-ts/src/infrastructure/tools/portfolio/portfolio-status-tool.test.ts`

- [ ] **Step 1: 写失败测试**

在 `agent-ts/src/infrastructure/tools/portfolio/portfolio-status-tool.test.ts` 追加新 describe：

```ts
describe("computePortfolioView T+1 可卖数量", () => {
  test("透出 shares_available（持仓总数与可卖数成对出现）", () => {
    const view = computePortfolioView({
      cash: "40000",
      total_value: "51000",
      positions: [
        {
          symbol: "600519",
          shares_total: 1000,
          shares_available: 600,
          avg_cost: "10",
          current_price: "11",
          market_value: "11000",
          profit_total: "1000",
          profit_total_rate: 0.1,
        },
      ],
    });
    expect(view.holdings[0].shares).toBe(1000);
    expect(view.holdings[0].shares_available).toBe(600);
  });

  test("shares_available 缺失时保持 undefined，绝不回退总持仓造假", () => {
    const view = computePortfolioView({
      cash: "40000",
      positions: [
        { symbol: "600519", shares: 40, market_value: "60000", profit: "0" },
      ],
    });
    expect(view.holdings[0].shares_available).toBeUndefined();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility/agent-ts
npm test -- --runTestsByPath src/infrastructure/tools/portfolio/portfolio-status-tool.test.ts
```

预期：第一个新测试 FAIL（`shares_available` 为 undefined）；第二个 PASS。

- [ ] **Step 3: 实现**

修改 `agent-ts/src/infrastructure/tools/portfolio/portfolio-status-tool.ts`：

PortfolioHolding 接口（17-30 行）在 `days_held` 字段后追加：

```ts
  /** T+1 可卖数量；后端未提供时为 undefined，绝不回退 shares 造假（同 days_held 契约） */
  shares_available?: number;
```

holdings 映射（100-110 行）的 return 对象中，在 `shares:` 行后追加 `shares_available` 字段。完整映射改为：

```ts
    // shares_available 是 T+1 风控关键字段：后端缺失时保持 undefined，
    // 绝不用 shares_total 回退造假（agent 会把"全部可卖"当事实）
    const sharesAvailable = h.shares_available != null && Number.isFinite(Number(h.shares_available))
      ? Number(h.shares_available)
      : undefined;

    return {
      symbol: h.symbol,
      shares: Number(h.shares_total ?? h.shares) || 0,
      shares_available: sharesAvailable,
      cost_price: Number(h.avg_cost ?? h.avg_price ?? h.cost_price ?? h.cost) || 0,
      current_price: Number(h.current_price) || 0,
      market_value: marketValue,
      pnl: profit,
      pnl_pct: pnlPct,
      days_held: daysHeld,
      price_updated_at: h.price_updated_at ?? undefined
    };
```

- [ ] **Step 4: 跑测试确认通过**

```bash
npm test -- --runTestsByPath src/infrastructure/tools/portfolio/portfolio-status-tool.test.ts
```

预期：全部 PASS（含原有恒等式测试）。

- [ ] **Step 5: Commit**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility
git add agent-ts/src/infrastructure/tools/portfolio/portfolio-status-tool.ts agent-ts/src/infrastructure/tools/portfolio/portfolio-status-tool.test.ts
git commit -m "feat(portfolio): portfolio_status 透出 shares_available——agent 事前知道每持仓可卖数量"
```

---

### Task 5: portfolio_trade T+1 拦截反馈翻译

**Files:**
- Modify: `agent-ts/src/infrastructure/tools/portfolio/portfolio-trade-tool.ts:91-97`（catch 分支）
- Test: `agent-ts/src/infrastructure/tools/portfolio/portfolio-trade-tool.test.ts`

- [ ] **Step 1: 写失败测试**

在 `agent-ts/src/infrastructure/tools/portfolio/portfolio-trade-tool.test.ts` 的 describe 内追加：

```ts
  test("T+1 超额卖出被拦截时返回结构化可卖数量", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({
      success: false,
      error: "T+1 可卖数量不足: 可卖 600 股，委托 1000 股",
      details: { sellable_shares: 600, symbol: "600519" },
    }), { status: 422, headers: { "Content-Type": "application/json" } }));
    const result = await executePortfolioTrade({
      action: "sell", symbol: "600519", account: "agent_virtual",
      shares: 1000, reason: "测试卖出理由：止盈离场不少于十个字",
    } as any) as any;
    expect(result.success).toBe(false);
    expect(result.sellable_shares).toBe(600);
    expect(result.hint).toContain("600");
    expect(result.hint).toContain("shares_available");
  });

  test("非 T+1 的 422 走原有兜底格式（无 sellable_shares）", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({
      success: false,
      error: "可用资金不足: 需要 ¥100,005.00，可用 ¥1,000.00",
    }), { status: 422, headers: { "Content-Type": "application/json" } }));
    const result = await executePortfolioTrade({
      action: "buy", symbol: "600519", account: "agent_virtual",
      shares: 1000, reason: "测试买入理由：资金不足应被拒绝",
    } as any) as any;
    expect(result.success).toBe(false);
    expect(result.sellable_shares).toBeUndefined();
    expect(result.error).toContain("交易执行失败");
  });
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility/agent-ts
npm test -- --runTestsByPath src/infrastructure/tools/portfolio/portfolio-trade-tool.test.ts
```

预期：第一个新测试 FAIL（`sellable_shares` 为 undefined）；第二个 PASS。

- [ ] **Step 3: 实现**

修改 `agent-ts/src/infrastructure/tools/portfolio/portfolio-trade-tool.ts`：

文件顶部 import 区追加：

```ts
import { QuantV2Error } from "../../adapters/quant/types.js";
```

catch 分支（91-97 行）改为：

```ts
  } catch (error) {
    // T+1 拦截：后端 422 details 带 sellable_shares，翻译成 agent 可自我修正的结构化反馈
    if (error instanceof QuantV2Error && typeof error.details?.sellable_shares === 'number') {
      const sellable = error.details.sellable_shares as number;
      return {
        success: false,
        error: `超出 T+1 可卖数量: ${error.apiError ?? error.message}`,
        sellable_shares: sellable,
        hint: `该持仓今日可卖 ${sellable} 股（超出部分为今日买入，明日才可卖）。` +
          `请用不超过 ${sellable} 股的数量重试；各持仓可卖数量以 portfolio_status 的 shares_available 为准。`,
      };
    }
    return {
      success: false,
      error: `交易执行失败: ${error instanceof Error ? error.message : String(error)}`,
      hint: '账户名错误或风控拦截；先用 portfolio_status({ action: "list" }) 确认账户'
    };
  }
```

- [ ] **Step 4: 跑测试确认通过**

```bash
npm test -- --runTestsByPath src/infrastructure/tools/portfolio/portfolio-trade-tool.test.ts
```

预期：全部 PASS。

- [ ] **Step 5: Commit**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility
git add agent-ts/src/infrastructure/tools/portfolio/portfolio-trade-tool.ts agent-ts/src/infrastructure/tools/portfolio/portfolio-trade-tool.test.ts
git commit -m "feat(portfolio): portfolio_trade T+1 拦截翻译——结构化 sellable_shares + 可自我修正的 hint"
```

---

### Task 6: T+1 话术澄清（5 处文案）

**Files:**
- Modify: `agent-ts/src/infrastructure/tools/portfolio/portfolio-trade-tool.ts:87`、`:109`、`:120`
- Modify: `agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts:41`、`:92`、`:159`

统一口径：**"仅当日买入部分不可卖；之前持有的随时可卖，以 portfolio_status 的 shares_available 为准"**。

- [ ] **Step 1: 改 portfolio-trade-tool.ts 三处**

87 行（买入成交 note）：

```ts
        ? 'T+1规则：本次买入的份额明日才可卖；其余已持有份额不受影响'
```

109 行（功能描述）：

```ts
    "\n  • 卖出股票（可卖数量以 portfolio_status 的 shares_available 为准）" +
```

120 行（注意事项）：

```ts
    "\n  • T+1规则：仅当日买入部分次日才可卖，之前持有的随时可卖（以 shares_available 为准）" +
```

- [ ] **Step 2: 改 agent-decision-tasks.ts 三处**

41 行：

```ts
   - 注意T+1：仅今日买入的部分明天才能卖；之前持有的随时可卖，以 portfolio_status 的 shares_available 为准
```

92 行：

```ts
- 记住T+1：仅今天买入的部分明天才能卖；之前持有的随时可卖（以 shares_available 为准）
```

159 行：

```ts
- 记住T+1：仅今日买入的部分无法当日卖出；之前持有的可卖（以 shares_available 为准）
```

- [ ] **Step 3: 跑相关测试 + 工具引用检查**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility/agent-ts
npm test -- --runTestsByPath src/infrastructure/tools/portfolio/portfolio-trade-tool.test.ts
npm run check:tool-refs
```

预期：测试 PASS；check:tool-refs 退出码 0（本次未改工具名，仅确认无漂移）。

- [ ] **Step 4: Commit**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility
git add agent-ts/src/infrastructure/tools/portfolio/portfolio-trade-tool.ts agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts
git commit -m "docs(agent): T+1 话术澄清——仅当日买入部分不可卖，以 shares_available 为准"
```

---

### Task 7: 全量验证

- [ ] **Step 1: 后端测试**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility/quantsys-v2
source venv/bin/activate
python -m pytest tests/test_multi_account_domain.py tests/api/test_simulation_trade_route.py tests/test_order_pnl_tracking.py tests/test_trading_window_guard.py tests/test_trade_cash_race.py -v
```

预期：全部 PASS。

- [ ] **Step 2: agent-ts 触碰的测试文件**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility/agent-ts
npm test -- --runTestsByPath \
  src/infrastructure/adapters/quant/quant-v2-client-accounts.test.ts \
  src/infrastructure/adapters/quant/quant-v2-client.test.ts \
  src/infrastructure/tools/portfolio/portfolio-status-tool.test.ts \
  src/infrastructure/tools/portfolio/portfolio-trade-tool.test.ts \
  src/infrastructure/tools/portfolio/portfolio-analyze-tool.test.ts \
  src/infrastructure/tools/portfolio/portfolio-account-tool.test.ts
```

预期：全部 PASS。

- [ ] **Step 3: TypeScript 编译检查**

```bash
cd /Users/yunpeng/pi-investment/.claude/worktrees/t1-sellable-visibility/agent-ts
npm run build
```

预期：tsc 无错误。

- [ ] **Step 4: 部署备注（合并后人工执行，不在本计划内操作）**

- 重启 5001 FastAPI（主工作区 venv nohup 手动重启）
- 重启 agent 进程使工具描述与 prompt 生效
- 无数据库迁移
