# M7-2 散户恐慌代理指标交付（2026-09-01）

> 署名：investor w-8366e526
> 状态：✅ 完成（M7 完成度 33% → 67%）

---

## 1. 背景与问题

原 opponent_behavior 的散户情绪是**离散三档**跳变：
- `panic_selling`（散户净流出>30亿）→ 情绪 20
- `fomo_buying`（净流入>30亿）→ 情绪 80
- 其余 → 中性 50

问题：①只有 3 个离散值，无法区分恐慌程度；②只看散户资金流一个维度，涨跌家数/量能/波动率等信息全部浪费。

## 2. 方案：连续 0-100 恐慌指数（五维合成）

| 维度 | 权重 | 数据源 | 恐慌分映射 |
|------|------|--------|-----------|
| 散户资金流 | 30% | stock_fund_flow（小单+中单） | 流出30亿=100，流入30亿=0 |
| 涨跌家数比 | 25% | market_sentiment_daily.ad_ratio | 普跌(≤0.6)=100，普涨(≥2.0)=0 |
| 恐慌贪婪指数 | 20% | market_sentiment_daily.fear_greed_index | fg=100 - fg |
| 量能 | 15% | market_sentiment_daily.volume_ratio | 地量(≤0.5)=+10 |
| 波动率 | 10% | market_sentiment_daily.volatility | ≥2.5%=100，≤0.8%=0 |

**等级**：≥70 恐慌 / 50-70 偏恐慌 / 30-50 偏贪婪 / <30 贪婪。缺失维度按剩余权重归一（不造数据，degraded 显式标记）。

## 3. 交付物

| 层 | 内容 |
|----|------|
| 后端服务 | `quantsys-v2/application/services/retail_panic_index_service.py`（合成 + 等级 + 序列） |
| API | `GET /api/market/perception/panic-index`（单日）/ `GET /api/market/perception/panic-index/series?days=N`（序列） |
| client | `getRetailPanicIndex({trade_date?, days?})` |
| Agent 工具 | `retail_panic_index`（competition 插件，单日/序列双模式） |

## 4. 实测数据（真实调用）

```
8/28: panic_index=19.6  greed（fg=95 极度贪婪吻合，ad_ratio=2.42 普涨）
8/27: panic_index=22.0  greed
8/25: panic_index=20.9  greed
8/24: panic_index=56.6  leaning_panic（此前一日确有恐慌迹象）
```

序列能区分恐慌-贪婪周期 → 可用于"散户恐慌=收割机会、散户贪婪=追高风险"的博弈判断。

## 5. 验证

- schema 冒烟 19/19 ✅
- 工具单测 18/18（含新工具 7 个：校验/映射/序列/降级/异常）✅
- 真实 API 调用（panic-index + series）✅

## 6. 下一步

- M7-3 操纵周期识别：manipulation_detect 工具已注册，后端检测逻辑实战验证
- M7-2 应用：恐慌指数 ≥70 时结合 opponent_behavior 判断"收割散户恐慌"标的；盘后例程可每日落库恐慌指数
