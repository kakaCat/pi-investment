"""中枢识别器 - 识别线段重叠形成的中枢"""
from typing import List, Optional, Tuple
from .types import Segment, ZhongShu


class ZhongShuIdentifier:
    """
    中枢识别器

    职责：识别中枢及动态变化
    规则：至少3个线段的重叠区间
    """

    def identify_zhongshus(self, segments: List[Segment]) -> List[ZhongShu]:
        """
        识别中枢

        流程：
        1. 滑动窗口（3个线段）
        2. 计算重叠区间
        3. 验证重叠有效性
        4. 尝试扩展中枢
        """
        if len(segments) < 3:
            return []

        zhongshus = []
        i = 0

        while i <= len(segments) - 3:
            # 尝试构建中枢
            window_segments = segments[i:i+3]
            overlap = self._calculate_overlap(window_segments)

            if overlap is not None:
                # 有效中枢，尝试扩展
                zh_low, zh_high = overlap
                zh_segments = window_segments.copy()
                j = i + 3

                # 扩展中枢（检查后续线段是否仍然重叠）
                while j < len(segments):
                    extended_segments = zh_segments + [segments[j]]
                    extended_overlap = self._calculate_overlap(extended_segments)
                    if extended_overlap is not None:
                        zh_segments.append(segments[j])
                        zh_low, zh_high = extended_overlap
                        j += 1
                    else:
                        break

                # 创建中枢对象
                zhongshus.append(ZhongShu(
                    segments=zh_segments,
                    high=zh_high,
                    low=zh_low,
                    start_index=zh_segments[0].start_index,
                    end_index=zh_segments[-1].end_index,
                    type='震荡'  # 简化版，暂不区分扩展/移动
                ))

                # 跳到中枢之后
                i = j
            else:
                i += 1

        return zhongshus

    def _calculate_overlap(self, segments: List[Segment]) -> Optional[Tuple[float, float]]:
        """
        计算线段重叠区间

        Returns:
            (overlap_low, overlap_high) 或 None（无重叠）
        """
        overlap_low = max(seg.low for seg in segments)
        overlap_high = min(seg.high for seg in segments)

        if overlap_low < overlap_high:
            return (overlap_low, overlap_high)
        else:
            return None
