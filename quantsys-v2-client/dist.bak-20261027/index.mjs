import axios from "axios";
import axiosRetry from "axios-retry";
//#region src/client.ts
/**
* 账户单一事实源（2026-09-13 w-c8cae280）：本包不依赖 @pi-investment/core-tool，
* 故就地定义同名常量；可用环境变量 DSH_INVESTMENT_ACCOUNT 覆盖。
* 提示词/任务侧的事实源是 profileDir/agents.json 的 instance.account。
*/
const DEFAULT_AGENT_ACCOUNT = typeof process !== "undefined" && process.env?.DSH_INVESTMENT_ACCOUNT?.trim() || "agent_brain";
/**
* QuantsysV2 API Client
*/
var QuantsysV2Client = class {
	client;
	constructor(config) {
		this.client = axios.create({
			baseURL: config.baseURL,
			timeout: config.timeout || 3e4,
			headers: {
				"Content-Type": "application/json",
				...config.headers
			}
		});
		this.client.interceptors.response.use((response) => response, (error) => {
			if (error?.message?.startsWith("[quantsys-v2]") || error?.message?.startsWith("[quantsys-v2 不可达]")) return Promise.reject(error);
			const endpoint = `${error.config?.method?.toUpperCase() ?? "?"} ${error.config?.url ?? "?"}`;
			if (!error.response) {
				const code = error.code ?? "NETWORK_ERROR";
				error.message = `[quantsys-v2 不可达] ${endpoint} (${code})。${code === "ECONNREFUSED" ? "后端服务未启动或端口不通——可用 quantsys_v2_status 检查后端健康，必要时 quantsys_v2_restart 拉起" : code === "ECONNABORTED" ? "请求超时——后端可能过载或挂死（历史上由事件循环阻塞引起），可用 quantsys_v2_status 确认" : code === "ERR_BAD_REQUEST" ? "HTTP 4xx：请求被后端拒绝（参数名/取值问题，非网络故障）——核对参数名与取值范围，必要时直接 curl 同一端点复现" : "网络异常——检查后端进程与端口" + (code ? "（code=" + code + "）" : "")}`;
				return Promise.reject(error);
			}
			const status = error.response.status;
			const body = error.response.data;
			error.message = `[quantsys-v2] ${endpoint} → HTTP ${status}: ${(body && typeof body === "object" ? (typeof body.error === "string" ? body.error : null) ?? body.message ?? (typeof body.detail === "string" ? body.detail : String(JSON.stringify(body.detail ?? body) ?? "").slice(0, 200)) : String(body ?? "").slice(0, 200)) || "无详情"}。${{
				400: "请求参数不合法——检查入参（字段名/格式/必填项）",
				404: "接口不存在或资源未找到——检查 URL 路径与参数",
				422: "参数校验失败（FastAPI schema）——检查字段类型",
				500: "后端内部错误——用 quantsys_v2_logs 查看后端日志定位",
				502: "上游数据源故障（网关）——稍后重试或切换数据源",
				503: "服务暂不可用——可能在重启或过载，稍后重试"
			}[status] ?? "查看后端日志定位原因"}`;
			return Promise.reject(error);
		});
		axiosRetry(this.client, {
			retries: 3,
			retryDelay: axiosRetry.exponentialDelay,
			retryCondition: (error) => {
				return axiosRetry.isNetworkOrIdempotentRequestError(error) || (error.response?.status ? error.response.status >= 500 : false);
			},
			onRetry: (retryCount, error, requestConfig) => {
				console.log(`[QuantsysV2Client] Retrying request (${retryCount}/3): ${requestConfig.method?.toUpperCase()} ${requestConfig.url} - ${error.message}`);
			}
		});
	}
	/**
	* Parse condition string to conditions array for watch rules (backend schema)
	* Examples:
	*   "price>100" -> [{type: "price_break", params: {direction: "above", price: 100}}]
	*   "price<90" -> [{type: "price_break", params: {direction: "below", price: 90}}]
	*   "change_pct>5" -> [{type: "pct_change", params: {direction: "above", pct: 5}}]
	*   "change_pct<-3" -> [{type: "pct_change", params: {direction: "below", pct: -3}}]
	* 
	* Supports:
	*   - price > N / price < N  → price_break (突破/跌破价格)
	*   - change_pct > N / change_pct < N  → pct_change (涨跌幅)
	*   - Operators: >, <, >=, <=
	*/
	parseCondition(condition) {
		const trimmed = condition.trim();
		if (trimmed.startsWith("{")) try {
			const parsed = JSON.parse(trimmed);
			if (parsed.type === "combined") return [parsed];
			if (parsed.type && parsed.params) return [parsed];
			throw new Error("JSON 格式必须包含 type 和 params");
		} catch (e) {
			throw new Error(`Invalid JSON condition format: "${condition}". \nJSON 格式示例：{"type":"combined","params":{"operator":"AND","conditions":[...]}}`);
		}
		const velMatch = trimmed.match(/^velocity\s*>\s*([0-9]+\.?[0-9]*)\s*\/\s*([0-9]+)$/);
		if (velMatch) return [{
			type: "velocity",
			params: {
				pct: parseFloat(velMatch[1]),
				window_min: parseInt(velMatch[2], 10)
			}
		}];
		const volMatch = trimmed.match(/^volume_surge\s*>\s*([0-9]+\.?[0-9]*)$/);
		if (volMatch) return [{
			type: "volume_surge",
			params: { multiple: parseFloat(volMatch[1]) }
		}];
		const match = trimmed.match(/^([a-z_]+)\s*(>=?|<=?)\s*(-?[0-9]+\.?[0-9]*)$/);
		if (!match) throw new Error(`Invalid watch condition format: "${condition}". \nSupported: price>N, price<N, change_pct>N, change_pct<-N, pnl_pct>N, pnl_pct<-N（需 cost_price）, volume_surge>N, velocity>N/M`);
		const [, field, operator, valueStr] = match;
		const value = parseFloat(valueStr);
		const direction = operator === ">" || operator === ">=" ? "above" : "below";
		if (field === "price") return [{
			type: "price_break",
			params: {
				direction,
				price: value
			}
		}];
		else if (field === "change_pct") return [{
			type: "pct_change",
			params: {
				direction,
				pct: value
			}
		}];
		else if (field === "pnl_pct") return [{
			type: "pnl_pct",
			params: {
				direction,
				pct: value
			}
		}];
		else throw new Error(`Unknown watch condition field: "${field}".\nSupported fields: price, change_pct, pnl_pct, volume_surge, velocity`);
	}
	/**
	* Unwrap response envelope based on endpoint-specific patterns
	*/
	unwrap(response, endpoint) {
		if (response.success === false) throw new Error(response.error || `API request failed: ${endpoint}`);
		if (response.success === true && "data" in response) return response.data;
		if (response.success === true && "rules" in response) return response.rules;
		if (response.success === true && "events" in response) return response;
		if (response.success === true && "event" in response) return response.event;
		if (response.success === true && "deleted" in response) return response;
		return response;
	}
	/**
	* Search stocks
	*/
	async searchStocks(query) {
		const response = await this.client.get("/api/stocks/search", { params: { q: query } });
		return this.unwrap(response.data, "searchStocks");
	}
	/**
	* Get K-line data
	* Real endpoint: GET /api/stock/{symbol}/klines
	* Response: {symbol, count, klines: [...]} - no success envelope
	*/
	async getKlines(symbol, startDate, endDate, period = "daily", limit) {
		return (await this.client.get(`/api/stock/${symbol}/klines`, { params: {
			start_date: startDate,
			end_date: endDate,
			period,
			limit
		} })).data.klines || [];
	}
	/**
	* Get K-line data with full envelope（含解析元数据）。
	* 2026-09-11（REQ-733c5e, w-348bf585）：后端 /api/stock/{symbol}/klines 自本日起在响应里附带
	* resolved_kind / resolved_symbol / resolved_name / ambiguity_warning，用于杜绝"指数/股票同码"
	* 静默错配（000905→厦门港务 vs 中证500）。getKlines 只取 klines 数组、会丢这些字段；
	* 需要歧义判定时用本方法拿完整 envelope。
	*/
	async getKlinesEnvelope(symbol, startDate, endDate, period = "daily", limit) {
		return (await this.client.get("/api/stock/" + symbol + "/klines", { params: {
			start_date: startDate,
			end_date: endDate,
			period,
			limit
		} })).data;
	}
	/**
	* List strategies
	* Real endpoint: GET /api/strategies/list
	* Response: {success, data: {total, page, pageSize, items: [...]}}
	*/
	async listStrategies(params) {
		if (params !== void 0 && (params === null || typeof params !== "object")) throw new Error("[listStrategies] 参数必须是对象，如 listStrategies({ source: \"user\" })，收到: " + typeof params);
		const { code_type, ...rest } = params ?? {};
		const response = await this.client.get("/api/strategies/list", { params: {
			...rest,
			...code_type ? { codeType: code_type } : {}
		} });
		return this.unwrap(response.data, "listStrategies");
	}
	/**
	* Get strategy by ID
	*/
	async getStrategy(id) {
		const response = await this.client.get(`/api/strategies/${id}`);
		return this.unwrap(response.data, "getStrategy");
	}
	/**
	* Create strategy
	*/
	async createStrategy(strategy) {
		const response = await this.client.post("/api/strategies/create", strategy);
		return this.unwrap(response.data, "createStrategy");
	}
	/**
	* Update strategy
	*/
	async updateStrategy(id, updates) {
		const response = await this.client.put(`/api/strategies/${id}`, updates);
		return this.unwrap(response.data, "updateStrategy");
	}
	/**
	* Delete strategy
	*/
	async deleteStrategy(id) {
		await this.client.delete(`/api/strategies/${id}`);
	}
	/**
	* Backtest strategy
	*/
	async backtestStrategy(request) {
		const body = {
			strategy_id: request.strategy_id,
			symbol: request.symbol || request.symbols?.[0],
			start_date: request.start_date,
			end_date: request.end_date,
			initial_capital: request.initial_capital ?? 1e5
		};
		if (request.parameters) body.parameters = request.parameters;
		const response = await this.client.post("/api/backtest/run", body);
		return this.unwrap(response.data, "backtestStrategy");
	}
	/**
	* Optimize strategy parameters (backtest matrix)
	* Real endpoint: POST /api/strategies/optimize
	*/
	async optimizeStrategy(params) {
		const body = {
			strategyId: params.strategy_id,
			symbol: params.symbol,
			startDate: params.start_date,
			endDate: params.end_date,
			paramRanges: params.param_ranges,
			initialCash: params.initial_cash,
			sortBy: params.sort_by
		};
		return (await this.client.post("/api/strategies/optimize", body)).data;
	}
	/**
	* List pools
	* Real endpoint: GET /api/pools
	* Response: {success, data: [...]}
	*/
	async listPools() {
		const response = await this.client.get("/api/pools");
		return this.unwrap(response.data, "listPools");
	}
	/**
	* Get pool by ID
	*/
	async getPool(id) {
		const response = await this.client.get(`/api/pools/${id}`);
		return this.unwrap(response.data, "getPool");
	}
	/**
	* Create pool（对齐后端 POST /api/pools 契约：pool_type 必填）
	* pool_type: static（手工成员）/ dynamic（filter_template 驱动，refresh 时重算）
	* category: 业务分类（如 板块共振），与 pool_type 正交
	* filter_template: 动态池筛选规则 {conditions:[...], top_n?, sort_by?, min_score?...}（经 validate_filter 校验）
	*/
	async createPool(pool) {
		const body = {
			name: pool.name,
			poolType: pool.pool_type,
			category: pool.category,
			description: pool.description,
			symbols: pool.symbols,
			filterTemplate: pool.filter_template,
			refreshInterval: pool.refresh_interval ?? void 0
		};
		const response = await this.client.post("/api/pools", body);
		return this.unwrap(response.data, "createPool");
	}
	/**
	* Update pool（name/symbols/description 覆盖更新——symbols 为整表替换，增删成员请用 addPoolMembers/removePoolMembers）
	*/
	async updatePool(id, updates) {
		const response = await this.client.put(`/api/pools/${id}`, updates);
		return this.unwrap(response.data, "updatePool");
	}
	/**
	* Delete pool
	*/
	async deletePool(id) {
		await this.client.delete(`/api/pools/${id}`);
	}
	/**
	* Get pool members —— 后端无 GET /api/pools/{id}/members 路由（2026-09-05 核对，仅
	* PUT/POST/DELETE members 三种），成员明细随池对象（getPool/create/update 响应）的
	* symbols/members 字段返回，故该方法移除，勿再调用。
	*/
	/**
	* Add members to pool（批量，对齐后端 POST /api/pools/{id}/members：body.symbols 数组）
	*/
	async addPoolMembers(poolId, params) {
		const body = {
			symbols: params.symbols,
			description: params.description,
			buyPoint: params.buy_point,
			sellPoint: params.sell_point,
			tags: params.tags
		};
		const response = await this.client.post(`/api/pools/${poolId}/members`, body);
		return this.unwrap(response.data, "addPoolMembers");
	}
	/**
	* Remove members from pool（批量，对齐后端 DELETE /api/pools/{id}/members：body.symbols 数组）
	*/
	async removePoolMembers(poolId, symbols) {
		const response = await this.client.delete(`/api/pools/${poolId}/members`, { data: { symbols } });
		return this.unwrap(response.data, "removePoolMembers");
	}
	/**
	* Update member metadata（对齐后端 PUT /api/pools/{id}/members/{symbol}：description/buy_point/sell_point/tags）
	*/
	async updatePoolMember(poolId, symbol, meta) {
		const body = {
			description: meta.description,
			buyPoint: meta.buy_point,
			sellPoint: meta.sell_point,
			tags: meta.tags
		};
		const response = await this.client.put(`/api/pools/${poolId}/members/${symbol}`, body);
		return this.unwrap(response.data, "updatePoolMember");
	}
	/**
	* Refresh pool（重算动态池成员 / 同步静态池展示计数）
	*/
	async refreshPool(poolId) {
		const response = await this.client.post(`/api/pools/${poolId}/refresh`);
		return this.unwrap(response.data, "refreshPool");
	}
	/**
	* Sync stock names（把池内符号补充为 {symbol, name} 展示形态）
	*/
	async syncStockNames(poolId) {
		const response = await this.client.post(`/api/pools/${poolId}/sync-stock-names`);
		return this.unwrap(response.data, "syncStockNames");
	}
	/**
	* Validate pool（对池成员跑策略回测校验，需 strategy_ids）
	*/
	async validatePool(poolId, params) {
		const body = {
			strategyIds: params.strategy_ids,
			startDate: params.start_date,
			endDate: params.end_date
		};
		const response = await this.client.post(`/api/pools/${poolId}/validate`, body);
		return this.unwrap(response.data, "validatePool");
	}
	/**
	* Scan-and-create pool（扫描筛选后自动建池，对齐后端 POST /api/pools/scan-and-create）
	*/
	async scanAndCreatePool(params) {
		const body = {
			name: params.name,
			poolType: params.pool_type,
			filterTemplate: params.filter_template,
			refreshInterval: params.refresh_interval ?? void 0,
			description: params.description,
			category: params.category
		};
		const response = await this.client.post("/api/pools/scan-and-create", body);
		return this.unwrap(response.data, "scanAndCreatePool");
	}
	/**
	* List signals
	*/
	async listSignals(params) {
		const response = await this.client.get("/api/signals", { params });
		return this.unwrap(response.data, "listSignals");
	}
	/**
	* Get real-time quote
	* Real endpoint: GET /api/stock/{symbol}/quote?source=auto
	* Response: {success, data: {symbol, name, price, open, high, low, prevClose, volume, amount, change, changePct, source, timestamp}}
	*/
	async getQuote(symbol, source = "auto") {
		const response = await this.client.get(`/api/stock/${symbol}/quote`, { params: { source } });
		return this.unwrap(response.data, "getQuote");
	}
	/**
	* Get market style
	* Real endpoint: GET /api/market/style
	* Real response data: {style, confidence, scores, indicators, recommendedFactors, detectionDate}
	*/
	async getMarketStyle() {
		const response = await this.client.get("/api/market/style");
		return this.unwrap(response.data, "getMarketStyle");
	}
	/**
	* Get macroeconomic data (GDP/CPI/PMI)
	* Real endpoint: GET /api/market/macro
	* Response: {success, data: {gdp: [...], cpi: [...], pmi: [...], updateTime}}
	*/
	async getMacroData() {
		const response = await this.client.get("/api/market/macro", { timeout: 6e4 });
		return this.unwrap(response.data, "getMacroData");
	}
	/**
	* Get north-bound capital flow
	* Real endpoint: GET /api/market/north-flow?start_date=&end_date=
	* Response: {success, data: [{tradeDate, netFlow, shNetFlow, szNetFlow}]}
	* Note: upstream data source is slow (~50s cold); uses an extended timeout.
	*/
	async getNorthFlow(startDate, endDate) {
		const response = await this.client.get("/api/market/north-flow", {
			params: {
				start_date: startDate,
				end_date: endDate
			},
			timeout: 9e4
		});
		return this.unwrap(response.data, "getNorthFlow");
	}
	/**
	* Get market sentiment
	* Real endpoint: GET /api/market/sentiment
	* Response: {success, data: {sentimentScore, sentimentLevel, fearGreedIndex, indicators, marketPhase, recommendation, ...}}
	*/
	async getMarketSentiment() {
		const response = await this.client.get("/api/market/sentiment");
		return this.unwrap(response.data, "getMarketSentiment");
	}
	/**
	* Get platform status (for quantsys_v2_status tool)
	*/
	async getPlatformStatus() {
		return (await this.client.get("/api/health/platform/status")).data.data;
	}
	/**
	* Get chip distribution
	*/
	async getChipDistribution(symbol) {
		const response = await this.client.get(`/api/analysis/chip-distribution/${symbol}`);
		return this.unwrap(response.data, "getChipDistribution");
	}
	/**
	* ZigZag 波段分析（买卖点识别）
	* Real endpoint: POST /api/analysis/swing-points
	* Body: { symbol, start_date?, end_date?, min_change? }
	* 响应为 camelCase（后端 convert_keys_to_camel）。
	* 2026-09-01 新增：后端路由原未注入 kline_repo 必 500，已修复。
	*/
	async analyzeSwingPoints(params) {
		const response = await this.client.post("/api/analysis/swing-points", {
			symbol: params.symbol,
			start_date: params.startDate,
			end_date: params.endDate,
			min_change: params.minChange
		});
		return this.unwrap(response.data, "analyzeSwingPoints");
	}
	/**
	* PE 历史分位
	* Real endpoint: GET /api/stock/{symbol}/pe-percentile
	* 响应 camelCase：currentPe/percentile/minPe/maxPe/meanPe/medianPe/dataPoints/years/interpretation
	*/
	async getPePercentile(symbol) {
		const response = await this.client.get(`/api/stock/${encodeURIComponent(symbol)}/pe-percentile`, { timeout: 6e4 });
		return this.unwrap(response.data, "getPePercentile");
	}
	/**
	* 个股分红历史
	* Real endpoint: GET /api/provider/dividend/{symbol}?years=N
	* ⚠️ 依赖 akshare，夜间/维护时段可能 All providers failed（调用方需容忍）
	*/
	async getDividends(symbol, years = 5) {
		const response = await this.client.get(`/api/provider/dividend/${encodeURIComponent(symbol)}`, {
			params: { years },
			timeout: 6e4
		});
		return this.unwrap(response.data, "getDividends");
	}
	/**
	* 高股息筛选
	* Real endpoint: GET /api/provider/screen-high-dividend?min_yield=3&min_years=5
	* ⚠️ 同样依赖 akshare，夜间可能不可用
	*/
	async screenHighDividend(params) {
		const response = await this.client.get("/api/provider/screen-high-dividend", {
			params: {
				min_yield: params?.minYield ?? 3,
				min_years: params?.minYears ?? 5
			},
			timeout: 12e4
		});
		return this.unwrap(response.data, "screenHighDividend");
	}
	/**
	* Get competition analysis
	*/
	async getCompetitionAnalysis(symbol, includeFinancial = true) {
		const response = await this.client.get(`/api/analysis/competition/${symbol}`, { params: { include_financial: includeFinancial } });
		return this.unwrap(response.data, "getCompetitionAnalysis");
	}
	/**
	* Get financial data
	* Response: existing .data.data || .data fallback works
	*/
	async getFinancialData(symbol, params) {
		const response = await this.client.get(`/api/v2/stock/${symbol}/financials`, { params: {
			statement_type: params?.statement_type || "all",
			periods: params?.periods || 4,
			source: params?.source || "auto"
		} });
		return response.data.data || response.data;
	}
	/**
	* Get financial statements (provider sina-statements, 真实报表数据)
	* Real endpoint: GET /api/provider/financial/{symbol}/sina-statements
	* 2026-08-30 新增：/api/v2/stock/{symbol}/financials 的 sina-web 指标源已失效
	* （全部返回 null），改用 DataProviderManager 的原始报表接口兜底。
	* 返回 { data_type, data: { income, balance, cashflow } }
	*/
	async getFinancialStatements(symbol) {
		const response = await this.client.get("/api/provider/financial/" + symbol + "/sina-statements");
		return this.unwrap(response.data, "getFinancialStatements");
	}
	/**
	* List watch rules
	* Real endpoint: GET /api/watch/rules
	* Response: {success, rules: [...]} - key is 'rules' not 'data'
	*/
	async listWatchRules(account) {
		const suffix = account ? `?account=${encodeURIComponent(account)}` : "";
		const response = await this.client.get(`/api/watch/rules${suffix}`);
		return this.unwrap(response.data, "listWatchRules");
	}
	/**
	* 盯盘触发记录（2026-09-11，w-c8cae280）
	*
	* 为什么需要：后端 /api/watch/rules 不返回 triggered_count，watch_list 工具层
	* 曾用 `?? 0` 兜底 → 53 条规则全部显示「从未触发」，而同一时刻 watch_triggers
	* 里规则 #135 当日已触发 4 次。这个假 0 直接造成「盯盘引擎失效」的误判。
	* 本方法提供真实计数的数据来源。
	* Response: {success, data: {triggers: [...]}}
	*/
	async listWatchTriggers(symbol, limit = 500) {
		const qs = new URLSearchParams();
		if (symbol) qs.set("symbol", symbol);
		qs.set("limit", String(limit));
		const response = await this.client.get(`/api/watch/triggers?${qs.toString()}`);
		const data = this.unwrap(response.data, "listWatchTriggers");
		return Array.isArray(data) ? data : data?.triggers ?? [];
	}
	/**
	* 待办列表
	* Real endpoint: GET /api/watch/todos
	* Response: {success, data: {items: [...], total: n}}
	* terminal 不传 = 只返回未收敛（闭环工作队列的默认视图）
	*/
	async listWatchTodos(params) {
		const qs = new URLSearchParams();
		const p = params ?? {};
		if (p.level) qs.set("level", p.level);
		if (p.flow_state) qs.set("flow_state", p.flow_state);
		if (p.account) qs.set("account", p.account);
		if (p.terminal) qs.set("terminal", p.terminal);
		if (p.limit !== void 0) qs.set("limit", String(p.limit));
		const suffix = qs.toString() ? `?${qs.toString()}` : "";
		const response = await this.client.get(`/api/watch/todos${suffix}`);
		const data = this.unwrap(response.data, "listWatchTodos");
		return Array.isArray(data) ? data : data?.items ?? [];
	}
	/**
	* 认领待办（L1→L2；仅未终态行生效）
	* Real endpoint: POST /api/watch/todos/{id}/claim
	* 失败：404 watch_todo_not_found / 409 watch_todo_already_closed
	*/
	async claimWatchTodo(todoId, ownerRef) {
		const response = await this.client.post(`/api/watch/todos/${todoId}/claim`, { owner_ref: ownerRef });
		const data = this.unwrap(response.data, "claimWatchTodo");
		return data?.todo ?? data;
	}
	/**
	* 收敛待办（终态校验在服务端）
	* Real endpoint: POST /api/watch/todos/{id}/close
	* Response: {success, data: {todo, receipt}}
	* 失败：400 watch_todo_invalid_terminal / watch_todo_missing_next_condition /
	*       watch_todo_missing_audit（L3 + trade|rule_change 缺 decision_audit_id）
	*/
	async closeWatchTodo(todoId, request) {
		const response = await this.client.post(`/api/watch/todos/${todoId}/close`, request);
		return this.unwrap(response.data, "closeWatchTodo");
	}
	/**
	* Get portfolio positions
	* 2026-08-31 修复：改调 /api/simulation/accounts/{account}（get_account_status），
	* 该接口每次请求实时拉行情刷新持仓价格并返回 price_stale / price_updated_at；
	* 原 /api/portfolio/positions 直读数据库 current_price 快照（陈旧价，曾导致 8/28 旧价）。
	* 响应为 snake_case，映射为工具层期望的 camelCase Position[]。
	*/
	async getPositions(accountName = DEFAULT_AGENT_ACCOUNT) {
		const response = await this.client.get(`/api/simulation/accounts/${encodeURIComponent(accountName)}`);
		const data = this.unwrap(response.data, "getPositions");
		return (Array.isArray(data.positions) ? data.positions : []).map((p) => this.mapPosition(p, data));
	}
	/**
	* Get portfolio summary
	* 2026-08-31 修复：同样改调 /api/simulation/accounts/{account}（实时刷新），
	* 原 /api/portfolio/summary 直读数据库快照（account.lastUpdated 曾停更在 8/28）。
	*/
	async getPortfolioSummary(accountName = DEFAULT_AGENT_ACCOUNT) {
		const response = await this.client.get(`/api/simulation/accounts/${encodeURIComponent(accountName)}`);
		const data = this.unwrap(response.data, "getPortfolioSummary");
		const positions = Array.isArray(data.positions) ? data.positions : [];
		const totalCost = positions.reduce((sum, p) => sum + (Number(p.avg_cost) || 0) * (Number(p.shares_total) || 0), 0);
		const marketValue = Number(data.position_value) || 0;
		const totalPnl = marketValue - totalCost;
		const cash = (Number(data.cash_available) || 0) + (Number(data.cash_frozen) || 0);
		return {
			accountName: String(data.account_name || accountName),
			totalValue: Number(data.total_value) || 0,
			totalCost,
			totalMarketValue: marketValue,
			totalPnl,
			totalPnlPct: totalCost > 0 ? Number((totalPnl / totalCost * 100).toFixed(2)) : 0,
			dailyChange: 0,
			positions: positions.length,
			cash,
			liquidAssets: cash,
			profitCount: positions.filter((p) => Number(p.profit_total) > 0).length,
			lossCount: positions.filter((p) => Number(p.profit_total) < 0).length,
			lastUpdated: data.last_updated || (/* @__PURE__ */ new Date()).toISOString(),
			priceStale: Boolean(data.price_stale)
		};
	}
	/**
	* 将 simulation 账户接口的 snake_case 持仓项映射为 Position（camelCase）
	*/
	mapPosition(p, account) {
		const quantity = Number(p.shares_total) || 0;
		const avgCost = Number(p.avg_cost) || 0;
		const currentPrice = Number(p.current_price) || avgCost;
		const marketValue = Number(p.market_value) || quantity * currentPrice;
		const totalCost = quantity * avgCost;
		const profitTotal = Number(p.profit_total) ?? marketValue - totalCost;
		const profitTotalRate = Number(p.profit_total_rate) ?? (totalCost > 0 ? profitTotal / totalCost : 0);
		return {
			symbol: String(p.symbol || ""),
			name: String(p.name || ""),
			quantity,
			sharesAvailable: Number(p.shares_available) ?? quantity,
			avgCost,
			currentPrice,
			totalCost,
			currentValue: marketValue,
			profitLoss: profitTotal,
			profitLossPct: Number((profitTotalRate * 100).toFixed(2)),
			profitToday: Number(p.profit_today) || 0,
			peakPrice: Number(p.peak_price) || 0,
			priceUpdatedAt: p.price_updated_at || account.last_updated || null,
			priceStale: Boolean(account.price_stale)
		};
	}
	/**
	* 读取投资脑 core 建仓计划（**只读**）。
	*
	* 返回 {available, unavailable_reason, freshness, plan, delta}：
	*   · plan      计划全文（与 config/core_plan.json 结构一致，**蛇形 key 原样返回**）
	*   · freshness 新鲜度（generated_at/data_date/is_stale/stale_reason）——
	*               直读文件时**看不出**计划陈不陈，周五的计划周一读出来一模一样
	*   · delta     目标组合 vs 当前持仓的机械差额（含 shares_available 供 T+1 校验）
	*
	* ⚠️ delta 不是委托清单：价格是计划时收盘价、未做 regime/止损复检、未做分批节奏。
	*    下单前仍须走 R-001/R-002。详见返回的 delta.caveats。
	* ⚠️ 不触发重新生成（生成参数集已审批）；补跑用 POST /api/scheduler/tasks/337/trigger。
	*/
	async getCorePlan(account) {
		const qs = new URLSearchParams();
		if (account) qs.set("account", account);
		const url = qs.toString() ? `/api/core-plan?${qs.toString()}` : "/api/core-plan";
		const response = await this.client.get(url);
		return this.unwrap(response.data, "getCorePlan");
	}
	async listPlans(account = DEFAULT_AGENT_ACCOUNT, status) {
		const qs = new URLSearchParams({ account });
		if (status) qs.set("status", status);
		const response = await this.client.get(`/api/plans?${qs.toString()}`);
		return this.unwrap(response.data, "listPlans");
	}
	async getPlan(planId) {
		const response = await this.client.get(`/api/plans/${planId}`);
		return this.unwrap(response.data, "getPlan");
	}
	async createPlan(payload) {
		const response = await this.client.post("/api/plans", payload);
		return this.unwrap(response.data, "createPlan");
	}
	async patchPlan(planId, payload) {
		const response = await this.client.patch(`/api/plans/${planId}`, payload);
		return this.unwrap(response.data, "patchPlan");
	}
	async applyPlan(planId, payload) {
		const response = await this.client.post(`/api/plans/${planId}/apply`, payload);
		return this.unwrap(response.data, "applyPlan");
	}
	async activatePlan(planId, payload = {}) {
		const response = await this.client.post(`/api/plans/${planId}/activate`, payload);
		return this.unwrap(response.data, "activatePlan");
	}
	async pausePlan(planId, payload = {}) {
		const response = await this.client.post(`/api/plans/${planId}/pause`, payload);
		return this.unwrap(response.data, "pausePlan");
	}
	async resumePlan(planId, payload = {}) {
		const response = await this.client.post(`/api/plans/${planId}/resume`, payload);
		return this.unwrap(response.data, "resumePlan");
	}
	async closePlan(planId, payload = {}) {
		const response = await this.client.post(`/api/plans/${planId}/close`, payload);
		return this.unwrap(response.data, "closePlan");
	}
	async compilePlanPreview(planId) {
		const response = await this.client.get(`/api/plans/${planId}/compile-preview`);
		return this.unwrap(response.data, "compilePlanPreview");
	}
	async plansToday(account = DEFAULT_AGENT_ACCOUNT) {
		const qs = new URLSearchParams({ account });
		const response = await this.client.get(`/api/plans/today?${qs.toString()}`);
		return this.unwrap(response.data, "plansToday");
	}
	async planStats(planId) {
		const response = await this.client.get(`/api/plans/${planId}/stats`);
		return this.unwrap(response.data, "planStats");
	}
	async recordPlanReflection(planId, payload) {
		const response = await this.client.post(`/api/plans/${planId}/reflections`, payload);
		return this.unwrap(response.data, "recordPlanReflection");
	}
	async listPlanReflections(planId) {
		const response = await this.client.get(`/api/plans/${planId}/reflections`);
		return this.unwrap(response.data, "listPlanReflections");
	}
	async blockedSignalStats(sinceDays = 30, horizon = 5) {
		const response = await this.client.get(`/api/watch/outcomes/blocked-stats?since_days=${sinceDays}&horizon=${horizon}`);
		return this.unwrap(response.data, "blockedSignalStats");
	}
	/**
	* Get evolution leaderboard
	* Real endpoint: GET /api/evolution/leaderboard
	* Response: {success, data: {windowEnd, windowDays, ranking: [...]}}
	*/
	async getEvolutionLeaderboard() {
		const response = await this.client.get("/api/evolution/leaderboard");
		return this.unwrap(response.data, "getEvolutionLeaderboard");
	}
	/**
	* Get evolution decision scores
	* Real endpoint: GET /api/evolution/decision-scores
	* Response: {success, data: {total, items: [...]}}
	*/
	async getEvolutionDecisionScores() {
		const response = await this.client.get("/api/evolution/decision-scores");
		return this.unwrap(response.data, "getEvolutionDecisionScores");
	}
	/**
	* Execute a trade (virtual account)
	* Real endpoint: POST /api/orders/create
	*/
	/**
	* Execute a trade（虚拟账户立即成交）
	* 2026-08-25 修复：改走 simulation 交易端点（/api/orders/create 属于订单管理系统，
	* 只建单不成交、不动虚拟账户持仓——卖出校验也查的是废弃 holdings 表）。
	* 正确端点：POST /api/simulation/accounts/{account}/trade（立即成交并更新持仓）。
	*/
	async executeTrade(params) {
		const account = params.account_name || DEFAULT_AGENT_ACCOUNT;
		const body = {
			action: params.action,
			symbol: params.symbol,
			shares: params.quantity,
			reason: params.reason && params.reason.length >= 10 ? params.reason : params.reason ? `${params.reason}（虚拟盘委托）` : "虚拟账户委托交易（未注明理由）"
		};
		if (params.price) body.price = params.price;
		if (params.genome_version) body.genome_version = params.genome_version;
		if (params.execute_at) body.execute_at = params.execute_at;
		if (params.price && params.execute_at) body.price_limit = params.price;
		if (params.allow_duplicate) body.allow_duplicate = true;
		const response = await this.client.post(`/api/simulation/accounts/${encodeURIComponent(account)}/trade`, body);
		const data = this.unwrap(response.data, "executeTrade");
		return {
			order_id: String(data.order_id ?? data.trade_id ?? data.pending_order_id ?? ""),
			action: data.action ?? params.action,
			symbol: data.symbol ?? params.symbol,
			quantity: Number(data.shares ?? params.quantity),
			price: Number(data.price ?? 0),
			amount: Number(data.amount ?? 0),
			status: data.status === "pending" ? "pending" : data.order_status ?? "filled",
			timestamp: data.timestamp ?? (/* @__PURE__ */ new Date()).toISOString(),
			...data.pending_order_id ? {
				pending_order_id: data.pending_order_id,
				message: data.message
			} : {}
		};
	}
	/**
	* 挂单列表（盘前挂单）
	* Real endpoint: GET /api/simulation/accounts/{account}/pending-orders?status=pending|all
	*/
	/**
	* 账户发现（2026-09-13 w-c8cae280）：列出账户 + 摘要。
	* 后端 GET /api/simulation/accounts?status=active → {accounts:[{account_name, display_name,
	* strategy_name, account_type, status, cash_available, cash_frozen, position_value,
	* total_value, cumulative_return, positions_count}], total}
	* 用途：让 agent **不必记住/写死账户名**——先查有哪些账户、哪个是本实例账户。
	*/
	async listAccounts(status = "active") {
		const response = await this.client.get("/api/simulation/accounts", { params: { status } });
		const data = this.unwrap(response.data, "listAccounts");
		const rows = Array.isArray(data) ? data : data?.accounts ?? [];
		return Array.isArray(rows) ? rows : [];
	}
	async listPendingOrders(accountName = DEFAULT_AGENT_ACCOUNT, status = "pending") {
		const response = await this.client.get(`/api/simulation/accounts/${encodeURIComponent(accountName)}/pending-orders`, { params: { status } });
		return this.unwrap(response.data, "listPendingOrders");
	}
	/**
	* 取消挂单（仅 pending 状态可取消）
	* Real endpoint: POST /api/simulation/accounts/{account}/pending-orders/{orderId}/cancel
	*/
	async cancelPendingOrder(accountName, orderId) {
		const response = await this.client.post(`/api/simulation/accounts/${encodeURIComponent(accountName)}/pending-orders/${orderId}/cancel`);
		return this.unwrap(response.data, "cancelPendingOrder");
	}
	/**
	* 记录决策
	* Real endpoint: POST /api/decisions/record
	* Body: { decision_type, reasoning, context?, parameters?, related_entity_type?, related_entity_id?, session_key? }
	*/
	async recordDecision(params) {
		const response = await this.client.post("/api/decisions/record", params);
		return this.unwrap(response.data, "recordDecision");
	}
	/**
	* 决策历史
	* Real endpoint: GET /api/decisions/history
	*/
	async getDecisionHistory(params) {
		const response = await this.client.get("/api/decisions/history", { params });
		return this.unwrap(response.data, "getDecisionHistory");
	}
	/**
	* 待评估决策（创建超过 days 天仍 pending）
	* Real endpoint: GET /api/decisions/pending
	*/
	async getPendingDecisions(days = 7) {
		const response = await this.client.get("/api/decisions/pending", { params: { days } });
		return this.unwrap(response.data, "getPendingDecisions");
	}
	/**
	* 触发决策评估（单笔或批量）
	* Real endpoint: POST /api/decisions/evaluate
	* Body: { decision_id? } 或 { days? }（批量）
	*/
	async evaluateDecisions(params) {
		const response = await this.client.post("/api/decisions/evaluate", params ?? {});
		return this.unwrap(response.data, "evaluateDecisions");
	}
	/**
	* 决策报告（按关联实体聚合统计）
	* Real endpoint: GET /api/decisions/report
	*/
	async getDecisionReport(entityType, entityId) {
		const response = await this.client.get("/api/decisions/report", { params: {
			entity_type: entityType,
			entity_id: entityId
		} });
		return this.unwrap(response.data, "getDecisionReport");
	}
	/**
	* ML 模型批量预测（上涨概率）
	* Real endpoint: POST /api/ml/predict  Body: { symbols: string[], model_type?, version? }
	* 注意：后端带上线门禁（test_accuracy<0.50 拒服，0.50~0.55 degraded 警告）；
	* 已知问题：DB 因子覆盖不足时输出恒等概率 0.4659（缺失补零），须关注 model_gate.level。
	*/
	async mlPredict(params) {
		const response = await this.client.post("/api/ml/predict", params, { timeout: 12e4 });
		return this.unwrap(response.data, "mlPredict");
	}
	/**
	* Get trade history
	* Real endpoint: GET /api/trades/list
	*/
	async getTradeHistory(params) {
		const response = await this.client.get("/api/simulation/trades", { params });
		return this.unwrap(response.data, "getTradeHistory");
	}
	/**
	* Execute algorithmic order (TWAP/VWAP)
	* Real endpoint: POST /api/orders/algo-execute
	*/
	async executeAlgo(params) {
		const { duration, ...rest } = params;
		const body = { ...rest };
		if (duration !== void 0) body.duration_minutes = duration;
		const response = await this.client.post("/api/orders/algo-execute", body);
		const raw = this.unwrap(response.data, "executeAlgo");
		return {
			algo_order_id: raw.orderId ?? raw.order_id ?? raw.algo_order_id,
			algo: raw.algo,
			symbol: raw.symbol,
			total_quantity: raw.parentQuantity ?? raw.parent_quantity ?? raw.total_quantity,
			filled_quantity: raw.filled_quantity ?? 0,
			avg_price: raw.avg_price ?? 0,
			slices: raw.childOrders ?? raw.child_orders ?? raw.slices ?? [],
			status: raw.status,
			side: raw.side,
			execution_stats: raw.executionStats ?? raw.execution_stats,
			parent_quantity: raw.parentQuantity ?? raw.parent_quantity,
			order_id: raw.orderId ?? raw.order_id
		};
	}
	/**
	* Verify trades (reconciliation)
	* Real endpoint: POST /api/risk/trade-verify
	*/
	async verifyTrades(params) {
		const response = await this.client.post("/api/risk/trade-verify", params ?? {});
		return this.unwrap(response.data, "verifyTrades");
	}
	/**
	* Manage watch rules (create/enable/disable/delete)
	* Real endpoints:
	*   POST   /api/watch/rules           (create)
	*   PATCH  /api/watch/rules/{id}      (enable/disable - update enabled field)
	*   DELETE /api/watch/rules/{id}      (delete)
	*/
	async manageWatchRule(params) {
		const { action, rule_id, condition, ...rest } = params;
		if (action === "list") return await this.listWatchRules();
		if (action === "create") {
			const conditions = params.conditions && params.conditions.length > 0 ? params.conditions : condition ? this.parseCondition(condition) : [];
			const { conditions: _omit, ...restClean } = rest;
			const body = {
				...restClean,
				conditions
			};
			const response = await this.client.post("/api/watch/rules", body);
			return this.unwrap(response.data, "manageWatchRule");
		}
		if (action === "enable") {
			const response = await this.client.patch(`/api/watch/rules/${rule_id}`, { enabled: true });
			return this.unwrap(response.data, "manageWatchRule");
		}
		if (action === "disable") {
			const response = await this.client.patch(`/api/watch/rules/${rule_id}`, { enabled: false });
			return this.unwrap(response.data, "manageWatchRule");
		}
		if (action === "delete") {
			const response = await this.client.delete(`/api/watch/rules/${rule_id}`);
			return this.unwrap(response.data, "manageWatchRule");
		}
		throw new Error(`Unknown watch rule action: ${action}`);
	}
	/**
	* Get market alerts
	* Real endpoint: GET /api/alerts/check
	*/
	async getAlerts(params) {
		const response = await this.client.get("/api/alerts/check", {
			params,
			timeout: 6e4
		});
		const raw = this.unwrap(response.data, "getAlerts");
		return (Array.isArray(raw) ? raw : []).map((a) => ({
			id: a.id ?? a.alert_id ?? "",
			level: a.level ?? "medium",
			title: a.title ?? "",
			description: a.description ?? a.message ?? "",
			symbol: a.symbol ?? (Array.isArray(a.symbols) ? a.symbols[0] : a.symbols),
			triggered_at: a.triggered_at ?? a.created_at ?? "",
			type: a.type,
			action: a.action,
			symbols: a.symbols,
			details: a.details
		}));
	}
	/**
	* Get sector analysis
	* Real endpoint: GET /api/market/sectors
	*/
	async getSectorAnalysis(params) {
		const response = await this.client.get("/api/market/sectors", { params });
		return this.unwrap(response.data, "getSectorAnalysis");
	}
	/**
	* Get sector constituent stocks（板块成分股，M2-1 主线→标的映射数据源）
	* Real endpoint: GET /api/market/sector/{sector:path}（sector 传中文板块名，如"白银"）
	* Response data: {sector, sectorCode, stocks: [{symbol, name, pe, marketCapBillion}], count}
	*/
	async getSectorStocks(sector) {
		const response = await this.client.get(`/api/market/sector/${encodeURIComponent(sector)}`);
		return this.unwrap(response.data, "getSectorStocks");
	}
	/**
	* Risk control: position_size / stop_loss / portfolio_risk
	* Dispatches to different endpoints based on command.
	*/
	async riskControl(params) {
		const { command, symbol, account_name, risk_level, price, entry_price } = params;
		if (command === "position_size") {
			const response = await this.client.post(`/api/stock/${symbol}/risk/position-size`, {
				account_name,
				price
			});
			return this.unwrap(response.data, "riskControl");
		}
		if (command === "stop_loss") {
			const response = await this.client.post(`/api/stock/${symbol}/risk/stop-loss`, {
				account_name,
				risk_level: risk_level || "large_cap",
				entry_price
			});
			return this.unwrap(response.data, "riskControl");
		}
		if (command === "portfolio_risk") {
			const response = await this.client.post("/api/risk/check", { account_name });
			return this.unwrap(response.data, "riskControl");
		}
		throw new Error(`Unknown risk control command: ${command}`);
	}
	/**
	* Calculate risk metrics
	* Real endpoint: POST /api/risk/metrics
	*/
	async getRiskMetrics(params) {
		const response = await this.client.post("/api/risk/metrics", params ?? {});
		return this.unwrap(response.data, "getRiskMetrics");
	}
	/**
	* 组合级回撤熔断状态读写（M4 硬拦截数据源，2026-09-10）
	* Real endpoints: GET/POST /api/risk/circuit-breaker
	*/
	async getCircuitBreaker(account_name) {
		const response = await this.client.get("/api/risk/circuit-breaker", { params: { account_name: account_name ?? DEFAULT_AGENT_ACCOUNT } });
		return this.unwrap(response.data, "getCircuitBreaker");
	}
	async setCircuitBreaker(params) {
		const response = await this.client.post("/api/risk/circuit-breaker", params);
		return this.unwrap(response.data, "setCircuitBreaker");
	}
	/**
	* Barra risk decomposition
	* Real endpoint: POST /api/factor-models/barra/calculate
	*/
	async getBarraDecomposition(params) {
		const response = await this.client.post("/api/factor-models/barra/calculate", params ?? {});
		return this.unwrap(response.data, "getBarraDecomposition");
	}
	/**
	* Generate trading signals
	* Real endpoint: POST /api/signals/scan
	*/
	async generateSignals(params) {
		const response = await this.client.post("/api/signals/scan", params);
		return this.unwrap(response.data, "generateSignals");
	}
	/**
	* Scan market opportunities
	* Real endpoint: POST /api/signals/scan
	*/
	async scanOpportunities(params) {
		const data = (await this.client.post("/api/signals/scan", params ?? {})).data;
		if (data?.success === false) throw new Error(data?.error || "API request failed: scanOpportunities");
		const list = data?.opportunities ?? data?.data ?? [];
		return Array.isArray(list) ? list : [];
	}
	/**
	* Screen stocks by filters
	* Real endpoint: GET /api/stocks/screen
	*/
	async screenStocks(params) {
		const { criteria, filters, sort_by, limit, ...rest } = params ?? {};
		const flat = { ...rest };
		const crit = {
			...criteria ?? {},
			...filters ?? {}
		};
		const rng = (key) => {
			const v = crit[key];
			if (Array.isArray(v) && v.length >= 2) return [v[0], v[1]];
			if (typeof v === "number") return [v, v];
			return [void 0, void 0];
		};
		const [peMin, peMax] = rng("pe");
		const [roeMin] = rng("roe");
		const [capMin, capMax] = rng("market_cap");
		const [, debtMax] = rng("debt_ratio");
		const [scoreMin] = rng("score");
		const [pbMax] = rng("pb");
		if (peMax != null) flat.max_pe = peMax;
		if (roeMin != null) flat.min_roe = roeMin;
		if (capMin != null) flat.min_market_cap = capMin;
		if (capMax != null) flat.max_market_cap = capMax;
		if (debtMax != null) flat.max_debt_ratio = debtMax;
		if (scoreMin != null) flat.min_score = scoreMin;
		if (pbMax != null) flat.max_pb = pbMax;
		if (sort_by) flat.sort_by = sort_by;
		if (limit) flat.limit = limit;
		if (crit.exclude_st !== void 0) flat.exclude_st = crit.exclude_st;
		const response = await this.client.get("/api/stocks/screen", { params: flat });
		return this.unwrap(response.data, "screenStocks");
	}
	/**
	* Generate rotation proposal
	* Real endpoint: GET /api/agent/rotation/proposal
	*/
	async generateRotationProposal(params) {
		const response = await this.client.get("/api/agent/rotation/proposal", { params });
		return this.unwrap(response.data, "generateRotationProposal");
	}
	/**
	* Simulate rotation proposal
	* Real endpoint: POST /api/agent/rotation/simulate
	*/
	async simulateRotation(params) {
		const { proposals, ...rest } = params;
		const response = await this.client.post("/api/agent/rotation/simulate", {
			actions: proposals ?? [],
			...rest
		});
		return this.unwrap(response.data, "simulateRotation");
	}
	/**
	* Execute rotation proposal
	* Real endpoint: POST /api/agent/rotation/execute
	*/
	async executeRotation(params) {
		const { proposals, ...rest } = params;
		const response = await this.client.post("/api/agent/rotation/execute", {
			actions: proposals ?? [],
			decision: "approve",
			reason: "agent rotation_execute",
			...rest
		});
		return this.unwrap(response.data, "executeRotation");
	}
	/**
	* Calculate stock factors
	* Real endpoint: GET /api/stock/{symbol}/factors
	*/
	async calculateFactors(params) {
		const response = await this.client.get(`/api/stock/${params.symbol}/factors`, { params: { factors: params.factors } });
		return this.unwrap(response.data, "calculateFactors");
	}
	/**
	* Analyze factor effectiveness
	* Real endpoint: POST /api/portfolio/factor-analyze
	*/
	async analyzeFactor(params) {
		const response = await this.client.post("/api/portfolio/factor-analyze", {
			factors: [params.factor_name],
			start_date: params.start_date,
			end_date: params.end_date
		});
		return this.unwrap(response.data, "analyzeFactor");
	}
	/**
	* 解析 agent 侧 model_id（如 "lightgbm_20260820_195134"）为后端所需的
	* model_type + version。裸类型名（如 "lightgbm"、"lgbm"）视为 latest。
	* 无法识别时抛错——禁止静默回退默认模型（RFC003-P3 验收发现）。
	*/
	parseModelId(modelId) {
		const alias = {
			lgbm: "lightgbm",
			lightgbm: "lightgbm",
			xgboost: "xgboost",
			randomforest: "randomforest",
			random_forest: "randomforest",
			neural_net: "neural_net"
		};
		const id = modelId.trim();
		for (const [prefix, canonical] of Object.entries(alias).sort((a, b) => b[0].length - a[0].length)) {
			if (id === prefix) return { model_type: canonical };
			if (id.startsWith(prefix + "_")) {
				const version = id.slice(prefix.length + 1);
				if (version) return {
					model_type: canonical,
					version
				};
			}
		}
		throw new Error(`无法解析 model_id "${modelId}"，正确格式如 lightgbm_20260820_195134（{model_type}_{version}）或裸类型名 lightgbm/xgboost`);
	}
	/**
	* 列出已注册模型
	* Real endpoint: GET /api/ml/models
	*/
	async listModels(params) {
		const response = await this.client.get("/api/ml/models", { params });
		return this.unwrap(response.data, "listModels");
	}
	/**
	* 选择默认模型：最新一个通过上线门禁（roc_auc >= 0.55, status=ready）的模型。
	* 无达标模型时返回 null，由后端默认路径兜底（RFC003-P3 门禁规则）。
	*/
	async resolveGatedDefaultModel() {
		try {
			const gated = ((await this.listModels({
				status: "ready",
				limit: 50
			}))?.models || []).filter((m) => typeof m.roc_auc === "number" && m.roc_auc >= .55 && m.train_date).sort((a, b) => String(b.train_date).localeCompare(String(a.train_date)));
			if (!gated.length) return null;
			return {
				model_type: gated[0].model_type,
				version: gated[0].version
			};
		} catch {
			return null;
		}
	}
	/**
	* Predict with ML model
	* Real endpoint: POST /api/ml/predict
	*/
	async predictWithModel(params) {
		let modelType;
		let version;
		if (params.model_id) {
			const parsed = this.parseModelId(params.model_id);
			modelType = parsed.model_type;
			version = parsed.version;
		} else {
			const gated = await this.resolveGatedDefaultModel();
			if (gated) {
				modelType = gated.model_type;
				version = gated.version;
			}
		}
		const response = await this.client.post("/api/ml/predict", {
			symbols: [params.symbol],
			...modelType ? { model_type: modelType } : {},
			...version ? { version } : {}
		});
		const result = this.unwrap(response.data, "predictWithModel");
		if (modelType) result.model_used = `${modelType}${version ? "_" + version : "@latest"}`;
		return result;
	}
	/**
	* Get data quality report
	* Real endpoint: GET /api/data/quality-report
	*/
	async getDataQualityReport(params) {
		const response = await this.client.get("/api/data/quality-report", { params });
		return this.unwrap(response.data, "getDataQualityReport");
	}
	/**
	* Data manager operations (status/refresh/cleanup/backup)
	* Real endpoint: POST /api/data/update
	*/
	async dataManager(params) {
		const response = await this.client.post("/api/data/update", params);
		return this.unwrap(response.data, "dataManager");
	}
	/**
	* Sync daily K-line data
	* Real endpoint: POST /api/data/sync-daily-klines
	*/
	async syncDailyKlines(params) {
		return (await this.client.post("/api/data/sync-daily-klines", params || {})).data;
	}
	/**
	* Get data sync status
	* Real endpoint: GET /api/data/sync-status
	*/
	async getDataSyncStatus() {
		return (await this.client.get("/api/data/sync-status")).data;
	}
	/**
	* Train ML model
	* Real endpoint: POST /api/ml/train
	*/
	async trainModel(params) {
		const response = await this.client.post("/api/ml/train", params);
		return this.unwrap(response.data, "trainModel");
	}
	/**
	* Evaluate ML model
	* Real endpoint: GET /api/ml/model/evaluate（后端参数为 model_type + version）
	* 注意：后端不支持按 test_period 重估，返回的是训练时落库的指标；
	* 未知 model_id 会明确报错（success=false），不再静默回退默认模型。
	*/
	async evaluateModel(params) {
		const parsed = this.parseModelId(params.model_id);
		const response = await this.client.get("/api/ml/model/evaluate", { params: {
			model_type: parsed.model_type,
			version: parsed.version || "latest"
		} });
		return this.unwrap(response.data, "evaluateModel");
	}
	/**
	* Opponent behavior analysis
	* Real endpoint: GET /api/game/market/opponent-behavior
	*/
	async getOpponentBehavior(params) {
		const response = await this.client.get("/api/game/market/opponent-behavior", { params });
		return this.unwrap(response.data, "getOpponentBehavior");
	}
	/**
	* Pool battlefield assessment
	* Real endpoint: GET /api/game/pools/{pool_id}/battlefield-assessment
	*/
	async getPoolBattlefield(params) {
		const response = await this.client.get(`/api/game/pools/${params.pool_id}/battlefield-assessment`);
		return this.unwrap(response.data, "getPoolBattlefield");
	}
	/**
	* Manipulation detection
	* Real endpoint: GET /api/game/market/manipulation-detect
	*/
	async detectManipulation(params) {
		const response = await this.client.get("/api/game/market/manipulation-detect", { params });
		return this.unwrap(response.data, "detectManipulation");
	}
	/**
	* Retail panic index (M7-2)
	* Real endpoint: GET /api/market/perception/panic-index
	*/
	async getRetailPanicIndex(params) {
		const url = params?.days != null ? "/api/market/perception/panic-index/series" : "/api/market/perception/panic-index";
		const response = await this.client.get(url, { params: params?.days != null ? { days: params.days } : params });
		return this.unwrap(response.data, "getRetailPanicIndex");
	}
	/**
	* Record a buy signal
	* Real endpoint: POST /api/signals/track
	* Body: {signal_date, symbol, grade, source, price, reason?}
	*/
	async recordSignal(params) {
		const response = await this.client.post("/api/signals/track", params);
		return this.unwrap(response.data, "recordSignal");
	}
	/**
	* Update signal performance (backfill 5/10/20-day returns)
	* Real endpoint: PUT /api/signals/track/update
	* Body: {signal_date?, lookback_days?}
	*/
	async updateSignalPerformance(params) {
		const response = await this.client.put("/api/signals/track/update", params ?? {});
		return this.unwrap(response.data, "updateSignalPerformance");
	}
	/**
	* Get signal statistics report
	* Real endpoint: GET /api/signals/track/report?start_date=&end_date=&grade=&source=
	*/
	async getSignalReport(params) {
		const response = await this.client.get("/api/signals/track/report", { params });
		return this.unwrap(response.data, "getSignalReport");
	}
	/**
	* 生成周报并推送到飞书（M6-2）
	*/
	async pushWeeklyReport(params) {
		const response = await this.client.post("/api/reports/weekly/push", null, { params });
		return this.unwrap(response.data, "pushWeeklyReport");
	}
	/**
	* 获取最新周报（M6-2）
	*/
	async getLatestWeeklyReport(format = "json") {
		const response = await this.client.get("/api/reports/weekly/latest", { params: { format } });
		return this.unwrap(response.data, "getLatestWeeklyReport");
	}
	/**
	* 查未来 N 天待处理事件（每日检查任务核心调用）
	*/
	async getUpcomingEvents(days = 2) {
		const response = await this.client.get("/api/events/upcoming", { params: { days } });
		return this.unwrap(response.data, "getUpcomingEvents");
	}
	/**
	* 范围查询事件日历（按日期区间/类型/状态/标的过滤）
	*/
	async listEvents(params) {
		const response = await this.client.get("/api/events", { params });
		return this.unwrap(response.data, "listEvents");
	}
	/**
	* 按 ID 查单个事件
	*/
	async getEvent(id) {
		const response = await this.client.get(`/api/events/${id}`);
		return this.unwrap(response.data, "getEvent");
	}
	/**
	* 创建/更新事件（幂等 upsert：按类型+日期+标题去重）
	*/
	async upsertEvent(event) {
		const response = await this.client.post("/api/events", event);
		return this.unwrap(response.data, "upsertEvent");
	}
	/**
	* 更新事件（状态/结果/影响评估）
	*/
	async updateEvent(id, updates) {
		const response = await this.client.patch(`/api/events/${id}`, updates);
		return this.unwrap(response.data, "updateEvent");
	}
	/**
	* 标记事件状态（状态机：pending→notified→collected→reviewed/skipped）
	*/
	async markEventStatus(id, status, metaPatch) {
		const payload = { status };
		if (metaPatch) payload.meta = metaPatch;
		const response = await this.client.patch(`/api/events/${id}`, payload);
		return this.unwrap(response.data, "markEventStatus");
	}
	/**
	* 删除事件
	*/
	async deleteEvent(id) {
		const response = await this.client.delete(`/api/events/${id}`);
		return this.unwrap(response.data, "deleteEvent");
	}
	/** 事件流（按 scope/type/日期过滤） */
	async getEventsFeed(params = {}) {
		return (await this.client.get("/api/events/feed", { params }).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 执行质量报表：决策价 vs 成交价的滑点（2026-09-13 w-a9ec14d7，M5 闭环） */
	async getSlippageReport(accountName = DEFAULT_AGENT_ACCOUNT, params = {}) {
		return (await this.client.get("/api/simulation/accounts/" + encodeURIComponent(accountName) + "/slippage-report", { params }).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 事件 → 盯盘规则建议（前瞻日历；2026-09-13 w-a9ec14d7 补上消费端） */
	async getEventWatchSuggestions(params = {}) {
		return (await this.client.get("/api/events/watch-suggestions", { params }).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 把任务派给处置 agent（2026-10-20）：统一信封 + 交付要求 + 留痕；返回 wake 状态 */
	async dispatchAgentTask(params) {
		return (await this.client.post("/api/agent/dispatch", params).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 条件入参契约（2026-10-20 框架适配）：全部条件类型参数说明/单位/示例 + market_gate 规格 */
	async getWatchConditionSchema() {
		return (await this.client.get("/api/watch/rules/condition-schema").catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 单标的盯盘简报（2026-10-20）：行情+成本+规则距离+未决触发+近48h消息命中，一张卡 */
	async getWatchBrief(symbol) {
		return (await this.client.get("/api/watch/brief", { params: { symbol } }).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 盯盘触发增量查询（2026-10-20）：since 之后的新触发（agent 轮询「有什么新信号」） */
	async getWatchTriggers(params = {}) {
		return (await this.client.get("/api/watch/triggers", { params }).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 处置触发（2026-10-20 框架适配）：handled/ignored 收敛未决触发——agent 的处置动作 */
	async resolveWatchTrigger(triggerId, body) {
		return (await this.client.patch(`/api/watch/triggers/${triggerId}`, body).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 个股事件（公告/解禁/财报/股东会/减持…）——买入前排雷 */
	async getSymbolEvents(symbol, params = {}) {
		return (await this.client.get(`/api/events/symbol/${symbol}`, { params }).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 分钟线（多源故障转移：腾讯/东财/新浪 + 本地 DB 兜底） */
	async getMinuteKlines(symbol, params = {}) {
		return (await this.client.get(`/api/stocks/${symbol}/minute-klines`, { params }).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 交易状态（ST/停牌/涨跌停/可交易性——下单前硬校验） */
	async getTradingStatus(symbol) {
		return (await this.client.get(`/api/stocks/${symbol}/trading-status`).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 执行预估（参与率/滑点/冲击成本，供 R-003 拆单参考） */
	async estimateExecution(payload) {
		return (await this.client.post("/api/execution/estimate", payload).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 个股资金流（主力/大单/中单/小单净流入） */
	async getStockFundFlow(symbol, days = 5) {
		return (await this.client.get(`/api/stock/${symbol}/fund-flow`, { params: { days } }).catch((e) => ({ data: {
			success: false,
			error: e.message
		} }))).data;
	}
	/** 板块资金流 */
	async getSectorFlow() {
		return (await this.client.get("/api/market/sector-flow").catch((e) => ({ data: {
			success: false,
			error: e.message
		} }))).data;
	}
	/** 个股融资融券（杠杆资金） */
	async getStockMargin(symbol, days = 5) {
		return (await this.client.get(`/api/stock/${symbol}/margin`, { params: { days } }).catch((e) => ({ data: {
			success: false,
			error: e.message
		} }))).data;
	}
	/** 产业链清单 */
	async getIndustryChains() {
		return (await this.client.get("/api/industry-chains").catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 单条产业链全貌（按环节分组的成员 + evidence/confidence） */
	async getIndustryChain(name) {
		return (await this.client.get(`/api/industry-chains/${encodeURIComponent(name)}`).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 个股所属产业链与环节（链式扫描的关键查询） */
	async getStockChain(symbol) {
		return (await this.client.get(`/api/stocks/${symbol}/chain`).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 链式扫描：按环节分组 + 可选挂实时行情 */
	async scanIndustryChain(name, params = {}) {
		return (await this.client.post(`/api/industry-chains/${encodeURIComponent(name)}/scan`, params).catch((err) => ({ data: {
			success: false,
			error: err.message
		} }))).data;
	}
	/** 指数成分股（如 000300 → 沪深300 成分代码列表） */
	async getIndexConstituents(symbol) {
		return (await this.client.get(`/api/provider/index/${symbol}/constituents`).catch((e) => ({ data: {
			success: false,
			error: e.message
		} }))).data;
	}
	/**
	* 记忆召回审计统计（quantsys-v2 /api/memory/recall-audit/stats）
	* 注意：该端点返回**裸 JSON**（非 {success,data} 包裹），此处不做 unwrap。
	*/
	async getRecallAuditStats(params = {}) {
		return (await this.client.get("/api/memory/recall-audit/stats", { params }).catch((e) => ({ data: {
			success: false,
			error: e.message
		} }))).data;
	}
	/**
	* 记忆召回审计明细（quantsys-v2 /api/memory/recall-audit）
	* 返回 { items: [...], ... }，同样为裸 JSON。
	*/
	async getRecallAudit(params = {}) {
		return (await this.client.get("/api/memory/recall-audit", { params }).catch((e) => ({ data: {
			success: false,
			error: e.message
		} }))).data;
	}
	/** 龙虎榜：某日上榜记录 */
	async getLhbDaily(date) {
		return (await this.client.get(`/api/provider/lhb/daily/${date}`).catch((e) => ({ data: {
			success: false,
			error: e.message
		} }))).data;
	}
	/** 龙虎榜：个股上榜明细 */
	async getLhbDetail(symbol) {
		return (await this.client.get(`/api/provider/lhb/detail/${symbol}`).catch((e) => ({ data: {
			success: false,
			error: e.message
		} }))).data;
	}
	/** 涨停池（某日涨停股+连板/封单） */
	async getLimitUpPool(date) {
		return (await this.client.get(`/api/provider/zt-pool/${date}`).catch((e) => ({ data: {
			success: false,
			error: e.message
		} }))).data;
	}
	/** 个股公告 */
	async getStockAnnouncements(symbol) {
		return (await this.client.get(`/api/provider/stock/${symbol}/announcements`).catch((e) => ({ data: {
			success: false,
			error: e.message
		} }))).data;
	}
	/** 个股新闻 */
	async getStockNews(symbol) {
		return (await this.client.get(`/api/provider/stock/${symbol}/news`).catch((e) => ({ data: {
			success: false,
			error: e.message
		} }))).data;
	}
	/** 内部人交易（高管增减持） */
	async getInsiderTrades(symbol) {
		return (await this.client.get(`/api/provider/stock/${symbol}/insider-trades`).catch((e) => ({ data: {
			success: false,
			error: e.message
		} }))).data;
	}
	/** 交易日历
	*
	* 2026-09-10 修复（investor / w-8f2c4cc5）：必须传日期窗口——不传时后端 Provider
	* 收到空区间返回 data:[]，调用方（trading_calendar 工具）会静默降级成"周末排除法"，
	* 实测把 2026-10-01 国庆误判为交易日。缺省时后端已给 ±1 年窗口，显式传更可控。
	*/
	async getTradingCalendar(startDate, endDate) {
		const params = {};
		if (startDate) params.start_date = startDate;
		if (endDate) params.end_date = endDate;
		return (await this.client.get("/api/provider/trading-calendar", { params }).catch((e) => ({ data: {
			success: false,
			error: e.message
		} }))).data;
	}
	/**
	* 跑一轮真实回测进化（参数网格 → 逐变体回测 → 同批 fitness 归一 → 落库）
	* Real endpoint: POST /api/evolution/engine/run
	* 请求/响应均为 camelCase；dataSource=qv2_real（真回测）| degraded（诚实降级，无占位数字）
	*/
	async evolutionRunStrategy(request) {
		const response = await this.client.post("/api/evolution/engine/run", request);
		return this.unwrap(response.data, "evolutionRunStrategy");
	}
	/**
	* 策略最近进化结果行（每 run 一条 = fitness 最优变体行；leaderboard 数据源）
	* Real endpoint: GET /api/evolution/engine/runs?strategy_id=&limit=
	*/
	async getStrategyEvolutionRuns(strategyId, limit = 50) {
		const response = await this.client.get("/api/evolution/engine/runs", { params: {
			strategy_id: strategyId,
			limit
		} });
		return this.unwrap(response.data, "getStrategyEvolutionRuns");
	}
};
//#endregion
//#region src/manipulation.ts
/**
* 检测个股操纵嫌疑（拉高出货、对倒交易、诱多诱空等）
* 
* 基于 K 线行为特征计算嫌疑评分（0-100），越高嫌疑越大。
* 
* @param qv2 - QuantsysV2Client 实例
* @param symbol - 股票代码（如 600519）
* @param days - 分析窗口（默认 30 天）
* @returns 嫌疑评分、检测模式、证据列表、操作建议
*/
async function detectManipulation(qv2, symbol, days = 30) {
	const end = /* @__PURE__ */ new Date();
	const start = /* @__PURE__ */ new Date(end.getTime() - Math.max(days, 30) * 2 * 864e5);
	const fmt = (d) => d.toISOString().slice(0, 10);
	const klines = await qv2.getKlines(symbol, fmt(start), fmt(end), "daily");
	if (!klines || klines.length < 10) return {
		symbol,
		manipulation_score: 0,
		risk_level: "unknown",
		recommendation: "watch",
		detected_patterns: [],
		evidence: [`K线数据不足（${klines?.length ?? 0} 根），无法评估`],
		window_days: 0
	};
	const bars = klines.slice(-Math.max(days, 20));
	const last20 = klines.slice(-20);
	let score = 0;
	const patterns = [];
	const evidence = [];
	const pct = (a, b) => (b - a) / a * 100;
	const close0 = last20[0].close;
	const closeN = last20[last20.length - 1].close;
	const avgVol20 = last20.reduce((sum, k) => sum + (k.volume || 0), 0) / 20;
	const chg20 = pct(close0, closeN);
	if (chg20 > 50) {
		score += 25;
		patterns.push("短期暴涨");
		evidence.push(`近20日涨幅 ${chg20.toFixed(1)}% > 50%`);
	}
	let limitUps = 0;
	for (let i = 1; i < bars.length; i++) if (pct(bars[i - 1].close, bars[i].close) >= 9.9) limitUps++;
	if (limitUps >= 3) {
		score += 20;
		patterns.push("连续涨停");
		evidence.push(`窗口内涨停 ${limitUps} 次（≥3）`);
	}
	let extremeAmp = 0;
	for (let i = 1; i < bars.length; i++) if ((bars[i].high - bars[i].low) / bars[i - 1].close * 100 > 15) extremeAmp++;
	if (extremeAmp >= 2) {
		score += 15;
		patterns.push("极端振幅");
		evidence.push(`单日振幅>15% 出现 ${extremeAmp} 次`);
	}
	let volSpikes = 0;
	for (const k of bars) if (avgVol20 > 0 && (k.volume || 0) / avgVol20 > 5) volSpikes++;
	if (volSpikes >= 2) {
		score += 15;
		patterns.push("异常放量");
		evidence.push(`量比>5 的异常放量 ${volSpikes} 日（对倒嫌疑）`);
	}
	let dumpDays = 0;
	for (let i = 1; i < bars.length; i++) {
		const drop = pct(bars[i - 1].close, bars[i].close);
		const volRatio = avgVol20 > 0 ? (bars[i].volume || 0) / avgVol20 : 0;
		if (drop <= -7 && volRatio > 2) dumpDays++;
	}
	if (dumpDays >= 1) {
		score += 15;
		patterns.push("放量急跌");
		evidence.push(`放量急跌（≤-7%且量比>2）${dumpDays} 日`);
	}
	let opportunity = false;
	const last5 = klines.slice(-5);
	if (chg20 < -30 && last5.length === 5) {
		const amp5 = (Math.max(...last5.map((k) => k.high)) - Math.min(...last5.map((k) => k.low))) / closeN * 100;
		if (amp5 < 10) {
			opportunity = true;
			patterns.push("崩盘后企稳");
			evidence.push(`20日跌幅 ${chg20.toFixed(1)}%，近5日振幅收敛至 ${amp5.toFixed(1)}%——操纵崩盘后的潜在机会窗口`);
		}
	}
	return {
		symbol,
		manipulation_score: Math.min(100, score),
		risk_level: score > 70 ? "high" : score >= 40 ? "medium" : "low",
		recommendation: opportunity ? "opportunity" : score > 70 ? "avoid" : score >= 40 ? "watch" : "normal",
		detected_patterns: patterns,
		evidence: evidence.length > 0 ? evidence : ["未发现显著操纵特征"],
		window_days: bars.length,
		note: "本地 K 线行为特征评分（M2-2 共享库）"
	};
}
//#endregion
export { QuantsysV2Client, detectManipulation };
