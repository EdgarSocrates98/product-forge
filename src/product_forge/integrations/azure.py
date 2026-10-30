"""Azure intelligence — KQL (Log Analytics) + Fabric/Power BI inventory.

Same honesty contract: missing SDK/credentials → typed unavailable.
"""

from __future__ import annotations

from typing import Any

from ..errors import SourceUnavailableError


def _credential() -> Any:
    try:
        from azure.identity import DefaultAzureCredential  # type: ignore
    except ImportError as e:
        raise SourceUnavailableError(
            "azure-identity not installed — pip install product-forge[azure]") from e
    cred = DefaultAzureCredential()
    try:
        cred.get_token("https://api.loganalytics.io/.default")
    except Exception as e:
        raise SourceUnavailableError(f"azure credentials unavailable: {e}") from e
    return cred


class KQLConnector:
    """Log Analytics KQL execution via azure-monitor-query."""

    def __init__(self, workspace_id: str) -> None:
        self.workspace_id = workspace_id

    def _client(self) -> Any:
        try:
            from azure.monitor.query import LogsQueryClient  # type: ignore
        except ImportError as e:
            raise SourceUnavailableError(
                "azure-monitor-query not installed — pip install product-forge[azure]") from e
        return LogsQueryClient(_credential())

    def verify(self) -> dict[str, Any]:
        self._client()
        return {"status": "healthy", "engine": "kql", "workspace_id": self.workspace_id[:8] + "…"}

    def execute(self, kql: str, *, timespan_hours: int = 24, row_limit: int = 1000,
                timeout_s: float = 60.0, cancel: Any = None) -> dict[str, Any]:
        import datetime as dt

        client = self._client()
        try:
            res = client.query_workspace(
                self.workspace_id, kql,
                timespan=dt.timedelta(hours=timespan_hours))
        except Exception as e:
            return {"status": "failed", "error": str(e)[:200]}
        tables = []
        for t in getattr(res, "tables", []):
            cols = [c.name if hasattr(c, "name") else str(c) for c in t.columns]
            tables.append({"columns": cols, "rows": [list(r) for r in t.rows[:row_limit]]})
        return {"status": "completed", "tables": tables,
                "truncated": any(len(t.rows) > row_limit for t in getattr(res, "tables", []))}


def powerbi_inventory(token: str | None = None) -> dict[str, Any]:
    """Power BI REST inventory — workspaces + datasets. Token required."""
    if not token:
        raise SourceUnavailableError("powerbi inventory requires a bearer token")
    import json
    import urllib.request

    req = urllib.request.Request(
        "https://api.powerbi.com/v1.0/myorg/groups",
        headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 — fixed MS URL
            groups = json.loads(r.read()).get("value", [])
    except Exception as e:
        raise SourceUnavailableError(f"powerbi inventory failed: {e}") from e
    return {"engine": "powerbi",
            "workspaces": [{"id": g["id"], "name": g["name"]} for g in groups]}


def fabric_inventory(workspace_id: str, token: str | None = None) -> dict[str, Any]:
    """Microsoft Fabric items inventory — token required."""
    if not token:
        raise SourceUnavailableError("fabric inventory requires a bearer token")
    import json
    import urllib.request

    req = urllib.request.Request(
        f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items",
        headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 — fixed MS URL
            items = json.loads(r.read()).get("value", [])
    except Exception as e:
        raise SourceUnavailableError(f"fabric inventory failed: {e}") from e
    return {"engine": "fabric",
            "items": [{"id": i["id"], "name": i["displayName"], "type": i["type"]}
                      for i in items]}
