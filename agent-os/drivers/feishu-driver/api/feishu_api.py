"""
Feishu API Client - Handle communication with Feishu Webhook API
"""
import os
import requests
import time
from typing import Dict, Any, Optional
from datetime import datetime


class FeishuAPI:
    """Feishu Webhook API client with retry mechanism"""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Feishu API client

        Args:
            webhook_url: Webhook URL, defaults to FEISHU_WEBHOOK_URL env var
        """
        self.webhook_url = webhook_url or os.getenv('FEISHU_WEBHOOK_URL')
        if not self.webhook_url:
            raise ValueError("Feishu webhook URL not provided. Set FEISHU_WEBHOOK_URL or pass webhook_url parameter.")

        self.max_retries = 3
        self.retry_delay = 1.0  # Initial delay in seconds
        self.timeout = 10

    def send_card(
        self,
        title: str,
        content: str,
        color: str = "blue"
    ) -> Dict[str, Any]:
        """
        Send an interactive card message to Feishu

        Args:
            title: Card title
            content: Card content (supports Markdown)
            color: Card header color (blue/green/red/orange/purple/grey)

        Returns:
            Dict with 'success' bool and 'response' or 'error'
        """
        message = self._build_card_message(title, content, color)
        return self._send_with_retry(message)

    def send_text(self, text: str) -> Dict[str, Any]:
        """
        Send a plain text message to Feishu

        Args:
            text: Plain text message

        Returns:
            Dict with 'success' bool and 'response' or 'error'
        """
        message = {
            "msg_type": "text",
            "content": {
                "text": text
            }
        }
        return self._send_with_retry(message)

    def _build_card_message(self, title: str, content: str, color: str) -> Dict[str, Any]:
        """Build interactive card message structure"""
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
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": content
                        }
                    },
                    {
                        "tag": "hr"
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"Sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            }
                        ]
                    }
                ]
            }
        }

    def _send_with_retry(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send message with exponential backoff retry

        Args:
            message: Message payload

        Returns:
            Dict with 'success' bool and 'response' or 'error'
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.webhook_url,
                    json=message,
                    timeout=self.timeout
                )

                # Check HTTP status
                response.raise_for_status()

                # Parse response
                result = response.json()

                # Check Feishu API response code
                if result.get('code') == 0:
                    return {
                        'success': True,
                        'response': result
                    }
                else:
                    # Feishu API returned error
                    error_msg = result.get('msg', 'Unknown Feishu API error')
                    last_error = f"Feishu API error (code={result.get('code')}): {error_msg}"

                    # Don't retry on certain errors
                    if result.get('code') in [9499, 19021]:  # Invalid webhook, permission denied
                        return {
                            'success': False,
                            'error': last_error,
                            'retries': attempt
                        }

            except requests.exceptions.Timeout as e:
                last_error = f"Request timeout: {str(e)}"

            except requests.exceptions.RequestException as e:
                last_error = f"Network error: {str(e)}"

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"

            # Exponential backoff before retry (except on last attempt)
            if attempt < self.max_retries - 1:
                delay = self.retry_delay * (2 ** attempt)
                time.sleep(delay)

        # All retries exhausted
        return {
            'success': False,
            'error': last_error,
            'retries': self.max_retries
        }
