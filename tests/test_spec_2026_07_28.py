"""Offline raw-wire regressions for the MCP 2026-07-28 migration."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx2
import pytest
from mcp import Client
from mcp.types import LATEST_PROTOCOL_VERSION
from mcp_types.version import MODERN_PROTOCOL_VERSIONS

from bill4time_mcp import server

PROTOCOL_VERSION = "2026-07-28"
LEGACY_PROTOCOL_VERSION = "2025-11-25"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _modern_request(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    protocol_version: str = PROTOCOL_VERSION,
    request_id: int = 1,
) -> tuple[dict[str, str], dict[str, Any]]:
    request_params = dict(params or {})
    request_params["_meta"] = {
        PROTOCOL_VERSION_META_KEY: protocol_version,
        CLIENT_CAPABILITIES_META_KEY: {},
        CLIENT_INFO_META_KEY: {"name": "bill4time-spec-test", "version": "0"},
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "mcp-protocol-version": protocol_version,
        "mcp-method": method,
    }
    if method in {"tools/call", "prompts/get"}:
        headers["mcp-name"] = str(request_params["name"])
    elif method == "resources/read":
        headers["mcp-name"] = str(request_params["uri"])
    return headers, {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": request_params,
    }


async def _post_modern(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    protocol_version: str = PROTOCOL_VERSION,
    header_overrides: dict[str, str] | None = None,
    omit_headers: tuple[str, ...] = (),
) -> httpx2.Response:
    app = server.mcp.streamable_http_app(
        host="0.0.0.0",
        stateless_http=True,
        json_response=True,
    )
    headers, body = _modern_request(
        method,
        params,
        protocol_version=protocol_version,
    )
    for header in omit_headers:
        headers.pop(header, None)
    if header_overrides:
        headers.update(header_overrides)

    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(
            transport=transport,
            base_url="http://spec-test",
        ) as client:
            return await client.post("/mcp", headers=headers, json=body)


def _result(response: httpx2.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    return payload["result"]


def test_spec_check_pins_the_2026_revision() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tests" / "spec_check.py"), "--mcp-only"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Spec check: PASS" in result.stdout
    assert LATEST_PROTOCOL_VERSION == PROTOCOL_VERSION
    assert MODERN_PROTOCOL_VERSIONS == (PROTOCOL_VERSION,)


def test_modern_discovery_is_sessionless_and_matches_server_capabilities() -> None:
    response = asyncio.run(_post_modern("server/discover"))
    result = _result(response)

    assert "mcp-session-id" not in response.headers
    assert result["supportedVersions"] == [PROTOCOL_VERSION]
    assert result["resultType"] == "complete"
    assert result["ttlMs"] == 0
    assert result["cacheScope"] == "private"
    assert result["capabilities"] == {
        "prompts": {"listChanged": True},
        "resources": {"listChanged": True, "subscribe": True},
        "tools": {"listChanged": True},
    }
    assert "extensions" not in result["capabilities"]
    assert result["_meta"][SERVER_INFO_META_KEY] == {
        "name": "bill4time",
        "version": "0.2.0",
    }


def test_client_negotiates_modern_and_retains_legacy_compatibility() -> None:
    async def negotiate() -> tuple[str, str]:
        async with Client(server.mcp, cache=None) as modern:
            modern_version = modern.protocol_version
        async with Client(server.mcp, mode="legacy", cache=None) as legacy:
            legacy_version = legacy.protocol_version
        return modern_version, legacy_version

    modern_version, legacy_version = asyncio.run(negotiate())
    assert modern_version == PROTOCOL_VERSION
    assert legacy_version == LEGACY_PROTOCOL_VERSION


def test_cacheable_list_results_are_complete_private_and_deterministic() -> None:
    async def list_results() -> list[dict[str, Any]]:
        methods = (
            "tools/list",
            "tools/list",
            "prompts/list",
            "resources/list",
            "resources/templates/list",
        )
        return [_result(await _post_modern(method)) for method in methods]

    first_tools, second_tools, prompts, resources, templates = asyncio.run(
        list_results()
    )
    for result in (first_tools, second_tools, prompts, resources, templates):
        assert result["resultType"] == "complete"
        assert result["ttlMs"] == 0
        assert result["cacheScope"] == "private"

    first_names = [tool["name"] for tool in first_tools["tools"]]
    second_names = [tool["name"] for tool in second_tools["tools"]]
    assert first_names == second_names
    assert len(first_names) == 59
    assert all(tool["inputSchema"]["type"] == "object" for tool in first_tools["tools"])
    assert len(prompts["prompts"]) == 3
    assert [item["uri"] for item in resources["resources"]] == [
        "bill4time://active_clients",
        "bill4time://users",
        "bill4time://security-notes",
    ]
    assert templates["resourceTemplates"] == []


def test_resource_and_tool_results_are_complete_with_revised_resource_error(
    monkeypatch,
) -> None:
    class StubBill4TimeClient:
        def list_clients_by_status(self, *_args) -> list[dict[str, Any]]:
            return [{"id": 1, "status": "Active"}]

        def list_users(self, *_args) -> list[dict[str, Any]]:
            return [{"id": 2}]

    monkeypatch.setattr(server, "_client", StubBill4TimeClient())

    found = asyncio.run(
        _post_modern("resources/read", {"uri": "bill4time://active_clients"})
    )
    result = _result(found)
    assert result["resultType"] == "complete"
    assert result["ttlMs"] == 0
    assert result["cacheScope"] == "private"
    assert '"status": "Active"' in result["contents"][0]["text"]

    tool_response = asyncio.run(
        _post_modern("tools/call", {"name": "list_users", "arguments": {}})
    )
    tool_result = _result(tool_response)
    assert tool_result["resultType"] == "complete"
    assert tool_result["isError"] is False
    assert tool_result["structuredContent"] == {"result": '[\n  {\n    "id": 2\n  }\n]'}

    missing = asyncio.run(
        _post_modern("resources/read", {"uri": "bill4time://does-not-exist"})
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == -32602


def test_modern_http_requires_routing_headers_and_uses_revised_errors() -> None:
    missing_protocol = asyncio.run(
        _post_modern("server/discover", omit_headers=("mcp-protocol-version",))
    )
    assert missing_protocol.status_code == 200
    assert missing_protocol.json()["error"]["code"] == -32601

    missing_method = asyncio.run(
        _post_modern("tools/list", omit_headers=("mcp-method",))
    )
    assert missing_method.status_code == 400
    assert missing_method.json()["error"]["code"] == -32020

    missing_name = asyncio.run(
        _post_modern(
            "tools/call",
            {"name": "list_users", "arguments": {}},
            omit_headers=("mcp-name",),
        )
    )
    assert missing_name.status_code == 400
    assert missing_name.json()["error"]["code"] == -32020

    mismatch = asyncio.run(
        _post_modern(
            "tools/list",
            header_overrides={"mcp-method": "resources/list"},
        )
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["error"]["code"] == -32020

    unsupported = asyncio.run(_post_modern("tools/list", protocol_version="2099-01-01"))
    assert unsupported.status_code == 400
    assert unsupported.json()["error"] == {
        "code": -32022,
        "message": "Unsupported protocol version",
        "data": {
            "supported": [PROTOCOL_VERSION],
            "requested": "2099-01-01",
        },
    }

    unknown = asyncio.run(_post_modern("example/unknown"))
    assert unknown.status_code == 404
    assert unknown.json()["error"] == {
        "code": -32601,
        "message": "Method not found",
        "data": "example/unknown",
    }


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (
            "missing",
            "Error executing tool list_clients: Missing BILL4TIME_API_KEY. Set it or run bill4time-mcp-setup.",
        ),
        (
            "auth",
            "Error executing tool list_clients: Bill4Time authorization was rejected or expired. Reauthorize with bill4time-mcp-setup.",
        ),
        (
            "http",
            "Error executing tool list_clients: Bill4Time returned HTTP 500: request failed",
        ),
        (
            "rate",
            "Error executing tool list_clients: Bill4Time rate limit reached. Retry after about 7 seconds.",
        ),
        (
            "invalid",
            "Error executing tool list_clients: Argument top must be an integer from 1 to 200.",
        ),
        (
            "not_found",
            "Error executing tool get_client: Bill4Time resource was not found. Check the requested record.",
        ),
    ],
)
def test_known_failures_are_actionable_tool_results(
    monkeypatch, failure, expected
) -> None:
    from bill4time_mcp.client import SafeToolFailure

    class FakeClient:
        def list_clients(self, *_args):
            raise SafeToolFailure(
                {
                    "missing": "Missing BILL4TIME_API_KEY. Set it or run bill4time-mcp-setup.",
                    "auth": "Bill4Time authorization was rejected or expired. Reauthorize with bill4time-mcp-setup.",
                    "http": "Bill4Time returned HTTP 500: request failed",
                    "rate": "Bill4Time rate limit reached. Retry after about 7 seconds.",
                }[failure]
            )

        def get_client(self, *_args):
            raise SafeToolFailure(
                "Bill4Time resource was not found. Check the requested record."
            )

    monkeypatch.setattr(server, "_client", FakeClient())
    name = "get_client" if failure == "not_found" else "list_clients"
    arguments = (
        {"client_id": 987654}
        if name == "get_client"
        else {"top": 999}
        if failure == "invalid"
        else {}
    )
    result = _result(
        asyncio.run(_post_modern("tools/call", {"name": name, "arguments": arguments}))
    )
    assert result["isError"] is True
    assert result["content"][0]["text"] == expected


def test_schema_and_unexpected_errors_are_sanitized(monkeypatch, caplog) -> None:
    import logging

    schema = _result(
        asyncio.run(
            _post_modern(
                "tools/call",
                {
                    "name": "list_clients",
                    "arguments": {"top": "person@example.invalid"},
                },
            )
        )
    )
    assert schema["isError"] is True
    assert (
        schema["content"][0]["text"]
        == "Error executing tool list_clients: Argument top must be an integer from 1 to 200."
    )
    assert "person@example.invalid" not in schema["content"][0]["text"]

    class ExplodingClient:
        def list_clients(self, *_args):
            raise RuntimeError(
                "customer@example.invalid secret-key=https://vendor.invalid/key/abc"
            )

    monkeypatch.setattr(server, "_client", ExplodingClient())
    with caplog.at_level(logging.ERROR):
        result = _result(
            asyncio.run(
                _post_modern("tools/call", {"name": "list_clients", "arguments": {}})
            )
        )
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Error executing tool list_clients"
    assert "customer@example.invalid" not in caplog.text
    assert "vendor.invalid" not in caplog.text


def test_date_validation_names_expected_format_through_dispatch(monkeypatch) -> None:
    from bill4time_mcp.client import SafeToolFailure

    class InvalidDateClient:
        def list_time_entries_by_date_range(self, *_args):
            raise SafeToolFailure("Argument start_date must use YYYY-MM-DD format.")

    monkeypatch.setattr(server, "_client", InvalidDateClient())
    result = _result(
        asyncio.run(
            _post_modern(
                "tools/call",
                {
                    "name": "list_time_entries_for_date_range",
                    "arguments": {"start_date": "not-a-date", "end_date": "2026-01-01"},
                },
            )
        )
    )
    assert result["isError"] is True
    assert (
        result["content"][0]["text"]
        == "Error executing tool list_time_entries_for_date_range: Argument start_date must use YYYY-MM-DD format."
    )
