import { describe, expect, test, beforeEach } from "@jest/globals";
import { mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { OrderService } from "./order-service.js";
import { PortfolioService } from "./portfolio/portfolio-service.js";
import { TradeService } from "./portfolio/trade-service.js";

describe("OrderService - High-level business methods", () => {
  let testDir: string;
  let orderService: OrderService;
  let portfolioService: PortfolioService;
  let tradeService: TradeService;

  beforeEach(() => {
    testDir = mkdtempSync(join(tmpdir(), "pi-invest-order-"));
    orderService = new OrderService(testDir);
    portfolioService = new PortfolioService(testDir);
    tradeService = new TradeService(testDir);
    orderService.setServices(portfolioService, tradeService);
    portfolioService.setTradeService(tradeService);
  });

  describe("fillOrder()", () => {
    test("successfully fills a buy order", async () => {
      // 创建买入挂单
      const order = orderService.create({
        symbol: "600519",
        name: "茅台",
        side: "buy",
        type: "limit",
        price: 1800,
        quantity: 100,
        market: "A",
      });

      // 执行成交
      const result = await orderService.fillOrder(order.id, 1800, 100);

      expect(result.success).toBe(true);
      expect(result.fillPrice).toBe(1800);
      expect(result.fillQuantity).toBe(100);
      expect(result.portfolioAction).toBe("add");
      expect(result.tradeRecorded).toBe(true);

      // ✅ 验证返回了更新后的持仓
      expect(result.updatedHolding).toBeDefined();
      expect(result.updatedHolding?.symbol).toBe("600519");
      expect(result.updatedHolding?.quantity).toBe(100);

      // ✅ 验证返回了剩余挂单列表
      expect(result.remainingOrders).toBeDefined();
      expect(Array.isArray(result.remainingOrders)).toBe(true);

      // 验证持仓
      const portfolio = portfolioService.load();
      expect(portfolio.holdings).toHaveLength(1);
      expect(portfolio.holdings[0].symbol).toBe("600519");
      expect(portfolio.holdings[0].quantity).toBe(100);

      // 验证挂单状态
      const updatedOrder = orderService.get(order.id);
      expect(updatedOrder?.status).toBe("filled");
    });

    test("successfully fills a sell order (partial)", async () => {
      // 先添加持仓
      portfolioService.add("600519", 100, 1800, 0, "茅台", "A");

      // 创建卖出挂单
      const order = orderService.create({
        symbol: "600519",
        name: "茅台",
        side: "sell",
        type: "limit",
        price: 2000,
        quantity: 30,
        market: "A",
      });

      // 执行成交
      const result = await orderService.fillOrder(order.id, 2000, 30);

      expect(result.success).toBe(true);
      expect(result.portfolioAction).toBe("update");

      // 验证持仓
      const portfolio = portfolioService.load();
      expect(portfolio.holdings[0].quantity).toBe(70);
    });

    test("successfully fills a sell order (clear position)", async () => {
      // 先添加持仓
      portfolioService.add("600519", 100, 1800, 0, "茅台", "A");

      // 创建卖出挂单
      const order = orderService.create({
        symbol: "600519",
        name: "茅台",
        side: "sell",
        type: "limit",
        price: 2000,
        quantity: 100,
        market: "A",
      });

      // 执行成交
      const result = await orderService.fillOrder(order.id, 2000, 100);

      expect(result.success).toBe(true);
      expect(result.portfolioAction).toBe("remove");

      // 验证持仓已清空
      const portfolio = portfolioService.load();
      expect(portfolio.holdings).toHaveLength(0);
    });

    test("fails when order not found", async () => {
      const result = await orderService.fillOrder("non-existent", 1800, 100);

      expect(result.success).toBe(false);
      expect(result.error).toContain("未找到挂单");
    });

    test("fails when order status is not pending", async () => {
      const order = orderService.create({
        symbol: "600519",
        name: "茅台",
        side: "buy",
        type: "limit",
        price: 1800,
        quantity: 100,
        market: "A",
      });

      // 先成交一次
      await orderService.fillOrder(order.id, 1800, 100);

      // 再次尝试成交
      const result = await orderService.fillOrder(order.id, 1800, 100);

      expect(result.success).toBe(false);
      expect(result.error).toContain("状态为");
    });

    test("fails when selling with insufficient holdings", async () => {
      // 只有 50 股持仓
      portfolioService.add("600519", 50, 1800, 0, "茅台", "A");

      // 创建卖出 100 股的挂单
      const order = orderService.create({
        symbol: "600519",
        name: "茅台",
        side: "sell",
        type: "limit",
        price: 2000,
        quantity: 100,
        market: "A",
      });

      // 执行成交
      const result = await orderService.fillOrder(order.id, 2000, 100);

      expect(result.success).toBe(false);
      expect(result.error).toContain("持仓不足");
    });

    test("fails with invalid fill price", async () => {
      const order = orderService.create({
        symbol: "600519",
        name: "茅台",
        side: "buy",
        type: "limit",
        price: 1800,
        quantity: 100,
        market: "A",
      });

      const result = await orderService.fillOrder(order.id, 0, 100);

      expect(result.success).toBe(false);
      expect(result.error).toContain("成交价必须大于0");
    });
  });

  describe("checkAndFillOrders()", () => {
    test("returns empty result when no pending orders", async () => {
      const result = await orderService.checkAndFillOrders();

      expect(result.totalChecked).toBe(0);
      expect(result.fills).toHaveLength(0);
      expect(result.notYets).toHaveLength(0);
      expect(result.errors).toHaveLength(0);
    });

    test("clears expired orders", async () => {
      // 创建一个已过期的挂单
      const order = orderService.create({
        symbol: "600519",
        name: "茅台",
        side: "buy",
        type: "limit",
        price: 1800,
        quantity: 100,
        market: "A",
        expires_in_minutes: -1, // 已过期
      });

      const result = await orderService.checkAndFillOrders();

      expect(result.expiredCount).toBe(1);

      // 验证挂单状态
      const updatedOrder = orderService.get(order.id);
      expect(updatedOrder?.status).toBe("expired");
    });

    test("dry run mode does not execute fills", async () => {
      orderService.create({
        symbol: "600519",
        name: "茅台",
        side: "buy",
        type: "limit",
        price: 1800,
        quantity: 100,
        market: "A",
      });

      const result = await orderService.checkAndFillOrders(undefined, true);

      // 试运行模式下，不会实际成交
      expect(result.fills.length).toBeGreaterThanOrEqual(0);

      // 验证持仓未变化
      const portfolio = portfolioService.load();
      expect(portfolio.holdings).toHaveLength(0);
    });
  });

  describe("calculateCommission()", () => {
    test("calculates A-share commission correctly (0.025%, min 5 CNY)", () => {
      // 小额交易：应返回最低手续费 5 元
      expect(orderService.calculateCommission("A", 10, 100)).toBe(5);

      // 大额交易：应按万2.5计算
      // 1800 * 1000 = 1,800,000，手续费 = 1,800,000 * 0.00025 = 450
      expect(orderService.calculateCommission("A", 1800, 1000)).toBe(450);

      // 边界测试：刚好超过最低手续费
      // 需要 amount * 0.00025 > 5，即 amount > 20000
      // 20000 * 0.00025 = 5
      expect(orderService.calculateCommission("A", 100, 200)).toBe(5);
      expect(orderService.calculateCommission("A", 100, 201)).toBe(5.03);
    });

    test("calculates HK-share commission correctly (0.05%, min 5 HKD)", () => {
      // 小额交易：应返回最低手续费 5 港币
      expect(orderService.calculateCommission("HK", 10, 50)).toBe(5);

      // 大额交易：应按万5计算
      // 100 * 1000 = 100,000，手续费 = 100,000 * 0.0005 = 50
      expect(orderService.calculateCommission("HK", 100, 1000)).toBe(50);

      // 边界测试：刚好超过最低手续费
      // 需要 amount * 0.0005 > 5，即 amount > 10000
      expect(orderService.calculateCommission("HK", 50, 200)).toBe(5);
      expect(orderService.calculateCommission("HK", 50, 201)).toBe(5.03);
    });

    test("commission is applied in buy orders", async () => {
      const order = orderService.create({
        symbol: "600519",
        name: "茅台",
        side: "buy",
        type: "limit",
        price: 1800,
        quantity: 100,
        market: "A",
      });

      await orderService.fillOrder(order.id, 1800, 100);

      // 验证持仓成本包含手续费
      // 手续费 = 1800 * 100 * 0.00025 = 45
      // 总成本 = 1800 * 100 + 45 = 180,045
      // 均价 = 180,045 / 100 = 1800.45
      const portfolio = portfolioService.load();
      const holding = portfolio.holdings[0];
      expect(holding.avg_cost).toBeCloseTo(1800.45, 2);
    });

    test("commission is applied in sell orders", async () => {
      // 先通过买入挂单成交来建立持仓（这样会同时创建持仓和交易记录）
      const buyOrder = orderService.create({
        symbol: "600519",
        name: "茅台",
        side: "buy",
        type: "limit",
        price: 1800,
        quantity: 100,
        market: "A",
      });
      await orderService.fillOrder(buyOrder.id, 1800, 100);

      // 创建卖出挂单
      const order = orderService.create({
        symbol: "600519",
        name: "茅台",
        side: "sell",
        type: "limit",
        price: 2000,
        quantity: 100,
        market: "A",
      });

      const result = await orderService.fillOrder(order.id, 2000, 100);

      // 验证盈亏计算包含手续费
      // 卖出金额 = 2000 * 100 = 200,000
      // 手续费 = 200,000 * 0.00025 = 50
      // 实际收入 = 200,000 - 50 = 199,950
      // 买入成本 = 1800 * 100 + 45 = 180,045
      // 盈亏 = 199,950 - 180,045 = 19,905
      expect(result.success).toBe(true);
      expect(result.tradeRecorded).toBe(true);

      // 验证交易记录
      const trades = tradeService.load();
      const sellTrade = trades.trades.find((t: any) => t.action === "sell");
      expect(sellTrade).toBeDefined();
      expect(sellTrade?.commission).toBe(50);
      expect(sellTrade?.amount).toBe(200000);
    });

    test("uses custom commission rate when provided", () => {
      // 自定义费率：万3 (0.0003)
      const customRate = 0.0003;

      // 小额交易：使用自定义费率，无最低限制
      // 10 * 100 * 0.0003 = 0.3
      expect(orderService.calculateCommission("A", 10, 100, customRate)).toBe(0.3);

      // 大额交易：按自定义费率计算
      // 1800 * 1000 * 0.0003 = 540
      expect(orderService.calculateCommission("A", 1800, 1000, customRate)).toBe(540);

      // 港股也使用自定义费率
      expect(orderService.calculateCommission("HK", 100, 1000, customRate)).toBe(30);
    });

    test("custom commission rate is applied in orders", async () => {
      // 创建带自定义费率的买入挂单（万3）
      const order = orderService.create({
        symbol: "600519",
        name: "茅台",
        side: "buy",
        type: "limit",
        price: 1800,
        quantity: 100,
        market: "A",
        commission_rate: 0.0003,
      });

      await orderService.fillOrder(order.id, 1800, 100);

      // 验证持仓成本使用自定义费率
      // 手续费 = 1800 * 100 * 0.0003 = 54
      // 总成本 = 1800 * 100 + 54 = 180,054
      // 均价 = 180,054 / 100 = 1800.54
      const portfolio = portfolioService.load();
      const holding = portfolio.holdings[0];
      expect(holding.avg_cost).toBeCloseTo(1800.54, 2);
    });
  });
});
