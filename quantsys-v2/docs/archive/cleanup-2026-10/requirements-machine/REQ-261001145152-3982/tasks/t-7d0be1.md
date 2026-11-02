# t-7d0be1 修 get_config() 空壳·联调

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
修 get_config() 空壳·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
接口联调通过：给出请求样例与期望响应，实际返回与预期一致

---
## 汇报 1（2026-10-01T09:30:10.840Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

联调段：7 条真实调用链全部通了，DSN 也确实改从配置来（而不是"抛异常后退回环境变量"）；服务重启后读写、健康检查、K 线接口都正常，启动日志干净。

### 完成项

- 逐个真实调用方路径验证通过（7/7）：engine→config.database.url、async_base_repository→async_url 与 database、jwt_manager→app.jwt_secret_key、sentry_config→app.sentry_dsn、llm_service→external.deepseek_api_key、以及 rate_limiter/websocket/cli 走的透传属性
- DSN 来源已切换到 config（优先级 2）：`_resolve_db_dsn()` 实测返回 postgresql://<user>@127.0.0.1:5432/quant_investment —— 改前这一步抛 AttributeError，只能退回环境变量拼装
- 服务重启后端到端可用：/docs 200、health db_connected=true、K 线接口返回 2026-09-30 数据；启动日志 0 error / 0 warning
- 未配置的密钥（jwt_secret_key / sentry_dsn / deepseek_api_key）现返回明确 None —— 调用方原本就按"取不到就 warn/降级"写，现在拿到的是明确的 None 而不是被吞掉的 AttributeError

### 改动文件

- `infrastructure/config/__init__.py`

---
