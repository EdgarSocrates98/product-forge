from email.message import Message

import pytest

from product_forge.knowledge.url import (
    UrlCaptureError,
    _PinnedHTTPConnection,
    fetch_url_document,
    validate_url,
)


def _public_resolver(host, *_args, **_kwargs):
    return [(None, None, None, None, ("93.184.216.34", 0))]


class _Response:
    def __init__(self, body: bytes, content_type: str = "text/html"):
        self._body = body
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def read(self, size=-1):
        return self._body if size < 0 else self._body[:size]


class _Opener:
    def __init__(self, response):
        self.response = response

    def open(self, _request, timeout):
        assert timeout > 0
        return self.response


@pytest.mark.parametrize(
    "value",
    [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://user:pass@example.com/docs",
        "http://127.0.0.1/docs",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.2/docs",
        "https://example.com:8443/docs",
    ],
)
def test_validate_url_refuses_unsafe_targets(value):
    with pytest.raises(UrlCaptureError):
        validate_url(value, resolver=_public_resolver)


def test_validate_url_refuses_dns_that_contains_private_address():
    def mixed_resolver(*_args, **_kwargs):
        return [
            (None, None, None, None, ("93.184.216.34", 0)),
            (None, None, None, None, ("10.0.0.4", 0)),
        ]

    with pytest.raises(UrlCaptureError, match="non-public"):
        validate_url("https://example.com/docs", resolver=mixed_resolver)


def test_html_capture_preserves_title_headings_code_links_and_table_text():
    body = b"""<html><head><title>Runbook</title></head><body>
    <h1>Diagnose Spark</h1><p>Read <a href='https://example.com/ref'>the guide</a>.</p>
    <pre>spark.sql(\"select 1\")</pre><table><tr><th>Key</th><th>Value</th></tr>
    <tr><td>mode</td><td>safe</td></tr></table><script>bad()</script>
    </body></html>"""
    result = fetch_url_document(
        "https://example.com/runbook", resolver=_public_resolver, opener=_Opener(_Response(body))
    )

    assert result["title"] == "Runbook"
    assert "Diagnose Spark" in result["content"]
    assert 'spark.sql("select 1")' in result["content"]
    assert "the guide (https://example.com/ref)" in result["content"]
    assert "Key | Value" in result["content"]
    assert "bad()" not in result["content"]
    assert result["extractor"] == "stdlib-html"
    assert result["provenance"]["redirects_followed"] == 0


def test_capture_refuses_unsupported_content_and_oversized_body():
    with pytest.raises(UrlCaptureError, match="content type"):
        fetch_url_document(
            "https://example.com/file",
            resolver=_public_resolver,
            opener=_Opener(_Response(b"binary", "application/octet-stream")),
        )
    with pytest.raises(UrlCaptureError, match="size limit"):
        fetch_url_document(
            "https://example.com/file",
            resolver=_public_resolver,
            max_bytes=4,
            opener=_Opener(_Response(b"12345", "text/plain")),
        )


def test_plain_text_capture_is_deterministic_and_has_metrics():
    result = fetch_url_document(
        "https://example.com/plain",
        resolver=_public_resolver,
        opener=_Opener(_Response(b"  first\nsecond  ", "text/plain")),
    )

    assert result["content"] == "first\nsecond"
    assert result["metrics"]["bytes_read"] == len(b"  first\nsecond  ")
    assert len(result["content_hash"]) == 64


def test_defuddle_is_explicit_optional_extractor(monkeypatch):
    monkeypatch.setattr(
        "product_forge.knowledge.url.parse_defuddle",
        lambda _html, url: {
            "title": "Defuddled",
            "content": "# cleaned",
            "extractor": "defuddle-cli",
            "url": url,
        },
    )
    result = fetch_url_document(
        "https://example.com/article",
        extractor="defuddle",
        resolver=_public_resolver,
        opener=_Opener(_Response(b"<article>raw</article>")),
    )
    assert result["title"] == "Defuddled"
    assert result["extractor"] == "defuddle-cli"
    assert "optional Defuddle" in result["warnings"][1]


def test_url_capture_rejects_unknown_extractor():
    with pytest.raises(UrlCaptureError, match="extractor must be stdlib or defuddle"):
        fetch_url_document(
            "https://example.com/article",
            extractor="other",
            resolver=_public_resolver,
            opener=_Opener(_Response(b"<p>safe</p>")),
        )


def test_pinned_connection_uses_validated_ip(monkeypatch):
    calls = {}

    def fake_connect(address, timeout, source_address=None):
        calls["address"] = address
        calls["timeout"] = timeout
        calls["source_address"] = source_address
        return object()

    monkeypatch.setattr("product_forge.knowledge.url.socket.create_connection", fake_connect)
    connection = _PinnedHTTPConnection("example.com", resolved_ip="93.184.216.34")
    connection.connect()
    assert calls["address"] == ("93.184.216.34", 80)
