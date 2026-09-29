"""Exercise actual client failure paths through the MCP wire handler, offline."""

import asyncio
import logging

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from test_list_contracts import StubResponse, _client_with_stub_session
from test_spec_2026_07_28 import _post_modern, _result

from bill4time_mcp import client as client_module
from bill4time_mcp import server
from bill4time_mcp.client import SafeToolFailure

PRIVATE = "Private Person person@example.invalid https://vendor.invalid/key/private"


class ErrorResponse(StubResponse):
    def __init__(self, status, payload, retry=None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self.payload = payload
        self.text = PRIVATE
        self.headers = {} if retry is None else {"Retry-After": retry}

    def json(self):
        return self.payload


def dispatch(name="list_clients", arguments=None):
    return _result(
        asyncio.run(
            _post_modern("tools/call", {"name": name, "arguments": arguments or {}})
        )
    )


@pytest.mark.parametrize(
    ("status", "payload", "retry", "message"),
    [
        (
            401,
            {"message": PRIVATE},
            None,
            "Bill4Time authorization was rejected or expired. Reauthorize with bill4time-mcp-setup.",
        ),
        (
            403,
            {"message": PRIVATE},
            None,
            "Bill4Time authorization was rejected or expired. Reauthorize with bill4time-mcp-setup.",
        ),
        (
            404,
            {"message": PRIVATE},
            None,
            "Bill4Time resource was not found. Check the requested record.",
        ),
        (
            500,
            {"code": "service_unavailable", "message": PRIVATE},
            None,
            "Bill4Time returned HTTP 500: service temporarily unavailable",
        ),
        (400, {"code": PRIVATE}, None, "Bill4Time returned HTTP 400: request failed"),
        (
            429,
            {"message": PRIVATE},
            "300",
            "Bill4Time rate limit reached. Retry after about 300 seconds.",
        ),
        (
            429,
            {"message": PRIVATE},
            PRIVATE,
            "Bill4Time rate limit reached. Retry later.",
        ),
        (429, {}, "-3", "Bill4Time rate limit reached. Retry later."),
    ],
)
def test_real_client_failures_are_safe_mcp_errors(
    monkeypatch, caplog, status, payload, retry, message
):
    client, session = _client_with_stub_session()
    response = ErrorResponse(status, payload, retry)
    monkeypatch.setattr(session, "get", lambda *args, **kwargs: response)
    monkeypatch.setattr(server, "_client", client)
    with caplog.at_level(logging.INFO):
        result = dispatch()
    assert result["isError"] is True
    assert (
        result["content"][0]["text"] == f"Error executing tool list_clients: {message}"
    )
    assert PRIVATE not in str(result) + caplog.text
    assert issubclass(SafeToolFailure, ToolError)


def test_missing_configuration_uses_actual_constructor(monkeypatch):
    monkeypatch.setattr(client_module, "API_KEY", "")
    monkeypatch.setattr(server, "_client", None)
    result = dispatch()
    assert result["isError"] is True
    assert (
        result["content"][0]["text"]
        == "Error executing tool list_clients: Missing BILL4TIME_API_KEY. Set it or run bill4time-mcp-setup."
    )


@pytest.mark.parametrize("argument", ["start_date", "end_date"])
def test_actual_date_validation_identifies_the_argument(monkeypatch, argument):
    client, session = _client_with_stub_session()
    monkeypatch.setattr(server, "_client", client)
    arguments = {
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
        argument: PRIVATE,
    }
    result = dispatch("list_time_entries_for_date_range", arguments)
    assert result["isError"] is True
    assert (
        result["content"][0]["text"]
        == f"Error executing tool list_time_entries_for_date_range: Argument {argument} must use YYYY-MM-DD format."
    )
    assert session.calls == []


def test_unexpected_outer_failure_stays_masked(monkeypatch, caplog):
    class BrokenClient:
        def list_clients(self, *args):
            raise RuntimeError(PRIVATE) from SafeToolFailure("known inner failure")

    monkeypatch.setattr(server, "_client", BrokenClient())
    with caplog.at_level(logging.ERROR):
        result = dispatch()
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Error executing tool list_clients"
    assert PRIVATE not in caplog.text
    assert "known inner failure" not in caplog.text
    assert "reason=unexpected_exception" in caplog.text
