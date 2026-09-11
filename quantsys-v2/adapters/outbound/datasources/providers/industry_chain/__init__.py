"""产业链出站 provider（RFC 015 §2.3 多源矩阵）

通道矩阵（§1.5.2 硬约束：每类数据的 provider 必须来自不同上游通道）：

| 优先级 | Provider (name)            | 上游通道            | 提供              | 失败降级 |
|--------|----------------------------|---------------------|-------------------|----------|
| 0 权威 | curated                    | 人工策展 seed YAML  | 环节拓扑+代表标的 | **不可降级**（拓扑唯一来源，缺失即 fail-loud） |
| 1      | eastmoney_revenue          | 东财 F10 emweb      | 主营构成（带占比）| → ths_revenue |
| 2      | ths_revenue                | 同花顺 F10 经营分析 | 产品构成（无占比）| → database_chain |
| 3      | akshare_concept            | 新浪行业（经 akshare）| 行业成分候选（低置信）| → database_chain |
| 4      | database_chain             | quant.industry_chain* | 上次成功图谱    | stale-while-error |

打样记录（2026-09-11，本机实测）与不可用通道见各模块 docstring。
"""
