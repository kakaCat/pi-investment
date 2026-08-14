"""
Notification Manager - Manage user/channel mappings and notification routing
"""
import os
from typing import Dict, Any, Optional
from api.feishu_api import FeishuAPI


class NotificationManager:
    """Manage notification routing to users and channels"""

    def __init__(self):
        """Initialize notification manager with user/channel mappings"""
        # User to webhook mapping
        self.user_webhooks = {
            'yunpeng': os.getenv('FEISHU_WEBHOOK_URL'),
            # Add more users as needed
        }

        # Channel to webhook mapping
        self.channel_webhooks = {
            'general': os.getenv('FEISHU_WEBHOOK_URL'),
            'trading': os.getenv('FEISHU_WEBHOOK_TRADING'),
            'alerts': os.getenv('FEISHU_WEBHOOK_ALERTS'),
            # Add more channels as needed
        }

    def send_to_user(
        self,
        user: str,
        title: str,
        message: str,
        color: str = "blue",
        webhook_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send notification to a specific user

        Args:
            user: User name
            title: Notification title
            message: Notification message (Markdown supported)
            color: Card header color
            webhook_override: Override webhook URL

        Returns:
            Dict with 'success' bool and result details
        """
        # Get webhook for user
        webhook_url = webhook_override or self.user_webhooks.get(user)

        if not webhook_url:
            return {
                'success': False,
                'error': f'User not found: {user}. Available users: {", ".join(self.user_webhooks.keys())}'
            }

        # Send notification
        api = FeishuAPI(webhook_url=webhook_url)
        return api.send_card(title=title, content=message, color=color)

    def send_to_channel(
        self,
        channel: str,
        title: str,
        message: str,
        color: str = "blue",
        webhook_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send notification to a specific channel

        Args:
            channel: Channel name
            title: Notification title
            message: Notification message (Markdown supported)
            color: Card header color
            webhook_override: Override webhook URL

        Returns:
            Dict with 'success' bool and result details
        """
        # Get webhook for channel
        webhook_url = webhook_override or self.channel_webhooks.get(channel)

        if not webhook_url:
            return {
                'success': False,
                'error': f'Channel not found: {channel}. Available channels: {", ".join(self.channel_webhooks.keys())}'
            }

        # Send notification
        api = FeishuAPI(webhook_url=webhook_url)
        return api.send_card(title=title, content=message, color=color)

    def list_users(self) -> list:
        """List available users"""
        return list(self.user_webhooks.keys())

    def list_channels(self) -> list:
        """List available channels"""
        return list(self.channel_webhooks.keys())

    def add_user(self, user: str, webhook_url: str):
        """Add or update user webhook mapping"""
        self.user_webhooks[user] = webhook_url

    def add_channel(self, channel: str, webhook_url: str):
        """Add or update channel webhook mapping"""
        self.channel_webhooks[channel] = webhook_url
