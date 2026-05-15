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
});
