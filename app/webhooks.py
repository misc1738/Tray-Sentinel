"""Webhook support for event notifications."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from enum import Enum

import httpx
from pydantic import BaseModel, HttpUrl


class WebhookEvent(str, Enum):
    """Webhook event types."""
    EVIDENCE_INTAKE = "evidence.intake"
    CUSTODY_ACTION = "custody.action"
    ENDORSEMENT_REQUEST = "endorsement.request"
    ENDORSEMENT_COMPLETE = "endorsement.complete"
    VERIFICATION_RESULT = "verification.result"
    REPORT_GENERATED = "report.generated"
    ALERT_CREATED = "alert.created"
    INCIDENT_OPENED = "incident.opened"
    INCIDENT_RESOLVED = "incident.resolved"


class WebhookSubscription(BaseModel):
    """Webhook subscription model."""
    subscription_id: str
    url: HttpUrl
    events: list[str]
    active: bool
    secret: Optional[str] = None
    created_at: str


class WebhookPayload(BaseModel):
    """Webhook event payload."""
    event: str
    timestamp: str
    subscription_id: str
    data: dict
    signature: Optional[str] = None


class WebhookManager:
    """Manage webhooks and event delivery."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.init_tables()
        self.http_client = httpx.AsyncClient(timeout=10.0)

    def init_tables(self):
        """Initialize webhook tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_subscriptions (
                    subscription_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    events TEXT NOT NULL,
                    active BOOLEAN DEFAULT 1,
                    secret TEXT,
                    created_at TEXT NOT NULL,
                    last_triggered_at TEXT,
                    failure_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_deliveries (
                    delivery_id TEXT PRIMARY KEY,
                    subscription_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    status_code INTEGER,
                    response_body TEXT,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    delivered_at TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(subscription_id) REFERENCES webhook_subscriptions(subscription_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_subscriptions_active ON webhook_subscriptions(active);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_deliveries_subscription ON webhook_deliveries(subscription_id);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_deliveries_created ON webhook_deliveries(created_at);
                """
            )
            conn.commit()

    def create_subscription(
        self,
        url: str,
        events: list[str],
        secret: Optional[str] = None,
    ) -> WebhookSubscription:
        """Create a new webhook subscription."""
        subscription_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc).isoformat()
        events_json = json.dumps(events)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO webhook_subscriptions
                (subscription_id, url, events, active, secret, created_at)
                VALUES (?, ?, ?, 1, ?, ?)
                """,
                (subscription_id, url, events_json, secret, now),
            )
            conn.commit()

        return WebhookSubscription(
            subscription_id=subscription_id,
            url=url,
            events=events,
            active=True,
            secret=secret,
            created_at=now,
        )

    def get_subscriptions(self, active_only: bool = True) -> list[WebhookSubscription]:
        """Get all webhook subscriptions."""
        query = "SELECT * FROM webhook_subscriptions"
        if active_only:
            query += " WHERE active = 1"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query)
            rows = cursor.fetchall()

        subscriptions = []
        for row in rows:
            subscriptions.append(
                WebhookSubscription(
                    subscription_id=row["subscription_id"],
                    url=row["url"],
                    events=json.loads(row["events"]),
                    active=bool(row["active"]),
                    secret=row["secret"],
                    created_at=row["created_at"],
                )
            )

        return subscriptions

    def delete_subscription(self, subscription_id: str) -> bool:
        """Delete a webhook subscription."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM webhook_subscriptions WHERE subscription_id = ?",
                (subscription_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def toggle_subscription(self, subscription_id: str, active: bool) -> bool:
        """Enable/disable a webhook subscription."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE webhook_subscriptions SET active = ? WHERE subscription_id = ?",
                (int(active), subscription_id),
            )
            conn.commit()

        return True

    async def dispatch_event(
        self,
        event: str,
        data: dict,
        actor_user_id: Optional[str] = None,
    ) -> int:
        """Dispatch event to all subscribed webhooks.
        
        Returns count of successful deliveries.
        """
        timestamp = datetime.now(tz=timezone.utc).isoformat()
        subscriptions = self.get_subscriptions(active_only=True)
        successful = 0

        for sub in subscriptions:
            if event not in sub.events:
                continue

            delivery_id = str(uuid.uuid4())
            payload = WebhookPayload(
                event=event,
                timestamp=timestamp,
                subscription_id=sub.subscription_id,
                data=data,
            )

            try:
                response = await self.http_client.post(
                    str(sub.url),
                    json=payload.model_dump(),
                    headers={"X-Webhook-Event": event},
                    timeout=10.0,
                )

                status_code = response.status_code
                response_body = response.text[:500] if response.text else ""
                error_msg = None

                if 200 <= response.status_code < 300:
                    successful += 1
                    delivered_at = datetime.now(tz=timezone.utc).isoformat()
                else:
                    error_msg = f"HTTP {status_code}"
                    delivered_at = None

            except Exception as e:
                status_code = None
                response_body = None
                error_msg = str(e)[:200]
                delivered_at = None

            # Record delivery
            self._record_delivery(
                delivery_id=delivery_id,
                subscription_id=sub.subscription_id,
                event=event,
                status_code=status_code,
                response_body=response_body,
                error_message=error_msg,
                delivered_at=delivered_at,
            )

        return successful

    def _record_delivery(
        self,
        delivery_id: str,
        subscription_id: str,
        event: str,
        status_code: Optional[int],
        response_body: Optional[str],
        error_message: Optional[str],
        delivered_at: Optional[str],
    ) -> None:
        """Record webhook delivery attempt."""
        now = datetime.now(tz=timezone.utc).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO webhook_deliveries
                (delivery_id, subscription_id, event, status_code, response_body,
                 error_message, delivered_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    delivery_id,
                    subscription_id,
                    event,
                    status_code,
                    response_body,
                    error_message,
                    delivered_at,
                    now,
                ),
            )
            conn.commit()

    def get_delivery_history(
        self,
        subscription_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get webhook delivery history."""
        query = "SELECT * FROM webhook_deliveries WHERE 1=1"
        params = []

        if subscription_id:
            query += " AND subscription_id = ?"
            params.append(subscription_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
