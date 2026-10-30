"""Amazon Bedrock provider adapter for the PF LLM gateway.

The gateway invokes `gateway.provider_cmd` as a subprocess with a JSON
request on stdin and expects a JSON answer on stdout. This adapter maps
that request onto `bedrock-runtime: Converse`.

Auth model: **AWS SSO (IAM Identity Center)** — no static keys. The
operator runs `aws sso login --profile <name>` once per session; this
adapter resolves credentials through the standard boto3 credential chain
(`AWS_PROFILE` or `PF_BEDROCK_PROFILE`). It never sees, stores, or logs
credentials itself.

Config:
    PF_BEDROCK_PROFILE   AWS SSO profile name (falls back to AWS_PROFILE)
    PF_BEDROCK_REGION    region override (default: profile region or
                         us-east-1)
    PF_BEDROCK_MODEL     model id (default: anthropic.claude-sonnet-4-5)

Honesty: when boto3 or usable credentials are absent the adapter exits
with a named `unavailable:*` state — never a fabricated answer.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

DEFAULT_MODEL = "anthropic.claude-3-7-sonnet-20250219-v1:0"


def build_converse_request(req: dict[str, Any]) -> dict[str, Any]:
    """Pure mapping PF gateway request → Converse params (deterministic)."""
    messages = [
        {"role": m.get("role", "user"),
         "content": [{"text": str(m.get("content", ""))}]}
        for m in req.get("messages", [])
        if m.get("role") in {"user", "assistant"}
    ] or [{"role": "user", "content": [{"text": ""}]}]
    params: dict[str, Any] = {
        "modelId": os.environ.get("PF_BEDROCK_MODEL",
                                  req.get("model") or DEFAULT_MODEL),
        "messages": messages,
        "inferenceConfig": {"maxTokens": int(req.get("max_tokens", 2048))},
    }
    if sys_txt := req.get("system"):
        params["system"] = [{"text": str(sys_txt)}]
    return params


def _reply(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload))


def main() -> int:
    try:
        req = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        _reply({"error": {"code": "PF-PROVIDER",
                          "message": "invalid JSON request",
                          "state": "error"}})
        return 2
    try:
        import boto3  # noqa: PLC0415 — optional dependency by design
        from botocore.exceptions import (  # noqa: PLC0415
            ClientError,
            MissingDependencyException,
            NoCredentialsError,
            ProfileNotFound,
            SSOTokenLoadError,
        )
    except ModuleNotFoundError:
        _reply({"error": {"code": "PF-PROVIDER",
                          "message": "boto3 not installed — "
                                     "pip install 'boto3>=1.34'",
                          "state": "unavailable:dependency"}})
        return 3
    profile = os.environ.get("PF_BEDROCK_PROFILE") or \
        os.environ.get("AWS_PROFILE")
    try:
        session = (boto3.Session(profile_name=profile) if profile
                   else boto3.Session())
        client = session.client(
            "bedrock-runtime",
            region_name=os.environ.get("PF_BEDROCK_REGION") or
            session.region_name or "us-east-1")
        resp = client.converse(**build_converse_request(req))
    except MissingDependencyException as e:
        _reply({"error": {"code": "PF-PROVIDER",
                          "message": str(e)[:200],
                          "state": "unavailable:dependency"}})
        return 3
    except ProfileNotFound as e:
        _reply({"error": {"code": "PF-PROVIDER", "message": str(e)[:200],
                          "state": "unavailable:no-profile"}})
        return 4
    except (NoCredentialsError, SSOTokenLoadError) as e:
        _reply({"error": {
            "code": "PF-PROVIDER",
            "message": "SSO session missing/expired — run "
                       f"`aws sso login --profile {profile or 'default'}`",
            "detail": str(e)[:160],
            "state": "unverified:no-sso-session"}})
        return 5
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "ClientError")
        _reply({"error": {"code": "PF-PROVIDER", "message": code,
                          "detail": str(e)[:200],
                          "state": f"unavailable:{code}"}})
        return 6
    out = resp.get("output", {}).get("message", {})
    text = "".join(b.get("text", "") for b in out.get("content", []))
    _reply({"text": text, "model": resp.get("modelId"),
            "usage": resp.get("usage", {}),
            "stop_reason": resp.get("stopReason")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
