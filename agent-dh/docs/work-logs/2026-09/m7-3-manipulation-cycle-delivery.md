# M7-3 操纵周期识别实战验证交付（2026-09-01）

> 署名：investor w-8366e526
> 状态：✅ 完成（M7 完成度 67% → 100%，工单 3/3 全 ✅）

---

## 1. 背景与问题

M7-1/M7-2 已识别"对手是谁"（散户恐慌/机构行为），M7-3 要识别"对手在干什么"——**拉高出货（pump-and-dump）等操纵周期**。工具 `manipulation_detect` 已注册，但后端 ManipulationDetector 的 6 个信号中有多个是 TODO 桩或数据源错误，8/28 涨停池实测 **0 只达到 3 信号判定阈值**，实战不可用。

## 2. 实战验证发现的 6 处缺陷（全部修复）

| # | 缺陷 | 根因 | 修复 |
|---|------|------|------|
| 1 | fund_flow_repo 未注入 | 构造缺兜底 | 注入 FundFlowORMRepository |
| 2 | zt_count 解析失败 | akshare 涨停统计是 `"10/5"` 字符串非 dict | 三级解析：dict→str 连板数→兜底 `连板数` 字段 |
| 3 | 信号5 恒 False | TODO 桩 | 实现 `_check_fundamental_deviation`（EPS 亏损/PE>200） |
| 4 | 信号6 恒 False | TODO 桩 | 实现 `_check_high_volume_stagnation`（高位放量滞涨：≥90% 20日高 + 量比1.5x + 3日涨幅<5%） |
| 5 | 信号4 数据源错误 | 误用 fund_flow `main_net_inflow` 当成交量 | 重写用 kline 真实 volume（近3日/前7日 ≥3x） |
| 6 | 信号3 数据源错误 | ①`get_lhb_detail` 汇总无 `买方营业部` 字段关键词永失配 ②东财席位全称中间夹"股份有限公司"导致 `'银河证券绍兴'` 类关键词失配 | 改 `stock_lhb_stock_detail_em` 席位明细 + **剥离干扰词后 compact 匹配** + 汇总净买额占比>20% 兜底 |

另发现并修复：`_get_current_price` TODO 桩；**落库僵尸桩**——`AgentIntelligenceORMRepository.create_event/get_active_events/resolve_event` 原为日志 stub（不写库、不读库），导致操纵事件无法落库、抄底机会链路（`_scan_post_manipulation_opportunities`）永远空。已实现 ManipulationEvent ORM 模型 + 三个方法真实读写 `quant.manipulation_events`。

## 3. 6 信号定义（判定阈值：≥3 信号）

| # | 信号 | 逻辑 |
|---|------|------|
| 1 | 连续涨停 | zt_count ≥ 3 |
| 2 | 换手率异常 | > 30% |
| 3 | 龙虎榜游资席位 | 席位名匹配游资聚集地关键词（拉萨/绍兴/杭州/宁波等 14 个）+ 净买额占比>20% 兜底 |
| 4 | 成交量放大 | 近3日均量/前7日均量 ≥ 3x |
| 5 | 价格偏离基本面 | EPS 亏损连板 或 PE > 200 |
| 6 | 高位放量滞涨 | ≥90% 20日高 + 量比1.5x + 3日涨幅<5% |

阶段判定：accumulation / markup / distribution / collapse；风险等级 extreme/high/medium（distribution 或偏离>50% → extreme）。

## 4. 实战验证结果（真实数据）

### 8/28 涨停池（50 只扫描，12 只连板≥3）→ 判定 3 只操纵

| 标的 | 连板 | 触发信号 | 阶段 | 风险 |
|------|------|---------|------|------|
| 002742 冀衡医药 | 10 | 连板 + 换手42% + 龙虎榜游资 | markup | extreme |
| 000017 深中华A | 7 | 连板 + 龙虎榜游资 + 量能4.76x | markup | extreme |
| 600479 千金药业 | 3 | 连板 + 龙虎榜游资 + 量能放大 | markup | extreme |

### 9/1 实时检测（API 全链路）

```
GET /api/game/market/manipulation-detect → HTTP 200, 29s
002418 康盛股份: 连续5天涨停 + 龙虎榜游资 + 成交量放大 → markup, conf 0.95, action=avoid
（价格 5.39 vs 公允 4.13，偏离 +30.5%）→ 落库 quant.manipulation_events
```

## 5. 性能优化

- 龙虎榜查询仅对连板≥2 的股票执行（游资拉板必上榜；0/1连板查询纯属浪费实时网络调用）
- 席位查询重试 3→2 次、关键词覆盖 14 个游资聚集地
- **事件去重**：同 symbol 已有 active 事件则跳过落库（实测修复前每次检测重复落库 1 条，2 次 API 调用产生 6 条重复；修复后保持 1 条）

**全池检测耗时：162s → 37s（4.4x 提速）**，API 29s 返回。

## 6. 交付物

| 层 | 内容 |
|----|------|
| 后端服务 | `quantsys-v2/application/services/manipulation_detector.py`（6 信号 + 阶段/风险/公允价 + 落库 + 去重） |
| 落库 | `quant.manipulation_events` 表 + AgentIntelligenceORMRepository 真实读写（原日志 stub → 落地） |
| API | `GET /api/game/market/manipulation-detect`（FastAPI，已有，现可用） |
| Agent 工具 | `manipulation_detect`（competition 插件，M7-1 已注册） |
| 盘后例程 | `post-market-routine-live`（工作日 15:30）已接入第 5 步：操纵检测，active 事件→飞书高优告警 |

## 7. 经验沉淀

- **akshare 字段形状必须真实调用核实**：`涨停统计` 是字符串不是 dict；`get_lhb_detail` 无 `买方营业部`；`stock_lhb_stock_detail_em` 无数据日抛 `TypeError: 'NoneType' object is not subscriptable`（akshare 内部 bug）。
- **营业部全称匹配陷阱**：东财席位全称"中国银河证券股份有限公司绍兴鲁迅中路证券营业部"，`'银河证券绍兴'` 关键词直接失配 → 需剥离"股份有限公司/证券营业部"等干扰词再匹配。
- **落库必须验证字段映射**：ManipulationDetector 传参键（signals/current_price/fair_value/risk_level）与表字段（detection_signals/price_at_detection/fair_value_estimate）不一致会导致静默失败——实现前先 `\d table` 核对。
- **僵尸桩检测**：日志 stub（"保存操纵事件"只打日志不落库）会把"没生效"伪装成"在工作"，实战验证必查。

## 8. 下一步

- 操纵事件落库后，`_scan_post_manipulation_opportunities`（崩盘抄底机会）已有数据基础，待 collapse 案例出现后验证
- 将 manipulation_detect 接入盘后例程：每日收盘检测操纵标的，active 事件 → 飞书告警
- 龙虎榜关键词可继续扩充（如宁波桑田路等知名游资席位，8/28 深中华A 即有"国盛证券宁波桑田路"）
