"""The API key sits in the request URL path and must never reach a log or an output.

These tests drive the real `requests` and `urllib3` stack against a throwaway
loopback HTTP server, so the HTTP libraries' own log records are exercised. The
key is an obviously fake value.
"""

from __future__ import annotations

import json
import logging
import re
import socket
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import requests
from test_tool_errors import dispatch

from bill4time_mcp import client as client_module
from bill4time_mcp import server
from bill4time_mcp.client import Bill4TimeClient, SafeToolFailure
from bill4time_mcp.setup import setup_wizard, verify

FAKE_KEY = "FAKE-SECRET-123"
README = Path(__file__).resolve().parents[1] / "README.md"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.server.paths.append(self.path)  # type: ignore[attr-defined]
        body = self.server.body  # type: ignore[attr-defined]
        self.send_response(self.server.status)  # type: ignore[attr-defined]
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        return


class Vendor:
    """A loopback stand-in for the Bill4Time API."""

    def __init__(self) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.httpd.paths = []  # type: ignore[attr-defined]
        self.httpd.status = 200  # type: ignore[attr-defined]
        self.httpd.body = b'[{"id": 1}]'  # type: ignore[attr-defined]
        self.thread = threading.Thread(
            target=lambda: self.httpd.serve_forever(poll_interval=0.01), daemon=True
        )
        self.thread.start()
        self.port = self.httpd.server_address[1]

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}/b4t-api"

    @property
    def paths(self) -> list[str]:
        return self.httpd.paths  # type: ignore[attr-defined]

    def respond(self, status: int, body: bytes) -> None:
        self.httpd.status = status  # type: ignore[attr-defined]
        self.httpd.body = body  # type: ignore[attr-defined]

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _no_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")


@pytest.fixture
def vendor(monkeypatch: pytest.MonkeyPatch):
    fake = Vendor()
    monkeypatch.setattr(client_module, "BASE", fake.base)
    monkeypatch.setattr(setup_wizard, "BASE", fake.base)
    monkeypatch.setattr(client_module, "API_KEY", FAKE_KEY)
    try:
        yield fake
    finally:
        fake.stop()


def _refused_base() -> str:
    """A loopback port that nothing listens on, so connecting is refused."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return f"http://127.0.0.1:{port}/b4t-api"


def _log_text(caplog: pytest.LogCaptureFixture) -> str:
    formatter = logging.Formatter("%(name)s %(levelname)s %(message)s")
    return "\n".join(formatter.format(record) for record in caplog.records)


def test_success_request_logging_does_not_expose_api_key(vendor, caplog):
    caplog.set_level(logging.DEBUG)
    client = Bill4TimeClient()

    result = client.list_users(top=1)

    assert result == [{"id": 1}]
    # The key really was in the request path, so its absence from the logs means something.
    assert any(FAKE_KEY in path for path in vendor.paths)
    assert FAKE_KEY not in _log_text(caplog)


def test_vendor_http_error_does_not_expose_api_key(vendor, caplog):
    caplog.set_level(logging.DEBUG)
    vendor.respond(500, b'{"code": "internal_server_error"}')
    client = Bill4TimeClient()

    with pytest.raises(SafeToolFailure) as raised:
        client.list_users(top=1)

    assert any(FAKE_KEY in path for path in vendor.paths)
    assert FAKE_KEY not in str(raised.value)
    assert FAKE_KEY not in _log_text(caplog)


def test_connection_error_does_not_expose_api_key(vendor, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(client_module, "BASE", _refused_base())
    client = Bill4TimeClient()

    with pytest.raises(SafeToolFailure) as raised:
        client.list_users(top=1)

    # requests puts the URL path, and so the key, in its own exception text,
    # so the safe error is raised without chaining that exception.
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__ is True
    assert FAKE_KEY not in str(raised.value)
    assert FAKE_KEY not in _log_text(caplog)
    assert FAKE_KEY not in "".join(traceback.format_exception(raised.value))


def test_tool_call_over_connection_error_does_not_expose_api_key(
    vendor, monkeypatch, caplog
):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(client_module, "BASE", _refused_base())
    monkeypatch.setattr(server, "_client", Bill4TimeClient())

    result = dispatch("list_clients")

    assert result["isError"] is True
    assert FAKE_KEY not in json.dumps(result)
    assert FAKE_KEY not in _log_text(caplog)


def test_unreadable_json_does_not_expose_api_key(vendor, caplog):
    caplog.set_level(logging.DEBUG)
    vendor.respond(200, b"not json at all")
    client = Bill4TimeClient()

    with pytest.raises(SafeToolFailure) as raised:
        client.list_users(top=1)

    assert FAKE_KEY not in str(raised.value)
    assert FAKE_KEY not in _log_text(caplog)


def test_urllib3_warnings_that_carry_the_url_are_silenced(caplog):
    # urllib3 connection.py logs "Failed to parse headers (url=...)" at WARNING with the
    # full request URL, which holds the key, so the logger must sit above WARNING.
    caplog.set_level(logging.DEBUG)
    logging.getLogger("urllib3.connection").warning(
        "Failed to parse headers (url=%s)", f"http://x/b4t-api/{FAKE_KEY}/v1/users"
    )
    assert FAKE_KEY not in _log_text(caplog)


def test_verify_command_does_not_expose_api_key(vendor, monkeypatch, capsys, caplog):
    caplog.set_level(logging.DEBUG)
    verify.main()
    monkeypatch.setattr(client_module, "BASE", _refused_base())
    with pytest.raises(SystemExit):
        verify.main()
    vendor.respond(500, b'{"code": "internal_server_error"}')
    monkeypatch.setattr(client_module, "BASE", vendor.base)
    with pytest.raises(SystemExit):
        verify.main()

    captured = capsys.readouterr()
    assert "Connected" in captured.out
    assert "Verification failed" in captured.out
    assert FAKE_KEY not in captured.out + captured.err
    assert FAKE_KEY not in _log_text(caplog)


def test_setup_wizard_key_test_does_not_expose_api_key(vendor, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    assert setup_wizard.test_api_key(FAKE_KEY) == [{"id": 1}]
    vendor.respond(500, b"{}")
    with pytest.raises(RuntimeError) as raised:
        setup_wizard.test_api_key(FAKE_KEY)
    monkeypatch.setattr(setup_wizard, "BASE", _refused_base())
    with pytest.raises(requests.ConnectionError):
        setup_wizard.test_api_key(FAKE_KEY)

    assert FAKE_KEY not in str(raised.value)
    assert FAKE_KEY not in _log_text(caplog)


def test_setup_wizard_failure_output_does_not_expose_api_key(
    vendor, monkeypatch, capsys, caplog
):
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(setup_wizard, "getpass", lambda _prompt: FAKE_KEY)
    monkeypatch.setattr(setup_wizard, "BASE", _refused_base())

    with pytest.raises(SystemExit):
        setup_wizard.main()

    captured = capsys.readouterr()
    assert "verification failed" in captured.out
    assert FAKE_KEY not in captured.out + captured.err
    assert FAKE_KEY not in _log_text(caplog)


def _readme_desktop_config() -> str:
    text = README.read_text(encoding="utf-8")
    section = text.split("## Usage with Claude Desktop", 1)[1]
    match = re.search(r"```json\n(.*?)\n```", section, re.DOTALL)
    assert match, "README has no JSON block under Usage with Claude Desktop"
    return match.group(1)


def test_setup_wizard_prints_the_readme_claude_desktop_config(
    vendor, monkeypatch, capsys
):
    monkeypatch.setattr(setup_wizard, "getpass", lambda _prompt: FAKE_KEY)
    monkeypatch.setattr(setup_wizard.credentials, "set_secret", lambda *_a: "keyring")
    monkeypatch.setattr(setup_wizard.credentials, "storage_backend", lambda: "test")

    setup_wizard.main()

    out = capsys.readouterr().out
    expected = _readme_desktop_config()
    assert expected in out
    assert json.loads(expected)["mcpServers"]["bill4time"]["command"] == "uv"
    assert '"command": "bill4time-mcp"' not in out
    assert FAKE_KEY not in out
