from __future__ import annotations

import httpx

from raatverse_agent.config import Settings
from raatverse_agent.notifications.models import NotificationMessage, NotificationResult


class NotificationError(RuntimeError):
    pass


class MockNotifier:
    provider = "mock"

    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, message: NotificationMessage) -> NotificationResult:
        return NotificationResult(
            provider=self.provider,
            sent=True,
            message=f"Mock notification accepted: {message.title}",
        )


class WebhookNotifier:
    provider = "webhook"

    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, message: NotificationMessage) -> NotificationResult:
        if not self.settings.notification_webhook_url:
            raise NotificationError("NOTIFICATION_WEBHOOK_URL is required for webhook notifications.")
        try:
            response = httpx.post(
                self.settings.notification_webhook_url,
                json=message.model_dump(mode="json"),
                timeout=15,
            )
        except httpx.HTTPError as exc:
            raise NotificationError(f"Webhook notification failed: {exc}") from exc
        if response.status_code >= 400:
            raise NotificationError(
                f"Webhook notification failed with HTTP {response.status_code}: {response.text[:300]}"
            )
        return NotificationResult(
            provider=self.provider,
            sent=True,
            message="Webhook notification sent.",
            status_code=response.status_code,
        )


def create_notifier(settings: Settings, *, mock: bool = False):
    provider = settings.notification_provider.lower().strip()
    if mock or provider == "mock":
        return MockNotifier(settings)
    if provider == "webhook":
        return WebhookNotifier(settings)
    raise NotificationError(f"Unsupported NOTIFICATION_PROVIDER '{settings.notification_provider}'.")
