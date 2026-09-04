window.__ModuleLoader__.load({
		id: "@pi-investment/dashboard-bulletin",
		factory: (require) => {
			var module = { exports: {} };
			var exports = module.exports;
			Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});function e(){let e=document.querySelector(`[data-pane="sidebar"], [class*="sidebarCol"], .dshDesktopUpstreamSidebar, .dshDesktopSidebarSurface`);if(e!==null)return e.querySelector(`[class*="logoRow"]`)?.parentElement??e.firstElementChild}function t(t){let n,r=()=>{let e=document.createElement(`button`);return e.type=`button`,e.className=`dsh-bbd-entry`,e.dataset.dshBbdEntry=``,e.setAttribute(`aria-label`,`公告板`),e.title=`公告板`,e.innerHTML=`<svg width='16' height='16' viewBox='0 0 16 16' fill='none' stroke='currentColor' stroke-width='1.4' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'><rect x='3' y='2.5' width='10' height='11' rx='1.5'/><path d='M6 6.5h4M6 9h4'/></svg><span class="dsh-bbd-entry-label">公告板</span>`,e.addEventListener(`click`,e=>{e.preventDefault(),e.stopPropagation(),t.toggle()}),e},i=()=>{let t=e();if(t===void 0)return!1;if(t.querySelector(`[data-dsh-bbd-entry]`)!==null){let e=t.querySelector(`[data-dsh-bbd-entry]`);return e!==void 0&&n===void 0&&(n=e),!0}let i=r(),a=t.querySelector(`[class*="logoRow"]`);return a!==null&&a.nextSibling!==null?t.insertBefore(i,a.nextSibling):t.prepend(i),n=i,!0};i();let a=new MutationObserver(()=>{(n===void 0||!document.contains(n)||n.parentElement===null)&&i()});a.observe(document.body,{childList:!0,subtree:!0});let o=window.setInterval(()=>{(n===void 0||!document.contains(n))&&i()},5e3),s=()=>{n?.setAttribute(`data-active`,t.isActive()?`true`:`false`)},c=window.setInterval(s,1e3);return s(),()=>{a.disconnect(),window.clearInterval(o),window.clearInterval(c),n?.remove(),n=void 0}}function n(){let e=`dsh-bbd-styles`;if(document.getElementById(e)!==null)return;let t=document.createElement(`style`);t.id=e,t.textContent=`
		.dsh-bbd-entry {
		  display: flex; align-items: center; gap: 8px; position: relative;
		  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
		  border: none; border-radius: 8px; background: transparent;
		  color: var(--dsw-text-secondary, inherit); font: inherit; font-size: 13px;
		  cursor: pointer; text-align: left;
		}
		.dsh-bbd-entry:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
		.dsh-bbd-entry[data-active="true"] { background: var(--dsw-active, rgba(128,128,128,.18)); color: var(--dsw-text-primary, inherit); font-weight: 500; }
		.dsh-bbd-entry svg { flex: none; }
		[data-sidebar-collapsed] [data-dsh-bbd-entry],
		[class*="_collapsed"] [data-dsh-bbd-entry] {
		  width: 36px; height: 36px; min-width: 36px; margin: 0 0 12px; padding: 0;
		  justify-content: center; gap: 0; text-align: center;
		}
		[data-sidebar-collapsed] [data-dsh-bbd-entry] .dsh-bbd-entry-label,
		[class*="_collapsed"] [data-dsh-bbd-entry] .dsh-bbd-entry-label { display: none; }
		[data-sidebar-collapsed] [data-dsh-bbd-entry] svg,
		[class*="_collapsed"] [data-dsh-bbd-entry] svg { width: 16px; height: 16px; }
		`,(document.head??document.documentElement).appendChild(t)}const r=[];function i(e){try{window.__dshBbdClient?.dispose?.()}catch{}n();let r={active:!1},i=t({isActive:()=>r.active,toggle:()=>{r.active=!r.active,console.info(`[dashboard-bulletin] 按钮已就绪（phase1）。看板正文待 phase2（RFC 013）`)}});window.__dshBbdClient={dispose(){try{i()}catch{}}}}exports.apply=i,exports.inject=r,exports.name=`@pi-investment/dashboard-bulletin/client`;
			return module.exports;
		}
	});

