# t-e49c3c 返工：详情页「🪙 Token」tab（汇总卡 + 四个折叠块）

> 需求：REQ-a33899 项目看板：记录并展示每个流程节点（阶段过程）的 Token 消耗
> 验收标准：pnpm build:client 通过且 verify-client-build 无报错；grep -c 'data-tab="token"' lib/client.js >= 1；一级折叠四块齐全；固定系统提示词每段可展开看到具体提示词内容（pre-wrap，超长内滚动）；无快照显示「无快照」、服务不可用显示「不可用」，均不显示 0。

---
## 汇报 1（2026-09-18T05:35:17.283Z，窗口 session-b11b0a40-5c65-4c8d-88c7-23988b4979b0）

返工复核：详情页「🪙 Token」tab（汇总卡 + 四个折叠块）。发版后线上接口可用，页面刷新后 tab 可打开；用例全绿。

### 完成项

- tests/token-tab.test.ts 全绿
- 线上 token 接口 200（页面数据源可用）

### 改动文件

- `agent-dh/packages/pages/dsh-pmboard/tests/token-tab.test.ts`

### 下一步

无（随发版完成）

---
