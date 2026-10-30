"""AWS intelligence — real boto3 connectors; honest unavailability.

Every operation degrades to a typed `unverified`/`error` result when the
SDK or credentials are absent — never fabricated responses. Locator for
athena = "s3://output-bucket/prefix"; database via metadata.database.
"""

from __future__ import annotations

import time
from typing import Any

from ..errors import SourceUnavailableError


def _boto3():
    try:
        import boto3  # type: ignore

        return boto3
    except ImportError as e:
        raise SourceUnavailableError(
            "boto3 not installed — pip install product-forge[aws]") from e


def _session_ok(boto3: Any) -> None:
    try:
        boto3.Session().client("sts").get_caller_identity()
    except Exception as e:
        raise SourceUnavailableError(f"aws credentials unavailable: {e}") from e


class AthenaConnector:
    """Real Athena query execution: start → poll → fetch results."""

    def __init__(self, workgroup: str = "primary", database: str = "default",
                 output: str = "", region: str | None = None) -> None:
        self.workgroup, self.database, self.output = workgroup, database, output
        self.region = region

    def _client(self) -> Any:
        b = _boto3()
        _session_ok(b)
        return b.client("athena", region_name=self.region)

    def verify(self) -> dict[str, Any]:
        c = self._client()
        try:
            c.get_work_group(WorkGroup=self.workgroup)
            return {"status": "healthy", "engine": "athena", "workgroup": self.workgroup}
        except Exception as e:
            raise SourceUnavailableError(f"athena workgroup check failed: {e}") from e

    def execute(self, sql: str, *, row_limit: int = 1000, timeout_s: float = 60.0,
                cancel: Any = None) -> dict[str, Any]:
        c = self._client()
        params: dict[str, Any] = {"QueryString": sql,
                                  "WorkGroup": self.workgroup,
                                  "QueryExecutionContext": {"Database": self.database}}
        if self.output:
            params["ResultConfiguration"] = {"OutputLocation": self.output}
        qid = c.start_query_execution(**params)["QueryExecutionId"]
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if cancel is not None and cancel.is_set():
                c.stop_query_execution(QueryExecutionId=qid)
                return {"status": "cancelled", "query_execution_id": qid}
            st = c.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
            state = st["State"]
            if state == "SUCCEEDED":
                break
            if state in {"FAILED", "CANCELLED"}:
                return {"status": "failed", "reason": st.get("StateChangeReason", state),
                        "query_execution_id": qid}
            time.sleep(0.5)
        else:
            c.stop_query_execution(QueryExecutionId=qid)
            return {"status": "timeout", "query_execution_id": qid}
        rows, cols, truncated = [], [], False
        paginator = c.get_paginator("get_query_results")
        for page in paginator.paginate(QueryExecutionId=qid):
            for r in page["ResultSet"]["Rows"]:
                vals = [d.get("VarCharValue") for d in r["Data"]]
                if not cols:
                    cols = vals
                    continue
                if len(rows) >= row_limit:
                    truncated = True
                    break
                rows.append(vals)
            if truncated:
                break
        return {"status": "completed", "columns": cols, "rows": rows,
                "truncated": truncated, "query_execution_id": qid}


def glue_catalog(database: str | None = None, region: str | None = None) -> dict[str, Any]:
    """Glue Data Catalog inventory — real list of databases/tables."""
    b = _boto3()
    _session_ok(b)
    c = b.client("glue", region_name=region)
    out: dict[str, Any] = {"engine": "glue", "databases": []}
    dbs = c.get_databases().get("DatabaseList", [])
    for d in dbs:
        if database and d["Name"] != database:
            continue
        tables = c.get_tables(DatabaseName=d["Name"]).get("TableList", [])
        out["databases"].append({"name": d["Name"],
                                 "tables": [{"name": t["Name"],
                                             "columns": [col["Name"] for col in
                                                         t.get("StorageDescriptor", {})
                                                         .get("Columns", [])]}
                                            for t in tables]})
    return out


def quicksight_inventory(account_id: str, region: str | None = None) -> dict[str, Any]:
    """QuickSight dashboards/datasets inventory (read-only)."""
    b = _boto3()
    _session_ok(b)
    c = b.client("quicksight", region_name=region)
    try:
        dashboards = c.list_dashboards(AwsAccountId=account_id).get("DashboardSummaryList", [])
        datasets = c.list_data_sets(AwsAccountId=account_id).get("DataSetSummaries", [])
    except Exception as e:
        raise SourceUnavailableError(f"quicksight inventory failed: {e}") from e
    return {"engine": "quicksight",
            "dashboards": [{"id": d["DashboardId"], "name": d["Name"]} for d in dashboards],
            "datasets": [{"id": d["DataSetId"], "name": d["Name"]} for d in datasets]}


def cost_summary(days: int = 30, region: str | None = None) -> dict[str, Any]:
    """Cost Explorer grouped usage — real spend, honest errors."""
    b = _boto3()
    _session_ok(b)
    c = b.client("ce", region_name=region)
    import datetime as dt

    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    try:
        res = c.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="MONTHLY", Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}])
    except Exception as e:
        raise SourceUnavailableError(f"cost explorer failed: {e}") from e
    services = []
    for r in res.get("ResultsByTime", []):
        for g in r.get("Groups", []):
            services.append({"service": g["Keys"][0],
                             "amount": float(g["Metrics"]["UnblendedCost"]["Amount"]),
                             "unit": g["Metrics"]["UnblendedCost"]["Unit"]})
    services.sort(key=lambda x: x["amount"], reverse=True)
    return {"engine": "cost-explorer", "period_days": days, "services": services[:25]}
