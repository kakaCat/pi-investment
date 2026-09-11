"""人工策展政策兜底 seed（RFC 015 §3.3 政策事件优先级 3：**最低保障**）

## 为什么必须有它（不是"可选补充"）
政策源没有稳定免费 API（本机已有东财 WAF 前例：gov.cn 政策文件库 403、上交所 SOA 缺 siteId、
深交所 CATALOGID 失效）。若两条自动通道同时挂掉而链路"静默返回空"，
/api/events/feed?type=policy 会给出"没有政策"的结论——**而事实是"没抓到"**，
两者无法区分（RFC §3.3 硬要求）。本 provider 因此在链尾提供**人工核对过的**最低保障集合。

## 与其它 provider 的区别（可审计性）
1. 每条都带 operator 标记（谁策展的）与 evidence（核验来源与口径），即"人签过字"，
   与机器抓取的数据在落库后仍可区分（写进 raw 字段）。
2. seed 条目**永不覆盖**自动通道的结果：本 provider 位于注册表最后一位，
   前面任一通道成功返回即不会走到这里（manager 的 failover 语义）。
3. seed 只放**真实核验过的**条目，禁止写入未经核验的"预期政策"。

## 当前 seed 内容与核验依据（2026-09-11 打样时从真实响应中摘取，非编造）
- 条目 1/2 来自 https://www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json 的实测响应
  （HTTP 200，1094 条，字段 TITLE/URL/DOCRELPUBTIME），原文与日期逐字核对。
- 条目 3 来自 https://www.ndrc.gov.cn/xxgk/zcfb/fzggwl/ 的实测列表
  （href=./202607/t20260731_1406815.html，标题含"2026年第45号令"）。

维护纪律：seed 有保质期。operator 应在新政策出台后补充条目，并删除已无时效价值的旧条目
（否则它会把陈年政策当"最新政策"反复投递）。SEED_AS_OF 记录本次策展时点。
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from domain.events.model import AUTHORITY_MANUAL
from domain.events.ports.IMarketEventProvider import IMarketEventProvider

logger = logging.getLogger(__name__)

#: seed 策展时点（人工核验的时间，不是条目生效时间）
SEED_AS_OF = '2026-09-11'
OPERATOR = 'investor/w-f436d4ea'

#: 人工策展条目（每条必须带 operator 与 evidence；url 为核验来源）
SEED_POLICIES: List[Dict] = [
    {
        'title': '市场监督管理所条例',
        'effective_date': '2026-09-11',
        'url': 'https://www.gov.cn/zhengce/content/202609/content_7080735.htm',
        'summary': '国务院政策：市场监督管理所条例（基层市场监管机构设置与职责）',
        'industries': ['市场监管'],
        'operator': OPERATOR,
        'evidence': 'gov.cn ZUIXINZHENGCE.json 实测响应（2026-09-11 抓取，TITLE/URL/DOCRELPUBTIME 逐字核对）',
    },
    {
        'title': '国务院办公厅关于加强中小企业回款难问题治理有关工作的通知',
        'effective_date': '2026-09-10',
        'url': 'https://www.gov.cn/zhengce/content/202609/content_7080627.htm',
        'summary': '国务院办公厅政策：治理中小企业回款难（应收账款/账期监管）',
        'industries': ['中小企业', '建筑装饰', '机械'],
        'operator': OPERATOR,
        'evidence': 'gov.cn ZUIXINZHENGCE.json 实测响应（2026-09-11 抓取，原文核对）',
    },
    {
        'title': '《国家发展改革委关于修改、废止一批规章和行政规范性文件的决定》 2026年第45号令',
        'effective_date': '2026-07-31',
        'url': 'https://www.ndrc.gov.cn/xxgk/zcfb/fzggwl/202607/t20260731_1406815.html',
        'summary': '发改委规范性文件清理（修改、废止一批规章）',
        'industries': [],
        'operator': OPERATOR,
        'evidence': 'ndrc.gov.cn/zcfb/fzggwl/ 实测列表（2026-09-11 抓取，href 中的 t20260731 为发布日期）',
    },
]


class ManualPolicySeedProvider(IMarketEventProvider):
    """人工策展政策兜底（政策事件通道 3；权威度 40，带 operator 标记）"""

    def __init__(self, seed: Optional[List[Dict]] = None):
        self._seed = seed if seed is not None else SEED_POLICIES
        self.last_error: Optional[str] = None
        self.injected_at: Optional[str] = None

    @property
    def name(self) -> str:
        return 'manual_policy_seed'

    # ------------------------------------------------------------------ 政策

    def fetch_policy(self) -> Optional[List[Dict]]:
        """返回人工策展条目（**永远成功**——它是最后一道保障，除非 seed 被清空）"""
        self.last_error = None
        if not self._seed:
            # seed 空 = 兜底能力丧失，必须显式失败（否则链路会以"无政策"收场）
            self.last_error = 'manual seed 为空：政策兜底能力缺失（SEED_POLICIES 被清空？）'
            return None
        self.injected_at = datetime.now().isoformat(timespec='seconds')
        rows: List[Dict] = []
        for item in self._seed:
            effective = str(item.get('effective_date') or '').strip()[:10]
            try:
                datetime.strptime(effective, '%Y-%m-%d')
            except ValueError:
                logger.warning('manual seed 条目日期非法，已跳过: %r', item)
                continue
            rows.append({
                'scope': None,
                'type': 'policy',
                'title': str(item.get('title') or '').strip(),
                'effective_date': effective,
                'announce_date': effective,
                'importance': 2,
                'symbols': list(item.get('symbols') or []),
                'industries': list(item.get('industries') or []),
                'source': self.name,
                'url': str(item.get('url') or ''),
                'summary': str(item.get('summary') or ''),
                'external_id': 'manual-seed:' + str(item.get('url') or item.get('title') or ''),
                'authority': AUTHORITY_MANUAL,
                'raw': {
                    'operator': item.get('operator') or OPERATOR,
                    'evidence': item.get('evidence') or '',
                    'seed_as_of': SEED_AS_OF,
                    'injected_at': self.injected_at,
                    'note': '人工策展兜底：本条由人核验后写入，非机器抓取',
                },
            })
        return rows

    # -------------------------------------------------------------- 个股事件

    def fetch_symbol_events(self, symbols: Optional[List[str]] = None) -> Optional[List[Dict]]:
        """人工 seed 只覆盖政策 → []（个股事件由自动通道负责）"""
        return []
