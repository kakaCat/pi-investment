//#region src/client/banner.ts
const TEXT = {
	offline: "服务重启中，正在自动重连…… 此期间发送的消息可能发不出去，请稍候",
	stalePending: "服务已重启（代码可能已更新），你停手后页面会自动刷新",
	staleManual: "服务已重启，当前页面的登录已失效。请重新运行 ./scripts/url.sh 获取新链接，或关闭此标签页"
};
/**
* 创建横幅（纯 DOM，无 React）。
* @param onReload - 点"立即刷新"时调用。
*/
function createBanner(onReload) {
	const bar = document.createElement("div");
	bar.className = "dsh-wlv-bar";
	bar.dataset.phase = "ok";
	bar.setAttribute("role", "status");
	const text = document.createElement("span");
	text.className = "dsh-wlv-text";
	const button = document.createElement("button");
	button.className = "dsh-wlv-action";
	button.type = "button";
	button.textContent = "立即刷新";
	button.addEventListener("click", onReload);
	bar.appendChild(text);
	bar.appendChild(button);
	document.body.appendChild(bar);
	return {
		render(phase, options) {
			if (phase === "ok") {
				bar.dataset.phase = "ok";
				return;
			}
			text.textContent = phase === "offline" ? TEXT.offline : options?.pending === true ? TEXT.stalePending : TEXT.staleManual;
			bar.dataset.phase = phase;
		},
		dispose() {
			button.removeEventListener("click", onReload);
			bar.remove();
		}
	};
}
//#endregion
//#region src/client/styles.ts
/**
* web-liveness 样式：一条顶部常驻横幅（`.dsh-wlv-*` 命名空间，单份 <style> 注入）。
* 配色对齐壳的 --dsw-* token，取不到时退回固定色，保证任何主题下都读得清。
*
* @module web-liveness/client/styles
*/
const STYLES = `
.dsh-wlv-bar {
  position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
  z-index: 10050; display: none; align-items: center; gap: 10px;
  max-width: min(88vw, 720px); padding: 8px 14px;
  border-radius: 8px; font-size: 12.5px; line-height: 1.5;
  box-shadow: 0 4px 16px rgba(0, 0, 0, .22);
  color: #fff; background: #303133;
}
.dsh-wlv-bar[data-phase="offline"] { display: flex; background: #b88230; }
.dsh-wlv-bar[data-phase="stale"] { display: flex; background: #2f6fbf; }
.dsh-wlv-text { flex: 1 1 auto; }
.dsh-wlv-action {
  flex: none; border: 1px solid rgba(255, 255, 255, .55); border-radius: 6px;
  background: rgba(255, 255, 255, .14); color: #fff; font: inherit;
  padding: 3px 10px; cursor: pointer;
}
.dsh-wlv-action:hover { background: rgba(255, 255, 255, .26); }
`;
const STYLE_ID = "dsh-wlv-styles";
/** 注入样式一次（重复调用/重复 apply 都安全）。 */
function injectStyles() {
	if (document.getElementById(STYLE_ID) !== null) return;
	const style = document.createElement("style");
	style.id = STYLE_ID;
	style.textContent = STYLES;
	(document.head ?? document.documentElement).appendChild(style);
}
/** 两次自动刷新之间的最小间隔；防止"刷新后仍拿到旧 HTML"造成的刷新死循环。 */
const RELOAD_GUARD_MS = 15e3;
/** detection 之后轮询"现在能不能刷"的间隔。 */
const RELOAD_POLL_MS = 1e3;
/** offline 横幅的显示宽限：短到看不见的抖动不闪横幅。 */
const OFFLINE_GRACE_MS = 1e3;
/**
* 开机自检的探测时机：页面加载后等这么久，让页面自己的启动读取先跑完再下结论。
*
* 背景（2026-09-22 用户事故）：页面在服务未完全就绪的瞬间加载，框架的**一次性读取**
* （cordis 插件清单 / 模型列表 / 设置）失败且永不重试 —— 插件页、设置页空白、模型
* 选择器不加载、输入发不出去，且此时 rev 与进程一致，SSE 比对不会触发任何刷新。
* 探测目标与插件页同源（`POST /api/dynamicCordisRunner/inventory`）：它失败 ⟹ 页面
* 自己的启动读取也几乎必然失败过 ⟹ 这页已经半初始化，唯一修复是重载。
*/
const BOOT_CHECK_DELAY_MS = 8e3;
/**
* 单次探测的超时。必须设：启动窗口内加载的页面，其请求会在服务端**永不返回**
* （僵尸连接，2026-09-22 探针实测复现）——没有超时的 fetch 既不通过也不失败，
* 自检形同虚设。本地服务 5s 不响应即视为僵尸/未就绪。
*/
const BOOT_PROBE_TIMEOUT_MS = 5e3;
/**
* 开机自检判定。
* @param phase - 当前 SSE 相位（仅 `ok` = 同进程确认后才探测；其余相位自有流程接管）。
* @param probeOk - 对 RPC 层的探测是否成功（fetch 网络错误或非 2xx 都算失败）。
*/
function bootCheckDecision(phase, probeOk) {
	if (phase !== "ok") return "skip";
	return probeOk ? "healthy" : "reload";
}
/**
* 读取页面加载时注入的 boot graph 版本号。
* @param boot - `window.__DSH_BOOT__` 的原始值（形状随框架版本可能变，一律宽容读取）。
* @returns rev 字符串；读不到则 undefined（调用方据此退化为"只提示、不刷新"）。
*/
function bootRevOf(boot) {
	if (typeof boot !== "object" || boot === null) return void 0;
	const rev = boot.rev;
	return typeof rev === "string" && rev !== "" ? rev : void 0;
}
/**
* 解析一帧 SSE data。
* @param raw - `MessageEvent.data` 原文。
* @returns 帧对象；非 JSON、非对象、缺 `type` 时返回 undefined。
*/
function parseFrame(raw) {
	let parsed;
	try {
		parsed = JSON.parse(raw);
	} catch {
		return;
	}
	if (typeof parsed !== "object" || parsed === null) return void 0;
	const record = parsed;
	if (typeof record.type !== "string") return void 0;
	const graph = record.graph;
	const rev = typeof graph === "object" && graph !== null && typeof graph.rev === "string" ? graph.rev : void 0;
	return rev === void 0 ? { type: record.type } : {
		type: record.type,
		rev
	};
}
/**
* 判定一帧 graph 该做什么。
* @param bootRev - 页面加载时的 rev（`bootRevOf` 的结果）。
* @param graphRev - 刚收到的 graph 帧的 rev。
* @returns 见 {@link GraphDecision}；任一 rev 读不到时一律 `ignore`（信息不足时不动比乱刷安全）。
*/
function decideGraph(bootRev, graphRev) {
	if (bootRev === void 0 || graphRev === void 0) return "ignore";
	return bootRev === graphRev ? "recover" : "reload";
}
/**
* 现在是否可以自动刷新：页面在后台（没人在看）或用户已停顿足够久。
* @param hidden - `document.hidden`。
* @param lastInputAt - 最后一次用户输入的时间戳（ms）。
* @param now - 当前时间戳（ms）。
* @param quietMs - 停顿阈值，默认 {@link DEFAULT_QUIET_MS}。
*/
function shouldReloadNow(opts) {
	if (opts.hidden) return true;
	return opts.now - opts.lastInputAt >= (opts.quietMs ?? 5e3);
}
/**
* 刷新防抖闸门：距上次自动刷新不足 {@link RELOAD_GUARD_MS} 就拒绝再刷。
* @param lastReloadAt - 上次自动刷新的时间戳；从未刷过传 undefined。
* @param now - 当前时间戳（ms）。
* @param guardMs - 闸门宽度，默认 {@link RELOAD_GUARD_MS}。
*/
function reloadAllowed(lastReloadAt, now, guardMs = RELOAD_GUARD_MS) {
	if (lastReloadAt === void 0 || !Number.isFinite(lastReloadAt)) return true;
	return now - lastReloadAt >= guardMs;
}
//#endregion
//#region src/client/index.ts
/**
* @pi-investment/web-liveness · client 半（浏览器端）。
*
* 解决的事故（2026-09-16）：**服务端一重启，已经打开的标签页就"废"了** ——
* 页面能开、消息发不出去、只能手动开新标签页。根因不是鉴权（cookie 跨重启有效），
* 而是**没有任何机制在重启后刷新页面**：
*   - 客户端 bundle 是 `Cache-Control: immutable` + `?rev=<进程 nonce>`，唯一能发现新版的
*     入口是 index.html，而没人去重新拉它；
*   - 框架自带的 HMR 只在**进程运行期间**发现 bundle 被改写才推 `rebuilt`，重启后不补发；
*   - 我们自己的 5 个页面插件都只做裸 fetch 轮询，没有任何 reload / 重连感知。
*
* 本插件订阅框架在 `/plugins/events` 上的免鉴权 SSE（连上即推一帧 `graph`），把它的
* `graph.rev` 与页面加载时注入的 `window.__DSH_BOOT__.rev` 比对：
*   - 相同 → 同一进程（含同进程断线重连）→ 不做任何事；
*   - 不同 → 服务端换过进程或 bundle 换过版 → 刷新页面（等用户停手后自动刷，也能手动点）；
*   - 连不上 → 顶部横幅提示"服务重启中"，避免用户对着发不出去的消息干等。
*
* 判定逻辑全在 `watch.ts`（纯函数、有单测），本文件只做副作用编排。
* @module web-liveness/client
*/
const name = "@pi-investment/web-liveness/client";
const inject = [];
/** 上次自动刷新的时间戳（sessionStorage 跨 reload 保留 —— 刷新死循环的唯一闸门）。 */
const RELOAD_MARK_KEY = "dsh-wlv-reload-at";
/** 免鉴权的 HMR/插件事件流；连上即推当前进程的 graph 帧。 */
const EVENTS_PATH = "/plugins/events";
/**
* 开机自检的探测端点：插件页的数据源 RPC。它失败 ⟹ 页面启动时框架的一次性读取
* （插件清单/模型/设置）也失败过 ⟹ 页面半初始化（空白插件页/模型不加载/输入发不出）。
*/
const BOOT_PROBE_PATH = "/api/dynamicCordisRunner/inventory";
const LOG = "[web-liveness]";
/** 读 sessionStorage（隐私模式等场景会抛，一律降级为 undefined）。 */
function readReloadMark() {
	try {
		const raw = window.sessionStorage.getItem(RELOAD_MARK_KEY);
		if (raw === null) return void 0;
		const value = Number(raw);
		return Number.isFinite(value) ? value : void 0;
	} catch {
		return;
	}
}
function writeReloadMark(now) {
	try {
		window.sessionStorage.setItem(RELOAD_MARK_KEY, String(now));
	} catch {}
}
/** 用户还在不在打字：这些事件任一发生就更新"最后活动时刻"。 */
const INPUT_EVENTS = [
	"keydown",
	"input",
	"compositionstart",
	"paste",
	"pointerdown"
];
function apply(ctx) {
	try {
		injectStyles();
		window.__dshWlvClient?.dispose?.();
		const log = ctx.logger?.("@pi-investment/web-liveness/client") ?? {
			info: () => {},
			warn: () => {}
		};
		const bootRev = bootRevOf(window.__DSH_BOOT__);
		if (bootRev === void 0) log.warn(`${LOG} window.__DSH_BOOT__.rev 读不到：只保留"服务重启中"提示，不做自动刷新`);
		let lastInputAt = Date.now();
		const markInput = () => {
			lastInputAt = Date.now();
		};
		for (const type of INPUT_EVENTS) document.addEventListener(type, markInput, true);
		const startedAt = Date.now();
		let phase = "ok";
		let everFramed = false;
		let reloadScheduled = false;
		/** 防抖闸门已拦下一次自动刷新 —— 本页生命周期内不再自动刷（防死循环）。 */
		let reloadBlocked = false;
		let reloadPoll;
		let offlineGrace;
		let bootCheck;
		const banner = createBanner(() => {
			reload();
		});
		const setPhase = (next, options) => {
			if (next !== phase) {
				log.info(`${LOG} ${phase} → ${next}`);
				phase = next;
			}
			banner.render(next, options);
		};
		/** 真正刷新（唯一的 location.reload 出口）。
		*
		* 重启后 token 已失效，刷新会导致鉴权失败。
		* 解决：禁用自动刷新，只显示横幅提示用户获取新链接。
		*/
		function reload() {
			writeReloadMark(Date.now());
			if (new URL(window.location.href).searchParams.has("token")) {
				log.warn(`${LOG} 检测到服务重启但使用 token 鉴权，禁用自动刷新以避免 401`);
				reloadBlocked = true;
				setPhase("stale");
				return;
			}
			window.location.reload();
		}
		/** 停掉"等用户停手"的轮询。 */
		const stopReloadPoll = () => {
			if (reloadPoll !== void 0) {
				window.clearInterval(reloadPoll);
				reloadPoll = void 0;
			}
		};
		/** stale 态：等一个可以刷新的时机（后台标签 / 用户停手 且 不在防抖窗口内）。 */
		const startReloadPoll = () => {
			if (reloadScheduled || reloadBlocked) return;
			reloadScheduled = true;
			const tick = () => {
				const now = Date.now();
				if (!reloadAllowed(readReloadMark(), now, 15e3)) {
					stopReloadPoll();
					reloadBlocked = true;
					log.warn(`${LOG} 距上次自动刷新不足 ${String(RELOAD_GUARD_MS)}ms，改为提示手动刷新`);
					setPhase("stale");
					return;
				}
				if (shouldReloadNow({
					hidden: document.hidden,
					lastInputAt,
					now,
					quietMs: 5e3
				})) {
					stopReloadPoll();
					log.info(`${LOG} 服务端已换版本，刷新页面`);
					reload();
					return;
				}
				setPhase("stale", { pending: true });
			};
			reloadPoll = window.setInterval(tick, RELOAD_POLL_MS);
			tick();
		};
		/**
		* 开机自检：页面加载后探测一次 RPC 层。覆盖的场景是"页面在服务未完全就绪的瞬间
		* 加载"——rev 与进程一致（SSE 不会触发刷新），但框架的一次性读取已失败且永不重试，
		* 表现为插件/设置页空白、模型不加载、输入发不出去（2026-09-22 用户事故）。
		* 更糟的是该场景下请求会**永不返回**（僵尸连接，探针实测）：浏览器 6 条连接被占死后
		* 整个浏览器对本站饿死。所以探测必须带超时，超时一律按失败处理；触发的重载会在
		* 页面导航时拆掉本标签页的僵尸连接，连接池随之解放。
		* 只在 phase === 'ok'（同进程确认）时探测：offline/stale 自有流程接管，避免
		* "服务重启中把页面刷到浏览器错误页"。探测失败 ⟹ 页面半初始化 ⟹ 重载（受防抖闸门）。
		*/
		const runBootCheck = async () => {
			let probeOk = false;
			const controller = new AbortController();
			const timeout = window.setTimeout(() => {
				controller.abort();
			}, BOOT_PROBE_TIMEOUT_MS);
			try {
				probeOk = (await window.fetch(BOOT_PROBE_PATH, {
					method: "POST",
					headers: { "content-type": "application/json" },
					body: "{}",
					signal: controller.signal
				})).ok;
			} catch {
				probeOk = false;
			} finally {
				window.clearTimeout(timeout);
			}
			switch (bootCheckDecision(phase, probeOk)) {
				case "healthy":
					log.info(`${LOG} 开机自检通过：RPC 层就绪`);
					console.info(`${LOG} 开机自检通过：RPC 层就绪`);
					return;
				case "reload": {
					const now = Date.now();
					if (!reloadAllowed(readReloadMark(), now, 15e3)) {
						log.warn(`${LOG} 开机自检仍失败且距上次刷新不足 ${String(RELOAD_GUARD_MS)}ms，改为提示手动刷新`);
						console.warn(`${LOG} 开机自检仍失败且距上次刷新不足 ${String(RELOAD_GUARD_MS)}ms，改为提示手动刷新`);
						setPhase("stale");
						return;
					}
					log.warn(`${LOG} 开机自检失败：页面在服务未就绪时加载（插件/设置/模型读取已损坏），自动刷新`);
					console.warn(`${LOG} 开机自检失败：页面在服务未就绪时加载（插件/设置/模型读取已损坏），自动刷新`);
					reload();
					return;
				}
				default: return;
			}
		};
		bootCheck = window.setTimeout(() => {
			runBootCheck();
		}, BOOT_CHECK_DELAY_MS);
		const es = new EventSource(EVENTS_PATH);
		es.onmessage = (event) => {
			const frame = parseFrame(event.data);
			if (frame === void 0 || frame.type !== "graph") return;
			everFramed = true;
			if (offlineGrace !== void 0) {
				window.clearTimeout(offlineGrace);
				offlineGrace = void 0;
			}
			switch (decideGraph(bootRev, frame.rev)) {
				case "recover":
					stopReloadPoll();
					reloadScheduled = false;
					setPhase("ok");
					break;
				case "reload":
					setPhase("stale", { pending: true });
					startReloadPoll();
			}
		};
		es.onerror = () => {
			if (phase === "stale" || offlineGrace !== void 0) return;
			offlineGrace = window.setTimeout(() => {
				offlineGrace = void 0;
				if (!everFramed && Date.now() - startedAt > 9e4) {
					log.warn(`${LOG} ${EVENTS_PATH} 始终没有可用帧，关闭监听（自动刷新不可用）`);
					dispose();
					return;
				}
				setPhase("offline");
			}, OFFLINE_GRACE_MS);
		};
		function dispose() {
			stopReloadPoll();
			if (offlineGrace !== void 0) {
				window.clearTimeout(offlineGrace);
				offlineGrace = void 0;
			}
			if (bootCheck !== void 0) {
				window.clearTimeout(bootCheck);
				bootCheck = void 0;
			}
			es.close();
			banner.dispose();
			for (const type of INPUT_EVENTS) document.removeEventListener(type, markInput, true);
			delete window.__dshWlvClient;
		}
		window.__dshWlvClient = { dispose };
		log.info(`${LOG} 已接管：boot rev=${bootRev ?? "(未知)"}，监听 ${EVENTS_PATH}`);
	} catch (error) {
		console.error("[web-liveness] client half failed to start:", error);
	}
}
//#endregion
export { apply, inject, name };

//# sourceMappingURL=index.mjs.map