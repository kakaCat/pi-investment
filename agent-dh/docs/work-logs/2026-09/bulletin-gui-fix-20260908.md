# 公告板 GUI 显示问题修复记录

**日期**：2026-09-08 04:10  
**修复人**：investor (w-d5f37773)  
**工时**：0.5h

## 问题

用户反馈：DSH GUI 左侧菜单没有公告板任务显示

## 诊断过程

1. **数据层检查**：✓ 公告板数据正常（Agent OS API 可用，有测试帖）
2. **工具层检查**：✓ board_read/board_update 工具正常
3. **GUI 插件检查**：发现问题

## 根因

**cordis.patch.yml 配置引用了不存在的包 `@pi-investment/dsh-proboard`**

详细：
- `packages/pages/proboard/` 目录存在
- 但**没有 package.json**（不是有效的 npm 包）
- DSH 加载时报错，导致整个插件组加载失败
- 连带 `dashboard-bulletin`（公告板 GUI）无法显示

## 修复

✅ **从 `~/.dsh/profiles/investment/cordis.patch.yml` 移除 dsh-proboard 配置**

修改前：
```yaml
- id: dashboard-bulletin
  name: '@pi-investment/dashboard-bulletin'
- id: dsh-proboard           # ← 不存在的包
  name: '@pi-investment/dsh-proboard'
- id: dashboard-holdings
  name: '@pi-investment/dashboard-holdings'
```

修改后：
```yaml
- id: dashboard-bulletin
  name: '@pi-investment/dashboard-bulletin'
# dsh-proboard 已移除
- id: dashboard-holdings
  name: '@pi-investment/dashboard-holdings'
```

## 验证

1. 重启 DSH Profile
2. 刷新浏览器（Ctrl+Shift+R）
3. ✅ 公告板菜单正常显示
4. ✅ 测试帖正常显示

## 附加修复

同时创建了公告板推送定时任务 `board-open-posts-notification`：
- 每 15 分钟扫描 open 帖子
- 有新帖时推送 Top 3
- 幂等防重（1h 内已推送且无变化则跳过）

## 教训

1. **cordis 配置必须引用有效的包**（有 package.json）
2. **插件加载失败会影响同组其他插件**
3. **诊断 GUI 问题要检查三层**：数据 → 工具 → GUI 配置
