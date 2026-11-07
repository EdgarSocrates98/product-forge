"""Safe, bounded URL document capture for Product Forge.

The adapter is deliberately stdlib-only.  It does not execute page scripts or
depend on a Node runtime: remote content is treated as untrusted text, fetched
once without redirects, normalized deterministically, and returned with
provenance and extraction metrics.
"""

from __future__ import annotations

import hashlib
import html
import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any

from .defuddle import DefuddleError, parse_defuddle

MAX_URL_BYTES = 1 * 1024 * 1024
DEFAULT_TIMEOUT_S = 10.0
ALLOWED_CONTENT_TYPES = {
    "text/html",
    "text/plain",
    "application/xhtml+xml",
    "application/json",
    "application/xml",
    "text/xml",
}


class UrlCaptureError(ValueError):
    """Stable, safe-to-display URL capture failure."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _public_ip(value: str) -> bool:
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError:
        return False
    # is_global excludes loopback, RFC1918, link-local, multicast, reserved,
    # unspecified and the cloud metadata address (169.254.169.254).
    return parsed.is_global and not parsed.is_private


def _resolve_public(host: str, resolver: Callable[..., Any] = socket.getaddrinfo) -> list[str]:
    try:
        addresses = resolver(host, None, type=socket.SOCK_STREAM)
    except (OSError, socket.gaierror) as exc:
        raise UrlCaptureError("URL-DNS-FAILED", "the URL host could not be resolved") from exc
    values = sorted({str(item[4][0]) for item in addresses if item and item[4]})
    if not values or any(not _public_ip(address) for address in values):
        raise UrlCaptureError("URL-SSRF-BLOCKED", "the URL host resolves to a non-public address")
    return values


def validate_url(raw_url: str, *, resolver: Callable[..., Any] = socket.getaddrinfo) -> str:
    """Validate URL syntax and resolve every address before a network request."""
    value = str(raw_url or "").strip()
    try:
        parsed = urllib.parse.urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise UrlCaptureError("URL-INVALID", "the URL port is invalid") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise UrlCaptureError("URL-INVALID", "only absolute http(s) URLs are supported")
    if parsed.username or parsed.password:
        raise UrlCaptureError("URL-CREDENTIALS-REFUSED", "URL credentials are not allowed")
    if port not in (None, 80, 443):
        raise UrlCaptureError("URL-PORT-REFUSED", "only ports 80 and 443 are allowed")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".localhost")):
        raise UrlCaptureError("URL-SSRF-BLOCKED", "local hostnames are not allowed")
    if _public_ip(host):
        addresses = [host]
    elif _looks_like_ip(host):
        raise UrlCaptureError("URL-SSRF-BLOCKED", "the URL host is not public")
    else:
        addresses = _resolve_public(host, resolver)
    if any(not _public_ip(address) for address in addresses):
        raise UrlCaptureError("URL-SSRF-BLOCKED", "the URL host is not public")
    return urllib.parse.urlunsplit(
        (parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, "")
    )


def _looks_like_ip(host: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F:.]+", host))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        raise UrlCaptureError("URL-REDIRECT-REFUSED", "redirects are not followed for URL capture")


class _PageParser(HTMLParser):
    """Small deterministic HTML-to-text extractor with code/link/table fidelity."""

    _ignored = {"script", "style", "noscript", "template", "svg"}
    _block = {
        "address",
        "article",
        "aside",
        "blockquote",
        "div",
        "dl",
        "dt",
        "dd",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "main",
        "p",
        "pre",
        "section",
        "table",
        "tr",
        "ul",
        "ol",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.parts: list[str] = []
        self.stack: list[str] = []
        self.href: str | None = None
        self.title_parts: list[str] = []
        self.in_title = False
        self.in_ignored = 0
        self.in_pre = 0

    def _flush(self) -> None:
        text = "".join(self.parts).strip()
        if text:
            self.lines.append(text)
        self.parts.clear()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self.stack.append(tag)
        if tag in self._ignored:
            self.in_ignored += 1
        if tag == "title":
            self.in_title = True
        if tag == "pre":
            self._flush()
            self.in_pre += 1
        elif tag in self._block and not self.in_pre:
            self._flush()
        if tag == "a":
            self.href = next((value for key, value in attrs if key.lower() == "href" and value), None)
        if tag in {"th", "td"} and self.parts:
            self.parts.append(" | ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "a" and self.href:
            self.parts.append(f" ({html.unescape(self.href)})")
            self.href = None
        if tag == "title":
            self.in_title = False
        if tag == "pre":
            self._flush()
            self.in_pre = max(0, self.in_pre - 1)
        elif tag in self._block and not self.in_pre:
            self._flush()
        if tag in self._ignored:
            self.in_ignored = max(0, self.in_ignored - 1)
        if self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        if self.in_ignored:
            return
        if self.in_title:
            self.title_parts.append(data)
        if self.in_pre:
            self.parts.append(data)
        else:
            self.parts.append(re.sub(r"\s+", " ", data))

    def finish(self) -> tuple[str, str]:
        self._flush()
        content = "\n\n".join(line for line in self.lines if line).strip()
        title = re.sub(r"\s+", " ", "".join(self.title_parts)).strip()
        return title[:160], content


def _extract(content: str, content_type: str) -> tuple[str, str, str]:
    if content_type in {"text/html", "application/xhtml+xml"}:
        parser = _PageParser()
        try:
            parser.feed(content)
            title, text = parser.finish()
            return title, text or re.sub(r"\s+", " ", content).strip(), "stdlib-html"
        except (ValueError, AssertionError):
            return "", re.sub(r"\s+", " ", content).strip(), "stdlib-text-fallback"
    return "", content.strip(), "stdlib-text"


def fetch_url_document(
    raw_url: str,
    *,
    extractor: str = "stdlib",
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_bytes: int = MAX_URL_BYTES,
    resolver: Callable[..., Any] = socket.getaddrinfo,
    opener: Any | None = None,
) -> dict[str, Any]:
    """Fetch one public URL, without redirecting or executing remote code."""
    if extractor not in {"stdlib", "defuddle"}:
        raise UrlCaptureError("URL-EXTRACTOR-INVALID", "extractor must be stdlib or defuddle")
    url = validate_url(raw_url, resolver=resolver)
    request = urllib.request.Request(  # noqa: S310 - scheme and host validated above
        url,
        headers={"Accept": "text/html, text/plain, application/xhtml+xml, application/json"},
    )
    client = opener or urllib.request.build_opener(_NoRedirect())
    try:
        response = client.open(request, timeout=timeout_s)
        header_size = int(response.headers.get("Content-Length", "0") or 0)
        if header_size > max_bytes:
            raise UrlCaptureError("URL-SIZE-LIMIT", "the remote document exceeds the safe size limit")
        payload = response.read(max_bytes + 1)
    except UrlCaptureError:
        raise
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            raise UrlCaptureError(
                "URL-REDIRECT-REFUSED", "redirects are not followed for URL capture"
            ) from exc
        raise UrlCaptureError("URL-FETCH-FAILED", "the remote document could not be fetched") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UrlCaptureError("URL-FETCH-FAILED", "the remote document could not be fetched") from exc
    if len(payload) > max_bytes:
        raise UrlCaptureError("URL-SIZE-LIMIT", "the remote document exceeds the safe size limit")
    content_type = str(response.headers.get_content_type() or "").lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise UrlCaptureError(
            "URL-CONTENT-TYPE-REFUSED", "the remote content type is not a supported document"
        )
    charset = response.headers.get_content_charset() or "utf-8"
    text = payload.decode(charset, errors="replace")
    if extractor == "defuddle":
        try:
            parsed = parse_defuddle(text, url)
        except DefuddleError as exc:
            raise UrlCaptureError(exc.code, str(exc), details=exc.details) from exc
        title = str(parsed["title"])
        normalized = str(parsed["content"])
        extractor_name = str(parsed["extractor"])
    else:
        title, normalized, extractor_name = _extract(text, content_type)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return {
        "schema": "productforge/UrlDocument/v1",
        "url": url,
        "title": title or urllib.parse.urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1] or url,
        "content": normalized,
        "content_hash": digest,
        "size": len(payload),
        "content_type": content_type,
        "extractor": extractor_name,
        "state": "ready_for_import",
        "warnings": [
            "remote content is untrusted and was not executed",
            *(["optional Defuddle extraction was selected"] if extractor == "defuddle" else []),
        ],
        "metrics": {"bytes_read": len(payload), "characters": len(normalized), "max_bytes": max_bytes},
        "provenance": {"requested_url": url, "final_url": url, "fetched_at": _now(), "redirects_followed": 0},
    }
