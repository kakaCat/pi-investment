window.__ModuleLoader__.load({
		id: "@pi-investment/web-liveness",
		factory: (require) => {
			var module = { exports: {} };
			var exports = module.exports;
			Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});const e={offline:`服务重启中，正在自动重连…… 此期间发送的消息可能发不出去，请稍候`,stalePending:`服务已重启（代码可能已更新），你停手后页面会自动刷新`,staleManual:`服务已重启，页面需要刷新才能用上新版本（反复出现请按 Cmd+Shift+R 硬刷新）`};function t(t){let n=document.createElement(`div`);n.className=`dsh-wlv-bar`,n.dataset.phase=`ok`,n.setAttribute(`role`,`status`);let r=document.createElement(`span`);r.className=`dsh-wlv-text`;let i=document.createElement(`button`);return i.className=`dsh-wlv-action`,i.type=`button`,i.textContent=`立即刷新`,i.addEventListener(`click`,t),n.appendChild(r),n.appendChild(i),document.body.appendChild(n),{render(t,i){if(t===`ok`){n.dataset.phase=`ok`;return}r.textContent=t===`offline`?e.offline:i?.pending===!0?e.stalePending:e.staleManual,n.dataset.phase=t},dispose(){i.removeEventListener(`click`,t),n.remove()}}}const n=`dsh-wlv-styles`;function r(){if(document.getElementById(n)!==null)return;let e=document.createElement(`style`);e.id=n,e.textContent=`
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
`,(document.head??document.documentElement).appendChild(e)}function i(e){if(typeof e!=`object`||!e)return;let t=e.rev;return typeof t==`string`&&t!==``?t:void 0}function a(e){let t;try{t=JSON.parse(e)}catch{return}if(typeof t!=`object`||!t)return;let n=t;if(typeof n.type!=`string`)return;let r=n.graph,i=typeof r==`object`&&r&&typeof r.rev==`string`?r.rev:void 0;return i===void 0?{type:n.type}:{type:n.type,rev:i}}function o(e,t){return e===void 0||t===void 0?`ignore`:e===t?`recover`:`reload`}function s(e){return e.hidden?!0:e.now-e.lastInputAt>=(e.quietMs??5e3)}function c(e,t,n=15e3){return e===void 0||!Number.isFinite(e)||t-e>=n}const l=[],u=`dsh-wlv-reload-at`,d=`/plugins/events`,f=`[web-liveness]`;function p(){try{let e=window.sessionStorage.getItem(u);if(e===null)return;let t=Number(e);return Number.isFinite(t)?t:void 0}catch{return}}function m(e){try{window.sessionStorage.setItem(u,String(e))}catch{}}const h=[`keydown`,`input`,`compositionstart`,`paste`,`pointerdown`];function g(e){try{r(),window.__dshWlvClient?.dispose?.();let u=e.logger?.(`@pi-investment/web-liveness/client`)??{info:()=>{},warn:()=>{}},g=i(window.__DSH_BOOT__);g===void 0&&u.warn(`${f} window.__DSH_BOOT__.rev 读不到：只保留"服务重启中"提示，不做自动刷新`);let _=Date.now(),v=()=>{_=Date.now()};for(let e of h)document.addEventListener(e,v,!0);let y=Date.now(),b=`ok`,x=!1,S=!1,C=!1,w,T,E=t(()=>{n()}),D=(e,t)=>{e!==b&&(u.info(`${f} ${b} → ${e}`),b=e),E.render(e,t)};function n(){m(Date.now()),window.location.reload()}let O=()=>{w!==void 0&&(window.clearInterval(w),w=void 0)},k=()=>{if(S||C)return;S=!0;let e=()=>{let e=Date.now();if(!c(p(),e,15e3)){O(),C=!0,u.warn(`${f} 距上次自动刷新不足 15000ms，改为提示手动刷新`),D(`stale`);return}if(s({hidden:document.hidden,lastInputAt:_,now:e,quietMs:5e3})){O(),u.info(`${f} 服务端已换版本，刷新页面`),n();return}D(`stale`,{pending:!0})};w=window.setInterval(e,1e3),e()},A=new EventSource(d);A.onmessage=e=>{let t=a(e.data);if(t!==void 0&&t.type===`graph`)switch(x=!0,T!==void 0&&(window.clearTimeout(T),T=void 0),o(g,t.rev)){case`recover`:O(),S=!1,D(`ok`);break;case`reload`:D(`stale`,{pending:!0}),k()}},A.onerror=()=>{b!==`stale`&&T===void 0&&(T=window.setTimeout(()=>{if(T=void 0,!x&&Date.now()-y>9e4){u.warn(`${f} ${d} 始终没有可用帧，关闭监听（自动刷新不可用）`),l();return}D(`offline`)},1e3))};function l(){O(),T!==void 0&&(window.clearTimeout(T),T=void 0),A.close(),E.dispose();for(let e of h)document.removeEventListener(e,v,!0);delete window.__dshWlvClient}window.__dshWlvClient={dispose:l},u.info(`${f} 已接管：boot rev=${g??`(未知)`}，监听 ${d}`)}catch(e){console.error(`[web-liveness] client half failed to start:`,e)}}exports.apply=g,exports.inject=l,exports.name=`@pi-investment/web-liveness/client`;
			return module.exports;
		}
	});

