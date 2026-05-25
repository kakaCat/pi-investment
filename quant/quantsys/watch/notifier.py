"""Notification adapters for watch decisions."""

from __future__ import annotations

import json
import urllib.request


class FeishuNotifier:
    """Send watch events to Feishu through an incoming webhook."""

    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = webhook_url

    def notify(self, title: str, payload: dict) -> None:
        if not self.webhook_url:
            return

        body = {
            "msg_type": "text",
            "content": {"text": f"{title}\n{json.dumps(payload, ensure_ascii=False)}"},
        }
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5):
            return
