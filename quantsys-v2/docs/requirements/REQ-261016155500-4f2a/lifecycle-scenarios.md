# 盯盘规则全生命周期场景覆盖矩阵与终结事件补全（2026-10-19）

> 用户裁定：**盯盘信息归盯盘引擎管，过期了应该被引擎处理**（不等 agent/用户）。
> 本文是规则全生命周期的场景审计 + C 区（终结事件）缺口的落地记录。

## 场景矩阵

### A. 创建与归属 ✅
| 场景 | 机制 |
|---|---|
| A1 机会扫描自动建规则 | 正常运转 |
| A2 缺账户归属 | digest 缺陷提示 + 补全待办 |
| A3 同标的多规则重复 | 合并工具 + 重叠治理项 |

### B. 日常盯盘 ✅
| 场景 | 机制 |
|---|---|
| B1 新鲜穿越 | 即时四段式卡（与我何干/建议动作/重估条件） |
| B2 陈旧驻留（早就跌破） | freshness_of 判定 → 阈值失真治理项（不发卡） |
| B3 电平复读 | 迟滞带 + 每条件日上限 2 次 |
| B4 观察类刷屏 | 15 分钟聚合卡（含建议动作/溯源） |

### C. 终结事件（本次补全）

| 场景 | 补全后机制 | 落点 |
|---|---|---|
| **C1 止损触发后** | **分账户归宿**：agent 自有账户 → 引擎自动退役（线破=使命完成）；**user_main 用户账户 → 只报不碰**（2026-10-19 用户裁定"拿着，不应该修改规则"——止损触发≠止损执行，原线仍是用户有效指令，治理注记提示 agent 来确认） | `engine._maybe_retire_executed_stop` |
| C2 止盈/减仓档触发后 | 不退役（部分动作，剩余仓位还要盯），治理链复核 | 同上守卫分支 |
| C3 买入执行后补挂止损/阶段推进 | 持仓联动账户扩到 `agent_virtual + agent_brain + user_main_simulation`（此前只 agent_virtual——#128 病根） | `factory.py` accounts |
| C4 清仓后卖出规则族收摊 | 同上扩展后生效 | 同上 |
| C5 规则到期 | 显式收摊注记（此前静默消失） | `expire_overdue_rules`（每日随 reconcile） |
| C6 长期不响 | meta_review | 既有 |
| C7 阈值失真 | 治理项 | 既有（B2） |

### D. 环境异常

| 场景 | 补全后机制 |
|---|---|
| D1 处置 agent 不在线 | 超时升级用户 + agent-dh launchd 常驻（KeepAlive） |
| **D2 停牌/退市** | **连续 3 交易日取数失败 → 停牌/退市治理项**（此前永久静默失效） | `engine._note_quote_failure` |
| D3 行情源全挂 | 取数失败计入同一计数，达标即治理 |
| D4 引擎进程死亡 | launchd KeepAlive + 心跳巡检 |

### E. 数据治理 ✅
触发洪水去重 / 待办重复（幂等守卫 + `uq_watch_todos_open_rulechange` 唯一索引）/ 回执收敛 / 抑噪跨日审计

### F. 成本与预案漂移

| 场景 | 补全后机制 |
|---|---|
| **F1 加仓/调仓后 cost_price 过时** | **每日 reconcile：持仓均价 vs 规则成本偏差 >2% → 自动同步 + 注记** | `_sync_cost_price` |
| F2 预案文本价位漂移 | 事实校正注记机制（半覆盖，接受） |

## 实施清单（2026-10-19 全部落地并重启生效）

1. `engine._maybe_retire_executed_stop`：exit_stop 触发 → enabled=false + lifecycle_stage=closed + ops_notes 横幅
2. `factory.py`：PositionLifecycleService accounts 扩三账户（#128 徐工止损挂单的结构性根因）
3. `position_lifecycle_service._sync_cost_price` + `expire_overdue_rules`
4. `engine._note_quote_failure`：QUOTE_FAIL_GOVERNANCE_DAYS=3
5. 测试 `tests/services/test_terminal_events.py` 8 例全绿；watch 全量 479 过
6. 顺带修复：`watch_runtime_dedup.account` 迁移漏应用导致的启动报错（prod+test 已补）

## 遗留（不在本次范围）

- C1 的"未平仓重建新线"：agent 起草 → 用户确认（交易阈值，宪法要求人工确认）
- F2 预案文本价位漂移：半覆盖接受
- tests/ 全量套件 5 个收集错误（迁移期 tools 模块路径，干净 HEAD 更多，预存）
