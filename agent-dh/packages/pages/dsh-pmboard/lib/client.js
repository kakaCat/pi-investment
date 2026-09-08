window.__ModuleLoader__.load({
		id: "dsh-pmboard",
		factory: (require) => {
			var module = { exports: {} };
			var exports = module.exports;
			Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });
		Object.defineProperty(exports,Symbol.toStringTag,{value:`Module`});let e=require("react");const t=`data-dsh-reqboard-active`,n=`dsh-pmboard`,r=`项目看板`,i=`dsh:panel-activate`;function a(){let e={boardOpen:!1},r=()=>{e.boardOpen?(document.documentElement.setAttribute(t,``),document.dispatchEvent(new CustomEvent(i,{detail:n}))):document.documentElement.removeAttribute(t)};return{getSnapshot:()=>e,openBoard:()=>{e.boardOpen=!0,r()},closeBoard:()=>{e.boardOpen=!1,r()},toggleBoard:()=>{e.boardOpen=!e.boardOpen,r()}}}function o(e){let n,r=()=>{if(n!==void 0)return;let e=document.querySelector(`[data-dsh-center-column], .dsh-center-column, main[role="main"]`);e!==null&&(n=document.createElement(`div`),n.dataset.dshReqboardView=``,n.className=`dsh-reqboard-view`,n.innerHTML=`
		      <div class="dsh-reqboard-placeholder">
		        <h2>项目看板</h2>
		        <p>RFC 014 · 需求流水线插件</p>
		        <p style="font-size:12px;color:#999">M3 开发中：泳道视图 / DAG / 待归类区 / 会话跳转</p>
		      </div>
		    `,e.appendChild(n))},a=new MutationObserver(()=>r());a.observe(document.body,{childList:!0,subtree:!0});let o=t=>{if(!e.getSnapshot().boardOpen)return;let n=t.target;n&&(n.closest(`[data-dsh-reqboard-view]`)||n.closest(`.dsh-reqboard-foot`)||e.closeBoard())};document.addEventListener(`click`,o,!0);let s=t=>{t.detail!==`dsh-pmboard`&&e.getSnapshot().boardOpen&&e.closeBoard()};return document.addEventListener(i,s),r(),()=>{document.removeEventListener(`click`,o,!0),document.removeEventListener(i,s),a.disconnect(),document.documentElement.removeAttribute(t),n?.remove(),n=void 0}}const s=`dsh-pmboard/footer-action.css`,c=`dsh-pmboard:open-board`,l=(0,e.createElement)(`svg`,{viewBox:`0 0 16 16`,width:`16`,height:`16`,fill:`none`,stroke:`currentColor`,"stroke-width":`1.4`,"stroke-linecap":`round`,"stroke-linejoin":`round`,"aria-hidden":`true`},(0,e.createElement)(`rect`,{x:`2`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`2`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`2`,y:`9`,width:`5`,height:`5`,rx:`1`}),(0,e.createElement)(`rect`,{x:`9`,y:`9`,width:`5`,height:`5`,rx:`1`}));function u(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${s}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=s,e.textContent=`
		.dsh-reqboard-foot {
		  display: flex; align-items: center; gap: 8px;
		  border: none; background: transparent; color: var(--dsw-text-secondary, inherit);
		  font: inherit; font-size: 13px; cursor: pointer;
		  -webkit-appearance: none; appearance: none;
		}
		.dsh-reqboard-foot:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
		.dsh-reqboard-foot:active { background: var(--dsw-active, rgba(128,128,128,.2)); }
		.dsh-reqboard-foot.wide {
		  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
		  border-radius: 8px; justify-content: flex-start; text-align: left;
		}
		.dsh-reqboard-foot.rail {
		  width: 36px; height: 36px; margin: 4px auto; border-radius: 8px;
		  justify-content: center; padding: 0;
		}
		.dsh-reqboard-foot-icon { display: inline-flex; flex: none; }
		.dsh-reqboard-foot.rail .dsh-reqboard-foot-label { display: none; }
		.dsh-reqboard-foot-icon svg { width: 16px; height: 16px; }
		`,document.head.appendChild(e)}function d(t){let{wide:n}=t,i=r;return(0,e.createElement)(`button`,{type:`button`,className:n?`dsh-reqboard-foot wide`:`dsh-reqboard-foot rail`,title:i,"aria-label":i,onClick:()=>{window.dispatchEvent(new CustomEvent(c,{detail:{open:!0}}))}},n?[(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-icon`,key:`i`},l),(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-label`,key:`l`},i)]:(0,e.createElement)(`span`,{className:`dsh-reqboard-foot-icon`,key:`i`},l))}const f=`dsh-pmboard/styles.css`;function p(){if(typeof document>`u`||document.querySelector(`style[data-plugin-css="${f}"]`))return;let e=document.createElement(`style`);e.dataset.pluginCss=f,e.textContent=`
		/* Sidebar footer button */
		.dsh-reqboard-foot {
		  display: flex; align-items: center; gap: 8px;
		  border: none; background: transparent; color: var(--dsw-text-secondary, inherit);
		  font: inherit; font-size: 13px; cursor: pointer;
		  -webkit-appearance: none; appearance: none;
		}
		.dsh-reqboard-foot:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
		.dsh-reqboard-foot:active { background: var(--dsw-active, rgba(128,128,128,.2)); }
		.dsh-reqboard-foot.wide {
		  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
		  border-radius: 8px; justify-content: flex-start; text-align: left;
		}
		.dsh-reqboard-foot.rail {
		  width: 36px; height: 36px; margin: 4px auto; border-radius: 8px;
		  justify-content: center; padding: 0;
		}
		.dsh-reqboard-foot-icon { display: inline-flex; flex: none; }
		.dsh-reqboard-foot.rail .dsh-reqboard-foot-label { display: none; }
		.dsh-reqboard-foot-icon svg { width: 16px; height: 16px; }
		
		/* Center column board container */
		.dsh-reqboard-view {
		  display: none;
		  position: absolute; inset: 0;
		  background: var(--dsw-bg-primary, #fff);
		  z-index: 10;
		  flex-direction: column;
		  padding: 24px;
		  overflow: auto;
		}
		html[data-dsh-reqboard-active] .dsh-reqboard-view { display: flex; }
		
		/* Placeholder content */
		.dsh-reqboard-placeholder {
		  display: flex; flex-direction: column; align-items: center; justify-content: center;
		  height: 100%; gap: 16px;
		  color: var(--dsw-text-secondary, #888);
		}
		.dsh-reqboard-placeholder h2 {
		  margin: 0; font-size: 20px; color: var(--dsw-text-primary, #333);
		}
		.dsh-reqboard-placeholder p {
		  margin: 0; font-size: 14px;
		}
		`,document.head.appendChild(e)}const m=[`slots`];function h(e){try{u(),p(),window.__dshReqboardClient?.dispose();let t=a(),i=o(t),s=e=>{e.detail?.open===!0?t.getSnapshot().boardOpen?t.closeBoard():t.openBoard():t.toggleBoard()};window.addEventListener(c,s),window.__dshReqboardClient={dispose:()=>{window.removeEventListener(c,s),i(),t.closeBoard()}};let l=e.slots;l?l.inject(`sidebar.footer.action`,()=>l.register({name:`sidebar.footer.action`,id:n,order:110,label:r},d)):console.warn(`[dsh-pmboard] ctx.slots unavailable`)}catch(e){console.error(`[dsh-pmboard] client half failed to start:`,e)}}exports.apply=h,exports.inject=m,exports.name=`dsh-pmboard/client`;
			return module.exports;
		}
	});

