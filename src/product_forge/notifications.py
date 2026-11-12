"""Approval-gated alert delivery for webhook and SMTP channels.

The registry stores only non-secret channel metadata. Secrets are resolved from
environment variables at delivery time and are never written to alert docs or
audit payloads.
"""

from __future__ import annotations

import json
import os
import smtplib
import time
import urllib.parse
import urllib.request
from email.message import EmailMessage
from typing import Any

from .domain.models import new_id, utcnow
from .errors import ValidationError
from .store.sqlite import Store


def register_channel(store: Store, *, kind: str, name: str, config: dict[str, Any]) -> dict[str, Any]:
    if kind == "webhook":
        url = str(config.get("url", ""))
        if urllib.parse.urlsplit(url).scheme != "https":
            raise ValidationError("webhook URL must use HTTPS")
        if not config.get("secret_env"):
            raise ValidationError("webhook secret_env is required")
    elif kind == "email":
        for key in ("host", "port", "from", "to", "password_env"):
            if key not in config:
                raise ValidationError(f"email config requires {key}")
    else:
        raise ValidationError(f"unsupported notification channel: {kind}")
    doc = {
        "id": new_id("chn"),
        "kind": kind,
        "name": name,
        "config": config,
        "enabled": False,
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    store.put_doc("notifications", doc, status="channel")
    return doc


def deliver_alert(
    store: Store,
    alert: dict[str, Any],
    channel: dict[str, Any],
    *,
    approved: bool = False,
    max_attempts: int = 3,
) -> dict[str, Any]:
    if not approved or not channel.get("enabled"):
        raise ValidationError("notification delivery requires an enabled, approved channel")
    cfg = channel["config"]
    attempts = []
    for attempt in range(1, max_attempts + 1):
        try:
            if channel["kind"] == "webhook":
                secret = os.environ.get(str(cfg["secret_env"]))
                if not secret:
                    raise ValidationError("webhook secret environment variable is missing")
                body = json.dumps({"schema": "productforge/Alert/v1", "alert": alert}).encode()
                req = urllib.request.Request(  # noqa: S310 — url from webhook config
                    str(cfg["url"]),
                    data=body,
                    method="POST",
                    headers={"Content-Type": "application/json", "X-Forge-Webhook-Secret": secret},
                )
                with urllib.request.urlopen(req, timeout=10) as response:  # noqa: S310 - HTTPS checked
                    if response.status < 200 or response.status >= 300:
                        raise OSError(f"webhook HTTP {response.status}")
            else:
                password = os.environ.get(str(cfg["password_env"]))
                if not password:
                    raise ValidationError("SMTP password environment variable is missing")
                msg = EmailMessage()
                msg["Subject"] = str(cfg.get("subject", "Product Forge alert"))
                msg["From"], msg["To"] = str(cfg["from"]), str(cfg["to"])
                msg.set_content(json.dumps(alert, ensure_ascii=False))
                with smtplib.SMTP(str(cfg["host"]), int(cfg["port"]), timeout=10) as smtp:
                    smtp.starttls()
                    smtp.login(str(cfg["username"]), password)
                    smtp.send_message(msg)
            alert = {
                **alert,
                "delivery": {
                    "state": "delivered",
                    "channel_id": channel["id"],
                    "attempts": attempt,
                    "delivered_at": utcnow(),
                },
            }
            store.put_doc("notifications", alert, status="delivered")
            return alert
        except Exception as exc:  # noqa: BLE001 - receipt records a redacted failure
            attempts.append({"attempt": attempt, "state": "failed", "error": str(exc)[:240], "at": utcnow()})
            if attempt < max_attempts:
                time.sleep(min(2 ** (attempt - 1), 4))
    result = {**alert, "delivery": {"state": "failed", "channel_id": channel["id"], "attempts": attempts}}
    store.put_doc("notifications", result, status="delivery_failed")
    return result
