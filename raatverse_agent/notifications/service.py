from __future__ import annotations

from raatverse_agent.config import Settings
from raatverse_agent.notifications.models import NotificationMessage, NotificationResult
from raatverse_agent.notifications.providers import NotificationError, create_notifier


class NotificationService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, message: NotificationMessage, *, mock: bool = False, force: bool = False) -> NotificationResult:
        if not force and not self.settings.notifications_enabled and not mock:
            return NotificationResult(
                provider=self.settings.notification_provider,
                sent=False,
                message="Notifications are disabled.",
            )
        notifier = create_notifier(self.settings, mock=mock)
        return notifier.send(message)

    def event(
        self,
        *,
        event: str,
        title: str,
        body: str,
        data: dict | None = None,
        mock: bool = False,
        force: bool = False,
    ) -> NotificationResult:
        return self.send(
            NotificationMessage(
                event=event,
                title=title,
                body=body,
                data=data or {},
            ),
            mock=mock,
            force=force,
        )

    def maybe_event(
        self,
        *,
        enabled: bool,
        event: str,
        title: str,
        body: str,
        data: dict | None = None,
        mock: bool = False,
    ) -> NotificationResult | None:
        if not enabled:
            return None
        try:
            return self.event(event=event, title=title, body=body, data=data, mock=mock)
        except NotificationError:
            raise
