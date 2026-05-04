from __future__ import annotations

from raatverse_agent.notifications.models import NotificationResult


def format_notification_result(result: NotificationResult) -> str:
    return (
        "RaatVerse notification result\n"
        f"Provider: {result.provider}\n"
        f"Sent: {result.sent}\n"
        f"Status code: {result.status_code or 'None'}\n"
        f"Message: {result.message}"
    )
