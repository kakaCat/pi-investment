"""
飞书格式化器基类

提供飞书消息格式化的通用方法：
1. 文本消息格式化
2. 卡片消息格式化
3. 颜色映射

Author: System
Date: 2026-09-02
"""

from typing import Dict, Any, List
from domain.notification.models.formatter import NotificationFormatter


class FeishuFormatter(NotificationFormatter):
    """飞书格式化器基类

    提供飞书消息格式化的通用方法，子类继承后实现具体业务逻辑
    """

    def format_text(self, text: str, mention_all: bool = False) -> Dict[str, Any]:
        """格式化为文本消息

        Args:
            text: 文本内容
            mention_all: 是否 @所有人

        Returns:
            Dict: 飞书文本消息载荷
        """
        if mention_all:
            text = '<at user_id="all">所有人</at> ' + text

        return {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }

    def format_card(
        self,
        title: str,
        content: str,
        color: str = "blue",
        actions: List[Dict] = None
    ) -> Dict[str, Any]:
        """格式化为卡片消息

        Args:
            title: 卡片标题
            content: 卡片内容（支持 Markdown）
            color: 标题颜色 blue/green/red/orange
            actions: 操作按钮列表

        Returns:
            Dict: 飞书卡片消息载荷
        """
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": content
                }
            }
        ]

        # 添加操作按钮
        if actions:
            action_elements = []
            for action in actions:
                button = {
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": action.get('label', 'Button')
                    },
                    "type": action.get('type', 'default')
                }

                # 添加 URL 或回调值
                if 'url' in action:
                    button['url'] = action['url']
                if 'value' in action:
                    button['value'] = action['value']

                action_elements.append(button)

            elements.append({
                "tag": "action",
                "actions": action_elements
            })

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title
                    },
                    "template": color
                },
                "elements": elements
            }
        }

    def get_urgency_color(self, priority_value: str) -> str:
        """根据优先级获取颜色

        Args:
            priority_value: 优先级值 low/normal/high/critical

        Returns:
            str: 飞书卡片颜色
        """
        color_map = {
            "low": "blue",
            "normal": "blue",
            "high": "orange",
            "critical": "red"
        }
        return color_map.get(priority_value, "blue")
