#!/usr/bin/env python3
"""Run an authorized SMTP smoke test without printing credentials.

Required environment: PRODUCT_FORGE_SMTP_HOST, PRODUCT_FORGE_SMTP_PORT,
PRODUCT_FORGE_SMTP_USERNAME, PRODUCT_FORGE_SMTP_PASSWORD,
PRODUCT_FORGE_SMTP_FROM and PRODUCT_FORGE_SMTP_TO.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from product_forge.notifications import deliver_alert, register_channel
from product_forge.store.sqlite import Store


def main() -> int:
    required = ("HOST", "PORT", "USERNAME", "PASSWORD", "FROM", "TO")
    missing = [name for name in required if not os.environ.get(f"PRODUCT_FORGE_SMTP_{name}")]
    if missing:
        print(json.dumps({"status": "blocked", "missing_env": missing}))
        return 2
    password_env = "PRODUCT_FORGE_SMTP_PASSWORD"  # noqa: S105 - env var name, not a password
    with tempfile.TemporaryDirectory(prefix="productforge-smtp-") as directory:
        store = Store(Path(directory) / "smoke.db")
        channel = register_channel(
            store,
            kind="email",
            name="authorized-smtp-smoke",
            config={
                "host": os.environ["PRODUCT_FORGE_SMTP_HOST"],
                "port": int(os.environ["PRODUCT_FORGE_SMTP_PORT"]),
                "username": os.environ["PRODUCT_FORGE_SMTP_USERNAME"],
                "password_env": password_env,
                "from": os.environ["PRODUCT_FORGE_SMTP_FROM"],
                "to": os.environ["PRODUCT_FORGE_SMTP_TO"],
                "subject": "Product Forge SMTP homologation",
            },
        )
        channel["enabled"] = True
        receipt = deliver_alert(
            store, {"kind": "smtp_homologation", "synthetic": True}, channel, approved=True
        )
        result = receipt.get("delivery", {})
        print(
            json.dumps(
                {
                    "status": result.get("state"),
                    "attempts": result.get("attempts"),
                    "channel": "authorized-smtp-smoke",
                }
            )
        )
        return 0 if result.get("state") == "delivered" else 1


if __name__ == "__main__":
    raise SystemExit(main())
