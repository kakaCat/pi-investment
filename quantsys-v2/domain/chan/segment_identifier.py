"""线段识别器 - 识别线段"""
from typing import List
from .types import Bi, Segment


class SegmentIdentifier:
    """
    线段识别器

    职责：识别线段
    规则（简化版）：
    - 至少3笔构成
    - 笔的方向交替（上笔→下笔→上笔 或 下笔→上笔→下笔）
    """

    def identify_segments(self, bis: List[Bi]) -> List[Segment]:
        """
        识别线段

        流程：
        1. 遍历笔序列
        2. 找到至少3笔构成的有效线段
        3. 验证方向一致性
        4. 计算线段高低点
        """
        if len(bis) < 3:
            return []

        segments = []
        i = 0

        while i <= len(bis) - 3:
            # 尝试构建线段
            segment_bis = [bis[i], bis[i+1], bis[i+2]]

            if self._is_valid_segment(segment_bis):
                # 有效线段，尝试扩展
                j = i + 3
                while j < len(bis):
                    extended_bis = segment_bis + [bis[j]]
                    if self._is_valid_segment(extended_bis):
                        segment_bis.append(bis[j])
                        j += 1
                    else:
                        break

                # 构建线段对象
                direction = segment_bis[0].direction
                start_index = segment_bis[0].start_fenxing.index
                end_index = segment_bis[-1].end_fenxing.index

                highs = [bi.high for bi in segment_bis]
                lows = [bi.low for bi in segment_bis]

                segments.append(Segment(
                    direction=direction,
                    bis=segment_bis,
                    start_index=start_index,
                    end_index=end_index,
                    high=max(highs),
                    low=min(lows)
                ))

                # 移动到下一个潜在线段起点
                i = j
            else:
                i += 1

        return segments

    def _is_valid_segment(self, bis: List[Bi]) -> bool:
        """验证是否构成有效线段"""
        if len(bis) < 3:
            return False

        # 检查方向交替
        first_direction = bis[0].direction
        for i in range(len(bis)):
            expected_direction = first_direction if i % 2 == 0 else ('down' if first_direction == 'up' else 'up')
            if bis[i].direction != expected_direction:
                return False

        return True
