---
req_id: REQ-261001145152-3982
title: 架构现状与治理方向
doc: design/architecture
serves: FR-1, FR-2, FR-3, FR-6
---

# 架构设计（REQ-261001145152-3982）

**重要前提**：本需求**不修改任何运行时架构**（只读审查 + 清单）。
因此本文档的"设计方案"指的是**审查方法**与**后续治理方向**，不是待实施的代码改动；
真正的实施条目在 [optimization-backlog.md](optimization-backlog.md)。

## 目标与总体方案（serves: FR-1）

**问题**：用户提出"V2 内容特别多，需要梳理看看如何优化"——缺一张可信的现状地图与优先级。

**当前状况**（实测，详见 [audit-report.md](audit-report.md)）：

```
   domain(341f) ──┐
                  ├── 117 处越层引入 / 54 文件 ──┐
application(235f)─┤                              ├── 包级 24 节点强连通（无层次）
                  │   application 层 45.5% 文件越层
adapters(295f) ───┤                              └── 函数内延迟 import 1,886 处
infrastructure(168f)┘
```

**设计方案**：四维度只读盘点 + 证据化清单：

| 维度 | 方法 | 产出 |
|---|---|---|
| 资产与分层 | AST 统计 + 仓库自带 `analyze_layer_violations.py` 交叉验证 | 违规率表 + TOP 文件 |
| 重复与分叉 | `md5` / `diff` / `difflib` 三档筛 + 逐个读文件排除伪重复 | 13 行复制清单（含是否已分叉） |
| 调度与运行态 | 代码路径追踪 + DB 台账 + 进程/端口/日志探针 | 4 套调度器拓扑 + 停摆时间线 |
| 依赖与环境 | import 静态扫描 × 安装态 × 两套清单差集 | 119 个 ImportError 模块归因 |

**不这么做的后果**：40 万行存量上直接动刀，无法区分"该删的重复"与"在用的实现"，
也无法判断哪些改动能验证、哪些不能。

## 模块改动地图（serves: FR-1）

```
  本需求的改动 = 文档（新增 7 份），代码改动 = 0

  quantsys-v2/
    docs/requirements/REQ-261001145152-3982/
      requirement.md                  [新增] 需求定义（已确认）
      design/
        audit-report.md               [新增] 体检报告
        optimization-backlog.md       [新增] 优化清单（核心交付）
        architecture.md               [新增] 本文件
        data-model.md                 [新增] 条目契约
        interfaces.md                 [新增] 交付接口
        test-cases.md                 [新增] 复现校验用例
        use-cases.md                  [新增] 三类使用场景

  生产代码（domain/ application/ adapters/ infrastructure/）：**零改动**
  数据库：**零改动**（只读查询 quant_investment）
```

| 模块/文件 | 类型 | 改动内容 | 原因（serves） | 影响范围 |
|---|---|---|---|---|
| `design/*.md` ×7 | 新增 | 审查报告 + 清单 + 契约 | FR-1…FR-7 | 仅文档，无运行时影响 |
| 生产代码 | 无 | — | — | 0 文件 |
| DB schema | 无 | — | — | 0 表 |

## 数据结构变更（serves: FR-6）

**无变更**。本需求不新增/不修改任何数据库表、字段或缓存结构。
被**记录**（非修改）的现状数据事实见 [data-model.md](data-model.md)。

## 接口变更（serves: FR-1）

**无变更**：不新增/修改任何 HTTP 端点、工具函数签名、事件协议。
本需求唯一的"新接口"是**交付文档**（见 [interfaces.md](interfaces.md)）。

## 依赖关系（serves: FR-4）

**新增依赖**：无。本次审查用仓库现有 `venv` + 系统 `psql` 完成（注：`venv` 缺 3 个包，
影响了 pytest 收集，但未影响审查结论——见 audit-report §4.2）。

**应当收口/删除的依赖声明**（属后续批次，非本设计改动）：

| 依赖项 | 原用途 | 处置 | 依据 |
|---|---|---|---|
| `psycopg2-binary`（pyproject） | DB 驱动 | **改回 `psycopg2`** | requirements.txt 注释记录 2026-08-11 double-OpenSSL 崩溃事故 |
| `docs/misc/requirements.txt` 的 47 个包 | 真实依赖声明 | **并入 pyproject** | 两套清单冲突，权威清单在文档目录 |
| `pybreaker` / `pydantic_settings` / `jieba` | 运行时必需 | **补声明** | 当前模块级硬 import 却未声明 → 119 模块 ImportError |

## 目录结构（serves: FR-1）

```
quantsys-v2/docs/
├── requirements/REQ-261001145152-3982/   # 本需求（新增）
└── （140 个 md 仍平铺在 docs/ 根目录 → 待归位，见 backlog P3-1）
```

## 关键算法/流程（serves: FR-1）

审查执行流程（可复现）：

```
读需求 ──▶ 四路并行盘点 ──▶ <证据是否可执行?>
                              │
                        否 ───┴─── 是
                        │          │
                   标"未验证"      记录命令+输出
                   （不猜）         │
                                    ▼
                        <两处实现是否 md5/diff 相同?>
                              │
                        是 ───┴─── 否
                        │          │
                  判"逐字重复"   判"已分叉"→ 风险升一级
                        │          │
                        └────┬─────┘
                             ▼
                  按 收益/风险/成本 排序 → 四批次清单
```

**关键决策点**：

| 决策 | 选项 A | 选项 B | 选了哪个 | 为什么 |
|---|---|---|---|---|
| 是否改代码 | 边审边改 | 只审不改 | **B** | 40 万行存量 + 服务已停；先有地图再动刀（用户已确认此边界） |
| "重复"如何判定 | 只看文件名 | md5+diff+读文件排除伪重复 | **B** | 已排除 7 对伪重复（如 quote/financial provider） |
| 孤儿模块口径 | 只匹配全限定名（165 个） | 含 `from parent import leaf` + 字符串（35 个） | **两者都报** | 差 5 倍本身证明"静态扫描不能作删除依据" |
| 优先级排序 | 按代码量 | 按"线上影响 × 修复成本" | **B** | 服务停摆 18 天远比 117 处分层违规紧急 |

## 安全/性能考虑（serves: FR-3）

**安全风险**：本需求对生产库 `quant_investment` 执行**只读查询**（`select`/`\d`），
不执行 DDL/DML；报告内不含凭据明文（`.env` 密码已脱敏）。

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| 只读查询误伤生产库 | 低（仅 select） | 全程未执行写入语句；未调用任何 job 触发接口 |
| 报告暴露内部拓扑 | 低 | 文档在需求目录内，随需求归档 |

**性能影响**：无（不改运行代码）。

| 指标 | 改前 | 改后 | 可接受吗 |
|---|---|---|---|
| 服务行为 | — | 无变化 | ✅ |

## 测试策略（serves: FR-7）

**必测场景** = 报告的**可复现性**：15 条命令逐条复核（见 [test-cases.md](test-cases.md)）。

| 场景 | 输入 | 预期输出 | 测试用例编号 |
|---|---|---|---|
| 服务停摆结论可复现 | `ls -lT logs/fastapi_5001.log` | 2026-09-13 15:33 | TC-1 |
| 调度重复可复现 | psql 分组查询 | 4 行重复 cron | TC-2 |
| 依赖缺口可复现 | `pytest --collect-only -q` | 5264 + 119 errors | TC-3 |
| 护栏失效可复现 | `grep BASELINE .git-hooks/pre-commit` | `BASELINE=7` | TC-4 |
| 删除项零引用 | `grep -rn "infrastructure\.quantlib\.adapters\."` | 仅目录内部 | TC-5 |
| 清单契约完整 | 解析 backlog 表 | 21 条 × 10 字段 | TC-6 |

## 错误处理（serves: FR-1）

**新增错误码/异常**：无。

本需求对"失败"的处理是**写作纪律**而非代码：

| 情形 | 处置 | 落点 |
|---|---|---|
| 结论无法验证 | 显式标注"未验证" | audit-report 各处（如 FastAPI 端点差集、13 个歧义孤儿） |
| 口径互相矛盾 | 并列两种口径 + 说明差异 | audit-report §1.3（分层标准）、§5.8（孤儿口径差 5 倍） |
| 发现初判错误 | 明确写"前提修正" | audit-report §2.0（quantlib 不是整库副本） |

## 配置项（serves: FR-4）

**无新增配置**。审查期间未修改 `.env` / `config/*`。

## 监控埋点（serves: FR-3）

**本设计不新增埋点**，但清单中的 `P0-3` 建议新增两条外部探针
（进程/端口心跳 + 数据新鲜度），理由是服务已"静默死亡"3 次而无人知晓。

| 埋点 | 触发时机 | 记录内容 | 用于排查什么问题 |
|---|---|---|---|
| （建议）心跳探针 | 每 5 分钟 | 5001/8080 可达性 | 服务静默停止（本仓已发生 3 次） |
| （建议）新鲜度探针 | 每日 | `max(trade_date)` 与最近交易日差 | 数据管线中断（本次滞后 20 天） |

## 部署变更（serves: FR-3）

**无部署变更**。注意：现网 `~/Library/LaunchAgents/com.pi-investment.v2-api.plist` **已不存在**，
故 `P0-1`（救活服务）需要先确认现网拉起方式——这属清单条目，不在本设计内执行。

| 变更项 | 操作步骤 | 回滚步骤 |
|---|---|---|
| 无 | — | — |

## 文档更新清单（serves: FR-5）

| 文档 | 更新内容 | 负责人 |
|---|---|---|
| `CLAUDE.md`（quantsys-v2） | 修 8 条矛盾：入口路径、requirements.txt、DATA_ACCESS_GUIDE、Flask 回滚栈、`infrastructure/repositories/`、`unified_scheduler` 已删、`USE_AGENT_OS_SCHEDULER`、launchd plist | 待排期（P3-4） |
| `docs/*.md`（9 份提到 `pip install -r requirements.txt`） | 改为真实依赖入口 | 待排期（P3-4） |
| `docs/work-logs/2026-10/` | 本次审查归档 | 归档阶段 |

## 遗留问题（serves: FR-5）

| 问题 | 影响 | 计划何时解决 |
|---|---|---|
| FastAPI 端点差集清单为静态提取（抽检发现误判 `/api/health`），未做运行时内省 | 该清单不可作为 parity 依据 | 待依赖修复后跑 `app.routes` 核对 |
| 13 个"歧义孤儿"未逐一确认真活 | 可能漏判死代码 | 随 P1-3 一并人工确认 |
| `scripts/` 的 `_v2`/`_fixed` 系列未逐个反查调用方 | 不可盲删 | P3-6 |
| `data_validator` 三份同名实现的语义等价性未逐行验证 | 合并前有风险 | P2-5 前置调研 |
| 运行时 ImportError 未做压测（未启动完整依赖环境的服务） | 悬空 import 的实际爆炸点未逐一确认 | P1-1 之后重测 |
