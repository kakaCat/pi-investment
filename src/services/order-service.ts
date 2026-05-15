/**
 * OrderService — 挂单追踪服务
 *
 * 存储路径: .pi-invest/orders.json
 * 每笔挂单记录限价单/止损单/分批计划，附带完整状态机：
 *
 * 状态机:
 *   pending ──→ filled      (市价达到挂单价，成交)
 *   pending ──→ cancelled   (用户主动撤销)
 *   pending ──→ expired     (过期/超时)
 *
 * 协作关系:
 *   - check_pending_orders 工具调用此服务检查触发条件
 *   - 成交后自动调用 PortfolioService.add/sell + TradeService.add
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { chinaDateTime } from "../utils/china-time.js";
import { FileLockService } from "./file-lock.service.js";

// ─── 数据类型 ──────────────────────────────────────────────────────────────

export type OrderSide = "buy" | "sell";
export type OrderType = "limit" | "stop_loss" | "batch_plan";
export type OrderStatus = "pending" | "filled" | "partial" | "cancelled" | "expired";

export interface OrderHistoryEntry {
  status: OrderStatus;
  timestamp: string;
  reason?: string;
}

export interface PendingOrder {
  id: string;
  symbol: string;           // 股票代码（6位A股，或港股带.HK后缀）
  name: string;             // 股票名称
  side: OrderSide;          // buy=买入, sell=卖出
  type: OrderType;          // limit=限价单, stop_loss=止损单, batch_plan=分批计划
  price: number;            // 挂单价
  quantity: number;         // 挂单数量
  filled_quantity: number;  // 已成交数量（用于分批成交）
  fill_price: number | null; // 实际成交价（null=未成交）
  status: OrderStatus;
  market: "A" | "HK";
  commission_rate?: number; // 手续费率（可选），如 0.00025 表示万2.5，不设置则使用默认值
  created_at: string;
  updated_at: string;
  expires_at: string | null; // null=永不过期
  history: OrderHistoryEntry[];
  notes: string;
}

export interface OrdersFile {
  orders: PendingOrder[];
  last_updated: string;
}

// ─── 工具函数 ──────────────────────────────────────────────────────────────

function makeId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

function nowStr(): string {
  return chinaDateTime();
}

function roundN(v: number, n = 2): number {
  return Math.round(v * Math.pow(10, n)) / Math.pow(10, n);
}

// ─── 高层业务结果类型 ──────────────────────────────────────────────────────

export interface FillOrderResult {
  success: boolean;
  order: PendingOrder;
  fillPrice: number;
  fillQuantity: number;
  portfolioAction: "add" | "remove" | "update" | "noop";
  portfolioMessage: string;
  tradeRecorded: boolean;
  error?: string;
  updatedHolding?: any;           // 更新后的持仓
  remainingOrders?: PendingOrder[]; // 剩余挂单
}

export interface CheckOrdersResult {
  expiredCount: number;
  totalChecked: number;
  fills: Array<{
    order: PendingOrder;
    currentPrice: number;
    fillQuantity: number;
    triggerCondition: string;
    result: FillOrderResult;
  }>;
  notYets: Array<{
    order: PendingOrder;
    currentPrice: number;
    diffPct: number;
    reason: string;
  }>;
  errors: Array<{
    order: PendingOrder;
    error: string;
  }>;
  portfolioSnapshot?: any;        // 完整持仓快照（供 LLM 决策）
  remainingOrders?: PendingOrder[]; // 剩余挂单
}

// ─── OrderService ──────────────────────────────────────────────────────────

export class OrderService {
  private filePath: string;
  private piDir: string;
  private portfolioService?: any;
  private tradeService?: any;

  constructor(piDir: string) {
    this.piDir = piDir;
    this.filePath = join(piDir, "orders.json");
    mkdirSync(piDir, { recursive: true });
    this.ensureFile();
  }

  /**
   * 设置依赖服务（用于高层业务方法）
   */
  setServices(portfolioService: any, tradeService: any): void {
    this.portfolioService = portfolioService;
    this.tradeService = tradeService;
  }

  /**
   * 计算交易手续费
   * @param market 市场类型
   * @param price 成交价格
   * @param quantity 成交数量
   * @param customRate 可选：自定义手续费率（如 0.00025 表示万2.5），优先使用此值
   * @returns 手续费金额（保留2位小数）
   */
  calculateCommission(
    market: "A" | "HK",
    price: number,
    quantity: number,
    customRate?: number
  ): number {
    const amount = price * quantity;

    // 如果提供了自定义费率，使用自定义费率（无最低限制）
    if (customRate !== undefined) {
      return roundN(amount * customRate, 2);
    }

    // A股：万2.5，最低5元
    if (market === "A") {
      const commission = amount * 0.00025;
      return roundN(Math.max(commission, 5), 2);
    }

    // 港股：万5，最低5港币
    if (market === "HK") {
      const commission = amount * 0.0005;
      return roundN(Math.max(commission, 5), 2);
    }

    return 0;
  }

  private ensureFile(): void {
    if (!existsSync(this.filePath)) {
      writeFileSync(
        this.filePath,
        JSON.stringify({ orders: [], last_updated: "" }, null, 2),
        "utf-8",
      );
    }
  }

  load(): OrdersFile {
    try {
      const content = readFileSync(this.filePath, "utf-8");
      const parsed = JSON.parse(content);

      // 兼容性处理：如果是旧的数组格式，自动迁移
      if (Array.isArray(parsed)) {
        console.warn("⚠️  检测到旧格式 orders.json（数组），自动迁移到新格式");
        const migrated: OrdersFile = {
          orders: parsed,
          last_updated: nowStr()
        };
        this.save(migrated);
        return migrated;
      }

      // 新格式验证
      if (!parsed.orders || !Array.isArray(parsed.orders)) {
        console.error("❌ orders.json 格式错误，期望 { orders: [], last_updated: '' }");
        return { orders: [], last_updated: "" };
      }

      return parsed as OrdersFile;
    } catch (error) {
      console.error("❌ 读取 orders.json 失败:", error);
      return { orders: [], last_updated: "" };
    }
  }

  private save(data: OrdersFile): void {
    data.last_updated = nowStr();
    FileLockService.withLockSync(this.filePath, () => {
      writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
    });
  }

  private addHistory(
    order: PendingOrder,
    status: OrderStatus,
    reason?: string,
  ): void {
    order.history.push({
      status,
      timestamp: nowStr(),
      reason,
    });
  }

  // ── CRUD ─────────────────────────────────────────────────────────────────

  /**
   * 创建挂单
   */
  create(params: {
    symbol: string;
    name: string;
    side: OrderSide;
    type: OrderType;
    price: number;
    quantity: number;
    market: "A" | "HK";
    commission_rate?: number; // 可选：自定义手续费率，如 0.00025 表示万2.5
    notes?: string;
    expires_in_minutes?: number; // 超时自动过期（分钟），不传=永不过期
  }): PendingOrder {
    if (params.quantity <= 0) throw new Error("quantity 必须大于0");
    if (params.price <= 0) throw new Error("price 必须大于0");

    // 限价单校验：市价单不允许（仅支持挂单）
    if (params.type !== "limit" && params.type !== "stop_loss" && params.type !== "batch_plan") {
      throw new Error(`不支持的挂单类型: ${params.type}`);
    }

    const now = nowStr();
    const expiresAt = params.expires_in_minutes
      ? new Date(Date.now() + params.expires_in_minutes * 60 * 1000).toISOString()
      : null;

    const order: PendingOrder = {
      id: makeId(),
      symbol: params.symbol,
      name: params.name,
      side: params.side,
      type: params.type,
      price: params.price,
      quantity: params.quantity,
      filled_quantity: 0,
      fill_price: null,
      status: "pending",
      market: params.market,
      commission_rate: params.commission_rate, // 保存自定义手续费率
      created_at: now,
      updated_at: now,
      expires_at: expiresAt,
      history: [{ status: "pending", timestamp: now, reason: "创建挂单" }],
      notes: params.notes || "",
    };

    return FileLockService.withLockSync(this.filePath, () => {
      const data = this.load();
      data.orders.push(order);
      data.last_updated = nowStr();
      writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
      return order;
    });
  }

  /**
   * 按ID查询挂单
   */
  get(id: string): PendingOrder | undefined {
    return this.load().orders.find((o) => o.id === id);
  }

  /**
   * 按条件筛选挂单
   */
  list(filter?: {
    status?: OrderStatus | OrderStatus[];
    symbol?: string;
    side?: OrderSide;
    type?: OrderType;
  }): PendingOrder[] {
    let orders = this.load().orders;
    if (filter) {
      if (filter.status) {
        const statuses = Array.isArray(filter.status) ? filter.status : [filter.status];
        orders = orders.filter((o) => statuses.includes(o.status));
      }
      if (filter.symbol) orders = orders.filter((o) => o.symbol === filter.symbol);
      if (filter.side) orders = orders.filter((o) => o.side === filter.side);
      if (filter.type) orders = orders.filter((o) => o.type === filter.type);
    }
    return orders;
  }

  /**
   * 获取所有 pending 状态挂单（最常用）
   */
  listPending(): PendingOrder[] {
    return this.list({ status: "pending" });
  }

  /**
   * 撤销挂单
   */
  cancel(id: string, reason?: string): PendingOrder | null {
    return FileLockService.withLockSync(this.filePath, () => {
      const data = this.load();
      const order = data.orders.find((o) => o.id === id);
      if (!order) return null;
      if (order.status !== "pending") {
        throw new Error(`挂单 ${id} 状态为 ${order.status}，无法撤销`);
      }
      order.status = "cancelled";
      order.updated_at = nowStr();
      this.addHistory(order, "cancelled", reason || "主动撤销");
      data.last_updated = nowStr();
      writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
      return order;
    });
  }

  /**
   * 标记挂单过期
   */
  expire(id: string, reason?: string): PendingOrder | null {
    return FileLockService.withLockSync(this.filePath, () => {
      const data = this.load();
      const order = data.orders.find((o) => o.id === id);
      if (!order) return null;
      if (order.status !== "pending") return null;
      order.status = "expired";
      order.updated_at = nowStr();
      this.addHistory(order, "expired", reason || "超时过期");
      data.last_updated = nowStr();
      writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
      return order;
    });
  }

  /**
   * 检查并执行超期挂单
   */
  expireOverdue(): number {
    return FileLockService.withLockSync(this.filePath, () => {
      const data = this.load();
      let count = 0;
      const now = Date.now();
      for (const order of data.orders) {
        if (
          order.status === "pending" &&
          order.expires_at &&
          new Date(order.expires_at).getTime() <= now
        ) {
          order.status = "expired";
          order.updated_at = nowStr();
          this.addHistory(order, "expired", "超时自动过期");
          count++;
        }
      }
      if (count > 0) {
        data.last_updated = nowStr();
        writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
      }
      return count;
    });
  }

  /**
   * 标记挂单成交（完全成交或部分成交）
   *
   * @param id 挂单ID
   * @param fillPrice 实际成交价
   * @param fillQuantity 本次成交数量（不传=全额成交）
   * @returns 成交后的订单对象
   */
  fill(
    id: string,
    fillPrice: number,
    fillQuantity?: number,
  ): PendingOrder | null {
    return FileLockService.withLockSync(this.filePath, () => {
      const data = this.load();
      const order = data.orders.find((o) => o.id === id);
      if (!order) return null;
      if (order.status !== "pending") return null;

      const qtyToFill = fillQuantity ?? order.quantity;

      if (qtyToFill <= 0) {
        throw new Error(`成交数量必须大于0: ${qtyToFill}`);
      }
      if (order.filled_quantity + qtyToFill > order.quantity) {
        throw new Error(
          `成交数量超过挂单剩余: 已成交 ${order.filled_quantity}，本次 ${qtyToFill}，总量 ${order.quantity}`,
        );
      }

      order.filled_quantity += qtyToFill;
      order.fill_price = roundN(fillPrice);
      order.updated_at = nowStr();

      // 判断是否完全成交
      if (order.filled_quantity >= order.quantity) {
        order.status = "filled";
        this.addHistory(
          order,
          "filled",
          `全额成交 ${qtyToFill}股 @${fillPrice}`,
        );
      } else {
        order.status = "partial";
        this.addHistory(
          order,
          "partial",
          `部分成交 ${qtyToFill}股 @${fillPrice}，剩余 ${order.quantity - order.filled_quantity}股`,
        );
      }

      data.last_updated = nowStr();
      writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
      return order;
    });
  }

  /**
   * 获取 Pi 目录路径（供外部使用）
   */
  get piDirPath(): string {
    return this.piDir;
  }

  // ── 高层业务方法 ────────────────────────────────────────────────────────

  /**
   * 完整的挂单成交流程（高层业务方法）
   *
   * 包含：验证挂单状态 → 校验持仓 → 更新持仓 → 记录交易 → 更新挂单状态
   *
   * @param orderId 挂单ID
   * @param fillPrice 实际成交价
   * @param fillQuantity 本次成交数量（不传=全额成交）
   * @returns 结构化的成交结果
   */
  async fillOrder(
    orderId: string,
    fillPrice: number,
    fillQuantity?: number,
  ): Promise<FillOrderResult> {
    if (!this.portfolioService || !this.tradeService) {
      throw new Error("OrderService.fillOrder() 需要先调用 setServices() 注入依赖");
    }

    // 1. 验证挂单
    const order = this.get(orderId);
    if (!order) {
      return {
        success: false,
        order: null as any,
        fillPrice: 0,
        fillQuantity: 0,
        portfolioAction: "noop",
        portfolioMessage: "",
        tradeRecorded: false,
        error: `未找到挂单 ${orderId}`,
      };
    }

    if (order.status !== "pending") {
      return {
        success: false,
        order,
        fillPrice: 0,
        fillQuantity: 0,
        portfolioAction: "noop",
        portfolioMessage: "",
        tradeRecorded: false,
        error: `挂单状态为 ${order.status}，无法成交`,
      };
    }

    if (fillPrice <= 0) {
      return {
        success: false,
        order,
        fillPrice: 0,
        fillQuantity: 0,
        portfolioAction: "noop",
        portfolioMessage: "",
        tradeRecorded: false,
        error: `成交价必须大于0，当前值: ${fillPrice}`,
      };
    }

    const fillQty = fillQuantity ?? order.quantity;
    if (fillQty <= 0) {
      return {
        success: false,
        order,
        fillPrice: 0,
        fillQuantity: 0,
        portfolioAction: "noop",
        portfolioMessage: "",
        tradeRecorded: false,
        error: `成交数量必须大于0，当前值: ${fillQty}`,
      };
    }

    // 2. 卖出前校验持仓
    if (order.side === "sell") {
      const portfolio = this.portfolioService.load();
      const holding = portfolio.holdings.find((h: any) => h.symbol === order.symbol);
      const heldQty = holding?.quantity ?? 0;
      if (heldQty < fillQty) {
        return {
          success: false,
          order,
          fillPrice,
          fillQuantity: fillQty,
          portfolioAction: "noop",
          portfolioMessage: "",
          tradeRecorded: false,
          error: `持仓不足: 需卖出 ${fillQty} 股，实际仅持有 ${heldQty} 股`,
        };
      }
    }

    // 3. 更新持仓
    let portfolioAction: "add" | "remove" | "update" | "noop" = "noop";
    let portfolioMessage = "";
    let tradeRecorded = false;
    let sellResult: any = undefined;

    try {
      if (order.side === "buy") {
        // 买入：计算手续费（优先使用挂单的自定义费率）
        const commission = this.calculateCommission(
          order.market,
          fillPrice,
          fillQty,
          order.commission_rate
        );
        const result = this.portfolioService.add(
          order.symbol,
          fillQty,
          fillPrice,
          commission,
          order.name,
          order.market,
          `挂单成交 ${orderId} @${fillPrice}`,
        );
        portfolioAction = "add";
        portfolioMessage = result.message;

        // 记录交易
        try {
          const { chinaDate } = await import("../utils/china-time.js");
          this.tradeService.add(
            chinaDate(),
            order.symbol,
            order.name,
            "buy",
            fillQty,
            fillPrice,
            commission,
            order.market,
            `挂单成交 [${orderId}] ${order.notes}`,
          );
          tradeRecorded = true;
        } catch (e) {
          console.warn("交易记录失败:", e);
        }
      } else {
        // 卖出：计算手续费（优先使用挂单的自定义费率）并调用 PortfolioService.sell()
        const commission = this.calculateCommission(
          order.market,
          fillPrice,
          fillQty,
          order.commission_rate
        );
        sellResult = this.portfolioService.sell(
          order.symbol,
          fillQty,
          fillPrice,
          commission,
          `挂单成交 [${orderId}] ${order.notes}`,
        );
        portfolioAction = sellResult.remaining > 0 ? "update" : "remove";
        portfolioMessage = sellResult.message;
        tradeRecorded = sellResult.tradeRecorded;
      }
    } catch (e) {
      return {
        success: false,
        order,
        fillPrice,
        fillQuantity: fillQty,
        portfolioAction: "noop",
        portfolioMessage: "",
        tradeRecorded: false,
        error: `更新持仓失败: ${e instanceof Error ? e.message : String(e)}`,
      };
    }

    // 4. 更新挂单状态
    this.fill(orderId, fillPrice, fillQty);

    // 5. 获取更新后的持仓和剩余挂单
    const updatedHolding = this.portfolioService
      .load()
      .holdings.find((h: any) => h.symbol === order.symbol);
    const remainingOrders = this.listPending();

    return {
      success: true,
      order,
      fillPrice,
      fillQuantity: fillQty,
      portfolioAction,
      portfolioMessage,
      tradeRecorded,
      updatedHolding,
      remainingOrders,
    };
  }

  /**
   * 检查并自动成交挂单（高层业务方法）
   *
   * 包含：清理过期 → 获取实时价格 → 判断触发 → 执行成交
   *
   * @param symbol 可选，只检查指定股票的挂单
   * @param dryRun 试运行模式，不实际成交
   * @returns 结构化的检查结果
   */
  async checkAndFillOrders(
    symbol?: string,
    dryRun = false,
  ): Promise<CheckOrdersResult> {
    if (!this.portfolioService || !this.tradeService) {
      throw new Error("OrderService.checkAndFillOrders() 需要先调用 setServices() 注入依赖");
    }

    // 1. 清理过期挂单
    const expiredCount = this.expireOverdue();

    // 2. 获取待检查的挂单
    let pendingOrders: PendingOrder[];
    if (symbol) {
      pendingOrders = this.list({ status: "pending", symbol });
    } else {
      pendingOrders = this.listPending();
    }

    const fills: CheckOrdersResult["fills"] = [];
    const notYets: CheckOrdersResult["notYets"] = [];
    const errors: CheckOrdersResult["errors"] = [];

    // 3. 逐个检查触发
    for (const order of pendingOrders) {
      // 获取实时价格
      let priceResult: string;
      try {
        const { get_stock_realtime_price, get_hk_stock_price } = await import("../infrastructure/akshare-ts/index.js");
        priceResult =
          order.market === "HK"
            ? await get_hk_stock_price(order.symbol)
            : await get_stock_realtime_price(order.symbol);
      } catch (e) {
        errors.push({
          order,
          error: `获取价格失败: ${e instanceof Error ? e.message : String(e)}`,
        });
        continue;
      }

      let parsed: Record<string, unknown>;
      try {
        parsed = JSON.parse(priceResult);
      } catch {
        errors.push({ order, error: `价格数据解析失败` });
        continue;
      }

      const currentPrice = Number(parsed.price ?? parsed.current_price ?? 0);
      if (!currentPrice || currentPrice <= 0) {
        errors.push({
          order,
          error: `当前价格不可用（非交易时段?）: price=${parsed.price}`,
        });
        continue;
      }

      const diffPct = roundN(((currentPrice - order.price) / order.price) * 100);

      // 4. 触发判断
      let triggered = false;
      let triggerCondition = "";

      if (order.side === "buy") {
        // 买入：市价 ≤ 挂单价
        if (currentPrice <= order.price) {
          triggered = true;
          triggerCondition = `买入触发: 市价 ¥${currentPrice.toFixed(2)} ≤ 挂单价 ¥${order.price.toFixed(2)} (${diffPct >= 0 ? "+" : ""}${diffPct.toFixed(2)}%)`;
        } else {
          triggerCondition = `未触发: 市价 ¥${currentPrice.toFixed(2)} > 挂单价 ¥${order.price.toFixed(2)} (需再跌 ${Math.abs(diffPct).toFixed(2)}%)`;
        }
      } else {
        // 卖出
        if (order.type === "stop_loss") {
          // 止损：市价 ≤ 止损价
          if (currentPrice <= order.price) {
            triggered = true;
            triggerCondition = `止损触发: 市价 ¥${currentPrice.toFixed(2)} ≤ 止损价 ¥${order.price.toFixed(2)} (${diffPct >= 0 ? "+" : ""}${diffPct.toFixed(2)}%)`;
          } else {
            triggerCondition = `止损未触发: 市价 ¥${currentPrice.toFixed(2)} > 止损价 ¥${order.price.toFixed(2)} (安全距离 ${Math.abs(diffPct).toFixed(2)}%)`;
          }
        } else {
          // 限价卖出：市价 ≥ 挂单价
          if (currentPrice >= order.price) {
            triggered = true;
            triggerCondition = `卖出触发: 市价 ¥${currentPrice.toFixed(2)} ≥ 挂单价 ¥${order.price.toFixed(2)} (${diffPct >= 0 ? "+" : ""}${diffPct.toFixed(2)}%)`;
          } else {
            triggerCondition = `未触发: 市价 ¥${currentPrice.toFixed(2)} < 挂单价 ¥${order.price.toFixed(2)} (需再涨 ${Math.abs(diffPct).toFixed(2)}%)`;
          }
        }
      }

      if (!triggered) {
        notYets.push({ order, currentPrice, diffPct, reason: triggerCondition });
        continue;
      }

      // 5. 试运行模式
      if (dryRun) {
        fills.push({
          order,
          currentPrice,
          fillQuantity: order.quantity - order.filled_quantity,
          triggerCondition: `[试运行] ${triggerCondition}`,
          result: {
            success: true,
            order,
            fillPrice: order.price,
            fillQuantity: order.quantity - order.filled_quantity,
            portfolioAction: "noop",
            portfolioMessage: "试运行模式，未实际成交",
            tradeRecorded: false,
          },
        });
        continue;
      }

      // 6. 执行成交
      const fillPrice = order.price;
      const fillQty = order.quantity - order.filled_quantity;

      const result = await this.fillOrder(order.id, fillPrice, fillQty);

      if (result.success) {
        fills.push({
          order,
          currentPrice,
          fillQuantity: fillQty,
          triggerCondition,
          result,
        });
      } else {
        errors.push({ order, error: result.error || "成交失败" });
      }
    }

    // 7. 获取完整持仓快照和剩余挂单
    let portfolioSnapshot: any;
    try {
      portfolioSnapshot = await this.portfolioService.getWithPnL();
    } catch (e) {
      console.warn("获取持仓快照失败:", e);
    }

    const remainingOrders = this.listPending();

    return {
      expiredCount,
      totalChecked: pendingOrders.length,
      fills,
      notYets,
      errors,
      portfolioSnapshot,
      remainingOrders,
    };
  }
}
