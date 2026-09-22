# REQ-260922133212-dd5b 修复归档门禁不认时间戳需求 id（REQUIREMENT_DIR_PATTERN 正则陈旧）

> 类型：bug ｜ 难度：simple ｜ 立项窗口：w-9faaac35（investor）
> 来源：2026-09-22 REQ-260922012924-2e29 归档材料提交被拒现场（REQBOARD_INVALID_INPUT）。

## 复现步骤

1. 任一采用新时间戳 id 格式的需求（如 REQ-260922012924-2e29）走完验收；
2. 调 `reqboard_submit(kind=archive, dir='docs/requirements/REQ-260922012924-2e29', ...)`；
3. 被拒：`需求目录不符合约定：应为 docs/requirements/REQ-xxxxxx`。

期望：新格式 id 的需求目录合法，材料正常登记；实际：一律拒绝。

## 根因

`src/shared/protocol.ts:1319` 的 `REQUIREMENT_DIR_PATTERN = /(?:^|\/)docs\/requirements\/REQ-[0-9a-f]{6}$/` 写死旧版六位十六进制 id。2026-09 需求 id 改为时间戳格式（`REQ-<14位时间戳>-<6位hex>`，见 dsh-pmboard/CHANGELOG-req-id-timestamp.md）后该校验未同步——**格式升级改了生成端，忘了校验端**。

## 功能点

### BUG-1: REQUIREMENT_DIR_PATTERN 兼容新旧两种 id 格式
正则改为同时接受 `REQ-[0-9a-f]{6}`（旧）与 `REQ-\d{12,14}-[0-9a-f]{6}`（新）；新增单测覆盖：旧格式通过 / 新格式通过 / 乱造格式仍拒（如 `REQ-XYZ`、`docs/other/REQ-260922133212-dd5b` 路径不对仍拒）。

### BUG-2: 修复后补交 REQ-260922012924-2e29 归档材料
用修复后的门禁补交其归档材料（dir/docs/merged_into/index_entry/manual_updates 已备好），验证"验收通过即 archived、材料后补"的 REQ-9f4a44 路径对新格式 id 闭环可用。

## 边界

- **做**：正则兼容 + 单测 + 补交验证。
- **不做**：不动 id 生成器；不改归档材料的其他校验项（必填文档/合并去向规则）；不追溯存量新格式需求（台账中仅 REQ-260922012924-2e29 一条受影响）。
- **不做**：triage 遗留路径删除（独立需求，下一个立）。

## 回归

- 新单测：protocol 的目录约定校验两格式 + 非法拒绝；全量回归 `vitest run packages/web/dsh-pmboard` 失败集与主干基线差集为空。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| BUG-1 | 🔴 **未被接收** | — |
| BUG-2 | 🔴 **未被接收** | — |

> 🔴 **未被接收（2 条）**：BUG-1、BUG-2

<!-- reqboard:marks:end -->
