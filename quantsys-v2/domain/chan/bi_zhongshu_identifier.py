"""笔中枢识别器——连续 3+ 笔重叠构成中枢（弃用线段层后的核心结构）"""
from typing import List
from .types import Bi, BiZhongShu


class BiZhongShuIdentifier:
    """
    规则：
    - 成立：连续 3 笔重叠，ZG = min(三笔高点) > ZD = max(三笔低点)
    - 延续：后续笔仍与 [ZD, ZG] 有重叠（bi.low < ZG 且 bi.high > ZD）则并入
    - ZG/ZD 由前 3 笔锁定，延续不修改
    """

    def identify(self, bis: List[Bi]) -> List[BiZhongShu]:
        if len(bis) < 3:
            return []

        zhongshus: List[BiZhongShu] = []
        i = 0
        while i <= len(bis) - 3:
            window = bis[i:i + 3]
            zg = min(b.high for b in window)
            zd = max(b.low for b in window)

            if zg > zd:
                members = list(window)
                j = i + 3
                while j < len(bis):
                    b = bis[j]
                    if b.low < zg and b.high > zd:   # 仍有重叠 → 延续
                        members.append(b)
                        j += 1
                    else:
                        break
                zhongshus.append(BiZhongShu(
                    zg=zg, zd=zd,
                    gg=max(b.high for b in members),
                    dd=min(b.low for b in members),
                    start_bi_idx=i, end_bi_idx=j - 1,
                    bis=members,
                ))
                i = j
            else:
                i += 1

        return zhongshus
