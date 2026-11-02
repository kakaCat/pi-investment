# t-a70b3c 修 get_config() 空壳·研发

> 需求：REQ-261001145152-3982 V2 项目全面审查与优化梳理

## 在做什么
修 get_config() 空壳·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
改动已落盘，相关测试或命令跑通并附输出摘要

---
## 汇报 1（2026-10-01T09:28:14.476Z，窗口 session-7fc133ad-e896-4aa2-9cb5-443ac7c5af22）

研发段：**"配置看起来配了、其实没生效"这个洞被补上了**——原先那个名为兼容层的函数永远返回默认值/空字典，而 17 处生产调用都按"能取到真实配置"在写，于是 DSN、密钥这些东西全部静默走默认；现在它返回真实配置，取不到的密钥明确返回 None 而不是抛异常被吞掉。

### 完成项

- 查清真实调用面：17 处真调用（不是 29——原统计把 `self.get_config(...)` 这类同名方法算进去了），分布在 engine/async_base_repository/jwt_manager/llm_service/sentry_config/rate_limiter/websocket_server/cli/memory 等
- 查清契约真相：调用方期望**带属性的嵌套对象**（config.database.url / config.app.jwt_secret_key / config.external.deepseek_api_key），而桩返回 {} → 全部抛 AttributeError 后被 except 吞掉（典型后果：DSN 静默退回环境变量）
- 额外查实：jwt_secret_key / sentry_dsn / deepseek_api_key 三个名字**全仓零定义**（只在调用方被引用），DatabaseSettings 只有 database_url 属性而非 url/async_url/database —— 即"空壳"之外还有一层"契约从未实现"
- 实现修复：get_config() 无参时返回 _CompatConfig（真实 settings + database/external/app 三个视图 + 其余属性透传）；带键时依次查 环境变量 → settings 摊平表（含 pydantic alias）→ default
- 验收①：`get_config('PGHOST','FALLBACK')` → '127.0.0.1'（真实值，不再是 FALLBACK）
- 验收②（前后对照，证明真生效）：改前 `config.database.url` 抛 AttributeError → 改后返回 postgresql://<user>@127.0.0.1:5432/quant_investment
- 验收③：重启服务后启动日志 **0 error / 0 warning**，无任何 DSN/配置异常；/docs 200、db_connected=true、K 线接口返回 09-30 数据
- 回归判定：config 相关测试 3 个失败，已用**基线对照**证实改动前就存在（同一组用例在旧版本上同样 3 failed），非本次引入
- 顺带核实无密码回归：.env 里 `PGPASSWORD=` 本就是空值（长度 0，本机 PG 走 trust），故改后 URL 不带密码与改前一致

### 改动文件

- `infrastructure/config/__init__.py`

---
