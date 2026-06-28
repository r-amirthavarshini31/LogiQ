"""
LogiQ Alerting Module
Sends alert notifications to Slack and Discord via webhooks.
"""

import os
import json
import requests
from datetime import datetime

from database.db import get_setting


def send_slack_alert(anomaly):
    """
    Send an alert notification to Slack via webhook.

    Args:
        anomaly (dict): Anomaly data with message, level, category, explanation.

    Returns:
        dict: {'success': bool, 'message': str}
    """
    webhook_url = os.getenv('SLACK_WEBHOOK_URL') or get_setting('slack_webhook_url')
    if not webhook_url:
        return {'success': False, 'message': 'Slack webhook URL not configured'}

    level = anomaly.get('level', 'error').upper()
    level_emoji = {
        'CRITICAL': ':rotating_light:',
        'ERROR': ':x:',
        'WARNING': ':warning:',
        'INFO': ':information_source:',
    }.get(level, ':bell:')

    color = {
        'CRITICAL': '#DC2626',
        'ERROR': '#EF4444',
        'WARNING': '#F59E0B',
        'INFO': '#3B82F6',
    }.get(level, '#6B7280')

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{level_emoji} LogiQ Alert — {level} Anomaly Detected"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Category:*\n{anomaly.get('category', 'Unknown')}"},
                    {"type": "mrkdwn", "text": f"*Severity:*\n{level}"},
                    {"type": "mrkdwn", "text": f"*Detected At:*\n{anomaly.get('timestamp', 'N/A')}"},
                    {"type": "mrkdwn", "text": f"*Status:*\n{anomaly.get('status', 'open').title()}"},
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Message:*\n```{anomaly.get('message', 'No message')[:500]}```"
                }
            },
        ],
        "attachments": [{
            "color": color,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*AI Explanation:*\n{anomaly.get('explanation', 'No explanation available')[:800]}"
                    }
                }
            ]
        }]
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10,
        )
        if response.status_code == 200:
            return {'success': True, 'message': 'Slack alert sent successfully'}
        else:
            return {'success': False, 'message': f'Slack API returned status {response.status_code}'}
    except Exception as e:
        return {'success': False, 'message': f'Failed to send Slack alert: {str(e)}'}


def send_discord_alert(anomaly):
    """
    Send an alert notification to Discord via webhook.

    Args:
        anomaly (dict): Anomaly data with message, level, category, explanation.

    Returns:
        dict: {'success': bool, 'message': str}
    """
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL') or get_setting('discord_webhook_url')
    if not webhook_url:
        return {'success': False, 'message': 'Discord webhook URL not configured'}

    level = anomaly.get('level', 'error').upper()
    color = {
        'CRITICAL': 0xDC2626,
        'ERROR': 0xEF4444,
        'WARNING': 0xF59E0B,
        'INFO': 0x3B82F6,
    }.get(level, 0x6B7280)

    payload = {
        "username": "LogiQ",
        "avatar_url": "https://cdn.jsdelivr.net/gh/lucide-icons/lucide/icons/search.svg",
        "embeds": [{
            "title": f"🔔 {level} Anomaly Detected",
            "description": anomaly.get('message', 'No message')[:500],
            "color": color,
            "fields": [
                {"name": "Category", "value": anomaly.get('category', 'Unknown'), "inline": True},
                {"name": "Severity", "value": level, "inline": True},
                {"name": "Status", "value": anomaly.get('status', 'open').title(), "inline": True},
                {"name": "Explanation", "value": anomaly.get('explanation', 'No explanation')[:500], "inline": False},
            ],
            "footer": {
                "text": f"LogiQ — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            },
            "timestamp": datetime.utcnow().isoformat(),
        }]
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=10,
        )
        if response.status_code in (200, 204):
            return {'success': True, 'message': 'Discord alert sent successfully'}
        else:
            return {'success': False, 'message': f'Discord API returned status {response.status_code}'}
    except Exception as e:
        return {'success': False, 'message': f'Failed to send Discord alert: {str(e)}'}


def send_alert(anomaly):
    """
    Send alert to all configured channels.

    Args:
        anomaly (dict): Anomaly data.

    Returns:
        dict: {'results': list[dict]} — results from each channel attempt.
    """
    results = []

    # Try Slack
    slack_result = send_slack_alert(anomaly)
    results.append({'channel': 'Slack', **slack_result})

    # Try Discord
    discord_result = send_discord_alert(anomaly)
    results.append({'channel': 'Discord', **discord_result})

    any_success = any(r['success'] for r in results)
    return {
        'success': any_success,
        'results': results,
        'message': 'Alerts sent' if any_success else 'No alerts could be sent — check webhook configuration in Settings',
    }
