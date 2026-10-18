# qs_notification（通知域）

通知三件套的独立二方包：NotificationFacade（唯一对外入口）、渠道（Feishu/Agent）、格式化器、领域模型与分组投递策略（运维群/原群/盯盘群路由）。

**2026-10-18 由 `application/notification` + `infrastructure/notification` + `domain/notification` 三层合并抽离**（方案卡：`docs/plans/package-boundaries-import-linter.md` §11.4 S2）。分支 `feat/qs-notification-package`。

## 规则

- **零业务依赖**：本包只允许 `requests/structlog` 等基础库；**禁止** import `domain/*`、`application/*`、`adapters/*`、`infrastructure/*`、`services/*`、`repositories/*`（import-linter 契约 `notification-independence`）。
- 对外只暴露 `NotificationFacade` / `NotificationFactory` / 领域模型；调用方**禁止**直接调用渠道类发消息（仓库规约：所有通知必须走 Facade）。
- 渠道命名约束：`FeishuChannel(..., name=...)` 必须给运维实例起不同名字（`feishu_ops`）——`NotificationService` 用 `{get_name(): channel}` 建索引，同名会互相顶掉。
- 渠道缺失时 `send_ops_card/send_ops_text` 返回 `False`，**绝不静默改投原群**。

## 常用任务路径

| 任务 | 从哪改 |
|---|---|
| 新通知类型（facade 方法） | `qs_notification/application/notification_facade.py` |
| 渠道实现 | `qs_notification/infrastructure/channels/`（feishu_channel / agent_channel） |
| 消息格式化 | `qs_notification/infrastructure/formatters/`（三群模板） |
| 分组/投递策略（系统群≠股票群） | `qs_notification/domain/policies/` |
| 通知领域模型 | `qs_notification/domain/models/` |

## 安装（主仓库开发者）

```bash
pip install -e ./packages/qs_notification   # 必须指向本工作区内路径
```

## 旧路径兼容

`application/notification`、`infrastructure/notification`、`domain/notification` 三个旧位置留有 `__path__` 转发 shim（30 天观察期后删除）。新代码禁止使用旧路径。
