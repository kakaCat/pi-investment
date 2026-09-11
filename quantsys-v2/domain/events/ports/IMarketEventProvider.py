"""市场事件 provider 端口（一类一文件，对齐 domain/industry_chain/ports 的组织方式）

RFC 015 §3.1 / §1.5（2026-09-11，REQ-cf627b，P3）。实现方（出站适配器）必须：

1. 提供唯一 name（注册进 DataProviderManager 的 event_symbol_providers / event_policy_providers
   两个列表；name 全局唯一，因为健康统计与熔断器按 name 共享）
2. **失败与空结果语义分离**（§1.5.2 硬约束 5）：
   - 成功返回 List[dict]（可为空列表 = 该源确实无此类事件）；
   - 失败返回 None 且必须写 self.last_error（真异常必须抛或至少写 last_error）；
   - 2026-09-11 起 manager 的 _try_providers 已区分二者：无 last_error 的空结果
     **不计入健康分**（_record_empty），不会导致源被降权——所以"该标的确实没公告"可以放心返回 []。
3. **不支持的方法返回 []（不是 None）**：本端口同时声明 fetch_policy 与 fetch_symbol_events，
   个股 provider 不提供政策时返回 []（= "本源不提供此类数据"），返回 None 会被当作故障。

## 行契约（provider 与领域层之间的唯一接口，改这里 = 改所有 provider）

    {
      'scope': 'macro' | 'industry' | 'individual',
      'type': 'policy|earnings|unlock|placement|shareholder_meeting|regulatory|dividend|other',
      'title': str,                     # 事件标题（原文，勿改写；公司名前缀可保留，归一化在领域层做）
      'effective_date': 'YYYY-MM-DD',   # 事件发生/生效日（必填；解析不到就丢弃该行，勿编造今天）
      'announce_date': 'YYYY-MM-DD' | '',   # 公告日（可空，空串 = 源不提供）
      'importance': 1 | 2 | 3 | None,   # 可空 = 由领域层 infer_importance 推断
      'symbols': [str],                 # 关联标的（6 位代码）；宏观事件为空列表
      'industries': [str],              # 关联行业（可空）
      'source': str,                    # provider name（manager 也会按实际服务源覆盖审计）
      'url': str,                       # 原文链接（可空串）
      'summary': str,                   # 摘要/正文片段（可空串）
      'external_id': str,               # 上游唯一 ID（art_code / announcementId），用于审计与回溯
      'authority': int | None,          # 源权威度，缺省由 domain.model.source_authority 按 name 推断
      'raw': dict,                      # 原始行（落库 meta，供排障）
    }

**字段映射纪律**（2026-09-11 分红 provider 全 0 事故的根因是"按文档猜列名"）：
每个 provider 的字段映射必须先用**真实响应**打样核对，并把打样证据写进模块 docstring。
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class IMarketEventProvider(ABC):
    """政策/个股事件 provider 抽象基类"""

    #: 子类应初始化为 None；失败时写入原因字符串（供 manager 判定"真故障 vs 空结果"）
    last_error: Optional[str] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称（全局唯一，用于日志、source 归因、健康统计与熔断）"""
        pass

    @abstractmethod
    def fetch_policy(self) -> Optional[List[Dict]]:
        """政策类事件（国务院/发改委/证监会/交易所发布页，或人工策展 seed）

        Returns:
            成功返回 List[dict]（行契约见模块 docstring；空列表 = 本周期无新政策）；
            失败返回 None 且写 self.last_error；**不提供政策的能力返回 []**（不是 None）
        """
        pass

    @abstractmethod
    def fetch_symbol_events(self, symbols: Optional[List[str]] = None) -> Optional[List[Dict]]:
        """个股事件（公告/财报/解禁/定增/股东会…）

        Args:
            symbols: 目标标的列表。None = 由 provider 自行决定范围（如解禁排队可取全市场窗口）；
                     实现方应对大列表做上限保护（禁止无界循环打上游）

        Returns:
            成功返回 List[dict]（空列表 = 这些标的确实无事件）；
            失败返回 None 且写 self.last_error；**不提供个股事件的能力返回 []**
        """
        pass
