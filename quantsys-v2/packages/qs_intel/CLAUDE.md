# qs_intel — 市场情报博弈包

> 抽离记录：quantsys-v2 单体 S5（2026-10-18）。方案卡：`docs/plans/package-boundaries-import-linter.md` §11.4 S5。

## 本包是什么

**AI 工作区 L2**：本目录=「市场情报」项目（博弈感知一条线）。上下文只要本文件，不要去根工作区。

- **定位**：对手行为分析 / 操纵检测 / 市场风格·情绪·环境识别 / 微观结构 / 龙虎榜 / 热点图 / 机会评分 / 散户恐慌指数 / 行业轮动 / 产业链地图 / 博弈预警 / 战场评估 / 事件流（event_feed）/ 条件监控 / 可配置评分
- **只读分析**：本包不写交易表、不发单（博弈预警/game_alert 只产出信号事件，接不接由 sourcing/trading 决定）
- **上游**：`qs_market_data`（只读行情快照，白名单边）
- **领域约定**：`domain/` 两子域**零 I/O、零外部依赖**（不 import requests/akshare/ORM/adapters），服务层负责取数与持久化

## 目录结构

```
qs_intel/
├── application/services/          19 服务
│   ├── opponent_behavior_service.py   对手行为（retail/institution/hot-money）
│   ├── manipulation_detector.py       操纵检测（pump&dump 阶段判定）
│   ├── battlefield_assessor.py        战场评估（0-100 竞争优势分）
│   ├── game_alert_service.py          博弈预警事件
│   ├── market_style_detector.py / market_regime_detector.py / market_sentiment_service.py / sentiment_service.py
│   ├── market_perception_service.py / market_session_service 之外的感知件
│   ├── microstructure_service.py      盘口微观结构
│   ├── lhb_service.py                 龙虎榜
│   ├── heatmap_service.py             热点图
│   ├── opportunity_scoring_service.py 机会评分
│   ├── retail_panic_index_service.py / sector_rotation_service.py
│   ├── industry_chain_service.py      产业链（用 domain/industry_chain）
│   ├── event_feed_service.py          事件流（事件日历/事件-个股映射）
│   ├── condition_monitor.py           条件监控（ORM 版，跨域条件触发）
│   └── configurable_scoring_service.py 配置驱动评分
└── domain/
    ├── competition/           博弈分析域（service 零 I/O）
    └── industry_chain/        产业链域（model + ports + seed 数据 + service）
```

## 依赖边界（方案卡 §11.3）

- 允许：本包 → kernel（`domain.ports` / `infrastructure.persistence`）、→ `qs_market_data`（只读行情）
- 暂留 L1 引用（S11 后收口）：infrastructure/services 两套 DI（ServiceFactory/service_registry）仍 import 本包成员做装配，属 kernel→package 暂时反向；部分仓储仍在 L1 `adapters/outbound/repositories/`（如 heatmap_repository），包→L1 仓储边待后续归属阶段收口
- 旧路径兼容 shim 在 L1：`application/services/<19 模块名>.py`（sys.modules 别名）、`domain/competition/__init__.py` + `domain/industry_chain/__init__.py`（__path__ 转发），30 天观察期后删除

## 常见任务路径

- **加对手行为信号** → `opponent_behavior_service.py`（net_flow 判定阈值）+ `game_alert_service.py`（事件格式）
- **加操纵模式** → `manipulation_detector.py`（阶段状态机）
- **改风格/情绪判定** → `market_style_detector.py`（风格 Presidency）+ `market_sentiment_service.py`
- **改产业链** → `domain/industry_chain/seed/`（静态数据）+ `industry_chain_service.py`（查询编排）
- **加条件触发规则** → `condition_monitor.py`（规则表达式，纯条件匹配不携带业务副作用）
