#!/usr/bin/env python3
"""
Feishu Driver - CLI tool for sending notifications via Feishu
"""
import click
import json
import sys
from api.feishu_api import FeishuAPI
from manager.notification_manager import NotificationManager


@click.group()
@click.version_option(version='1.0.0')
def cli():
    """Feishu Driver - Send notifications to Feishu"""
    pass


@cli.command()
@click.option('--user', help='User name to send notification to')
@click.option('--channel', help='Channel name to send notification to')
@click.option('--title', required=True, help='Notification title')
@click.option('--message', required=True, help='Notification message (supports Markdown)')
@click.option('--color', default='blue', help='Card header color (blue/green/red/orange)')
@click.option('--webhook', help='Override webhook URL (optional)')
def send(user, channel, title, message, color, webhook):
    """Send a notification to Feishu"""

    if not user and not channel:
        click.echo("Error: Either --user or --channel must be specified", err=True)
        sys.exit(1)

    if user and channel:
        click.echo("Error: Cannot specify both --user and --channel", err=True)
        sys.exit(1)

    try:
        # Initialize manager
        manager = NotificationManager()

        # Send notification
        if user:
            result = manager.send_to_user(
                user=user,
                title=title,
                message=message,
                color=color,
                webhook_override=webhook
            )
        else:
            result = manager.send_to_channel(
                channel=channel,
                title=title,
                message=message,
                color=color,
                webhook_override=webhook
            )

        if result['success']:
            click.echo("Notification sent successfully")
            sys.exit(0)
        else:
            click.echo(f"Error: {result.get('error', 'Unknown error')}", err=True)
            sys.exit(2)

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(3)


@cli.command()
@click.option('--title', required=True, help='Test notification title')
@click.option('--webhook', help='Webhook URL to test')
def test(title, webhook):
    """Send a test notification"""

    try:
        api = FeishuAPI(webhook_url=webhook)
        result = api.send_card(
            title=title,
            content="This is a test notification from Feishu Driver",
            color="blue"
        )

        if result['success']:
            click.echo("✓ Test notification sent successfully")
            click.echo(f"  Response: {json.dumps(result['response'], ensure_ascii=False)}")
            sys.exit(0)
        else:
            click.echo(f"✗ Test failed: {result.get('error')}", err=True)
            sys.exit(2)

    except Exception as e:
        click.echo(f"✗ Test failed: {str(e)}", err=True)
        sys.exit(3)


if __name__ == '__main__':
    cli()
