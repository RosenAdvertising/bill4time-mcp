"""In-process Streamable HTTP transport for MCP 2026-07-28."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx2
import pytest
from mcp.server.connection import Connection
from test_list_contracts import _client_with_stub_session

from bill4time_mcp import server

PROTOCOL_VERSION = "2026-07-28"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"
CLIENT_CAPABILITIES_META_KEY = "io.modelcontextprotocol/clientCapabilities"
CLIENT_INFO_META_KEY = "io.modelcontextprotocol/clientInfo"
SERVER_INFO_META_KEY = "io.modelcontextprotocol/serverInfo"


@pytest.fixture(autouse=True)
def _isolated_http_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "BILL4TIME_MCP_TRANSPORT",
        "BILL4TIME_MCP_HOST",
        "BILL4TIME_MCP_ALLOWED_HOSTS",
        "BILL4TIME_MCP_ALLOWED_ORIGINS",
        "PORT",
    ):
        monkeypatch.delenv(name, raising=False)


def _modern_request(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: int = 1,
) -> tuple[dict[str, str], dict[str, Any]]:
    request_params = dict(params or {})
    request_params["_meta"] = {
        PROTOCOL_VERSION_META_KEY: PROTOCOL_VERSION,
        CLIENT_CAPABILITIES_META_KEY: {},
        CLIENT_INFO_META_KEY: {"name": "bill4time-http-test", "version": "0"},
    }
    headers = {
        "accept": "application/json, text/event-stream",
        "content-type": "application/json",
        "mcp-protocol-version": PROTOCOL_VERSION,
        "mcp-method": method,
    }
    if method in {"tools/call", "prompts/get"}:
        headers["mcp-name"] = str(request_params["name"])
    return headers, {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": request_params,
    }


@asynccontextmanager
async def _http_client(
    app: Any, base_url: str = "http://127.0.0.1:8080"
) -> AsyncIterator[httpx2.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(
            transport=transport, base_url=base_url, timeout=5.0
        ) as client:
            yield client


async def _post(
    client: httpx2.AsyncClient,
    method: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: int = 1,
    header_overrides: dict[str, str] | None = None,
) -> httpx2.Response:
    headers, body = _modern_request(method, params, request_id=request_id)
    if header_overrides:
        headers.update(header_overrides)
    return await client.post("/mcp", headers=headers, json=body)


def _result(response: httpx2.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    return payload["result"]


def test_default_transport_is_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    assert server._requested_transport() == "stdio"
    called: list[str] = []
    monkeypatch.setattr(server.mcp, "run", lambda: called.append("stdio"))
    server.main()
    assert called == ["stdio"]


def test_bogus_transport_names_both_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BILL4TIME_MCP_TRANSPORT", "bogus")
    with pytest.raises(SystemExit) as raised:
        server.main()
    message = str(raised.value)
    assert "stdio" in message
    assert "streamable-http" in message


def test_non_integer_port_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "nope")
    with pytest.raises(SystemExit) as raised:
        server._port()
    assert "PORT" in str(raised.value)


def test_non_loopback_host_without_allowed_hosts_exits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BILL4TIME_MCP_HOST", "0.0.0.0")
    with pytest.raises(SystemExit) as raised:
        server.create_serve_app()
    assert "BILL4TIME_MCP_ALLOWED_HOSTS" in str(raised.value)


def test_server_identity_is_present() -> None:
    assert server.mcp.name == "bill4time"
    assert server.mcp.title
    assert server.mcp.version


def test_lifespan_runs_once_for_the_app_not_per_request() -> None:
    entered: list[int] = []

    @asynccontextmanager
    async def counting_lifespan(_app: Any):
        entered.append(1)
        yield {}

    original = server.mcp._lowlevel_server.lifespan
    server.mcp._lowlevel_server.lifespan = counting_lifespan
    try:

        async def two_requests() -> None:
            app = server.create_serve_app()
            async with _http_client(app) as client:
                first = await _post(client, "tools/list", request_id=1)
                second = await _post(client, "tools/list", request_id=2)
                assert first.status_code == 200
                assert second.status_code == 200

        asyncio.run(two_requests())
    finally:
        server.mcp._lowlevel_server.lifespan = original
    assert entered == [1]


def test_tools_list_matches_stdio_and_requests_are_sessionless() -> None:
    async def compare() -> None:
        stdio_tools = await server.mcp.list_tools()
        stdio_pairs = [
            (
                tool.name,
                tool.model_dump(by_alias=True, exclude_none=True)["inputSchema"],
            )
            for tool in stdio_tools
        ]
        app = server.create_serve_app()
        async with _http_client(app) as client:
            first = await _post(client, "tools/list", request_id=1)
            second = await _post(
                client,
                "tools/list",
                request_id=2,
                header_overrides={"mcp-session-id": "not-a-session"},
            )
        for response in (first, second):
            assert "mcp-session-id" not in response.headers
        http_tools = _result(first)["tools"]
        http_pairs = [(tool["name"], tool["inputSchema"]) for tool in http_tools]
        assert http_pairs == stdio_pairs
        assert [tool["name"] for tool in _result(second)["tools"]] == [
            name for name, _schema in stdio_pairs
        ]

    asyncio.run(compare())


_CONNECTION_STATE_SENTINEL = "bill4time-request-state"


def test_each_request_gets_a_fresh_connection_state() -> None:
    """Two POSTs must not share Connection.state or a sentinel written into it."""
    observed: list[tuple[int, bool]] = []
    original = Connection.from_envelope.__func__

    def observe(cls: type[Connection], *args: Any, **kwargs: Any) -> Connection:
        connection = original(cls, *args, **kwargs)
        leaked = _CONNECTION_STATE_SENTINEL in connection.state
        connection.state[_CONNECTION_STATE_SENTINEL] = len(observed) + 1
        observed.append((id(connection.state), leaked))
        return connection

    Connection.from_envelope = classmethod(observe)  # type: ignore[method-assign]
    try:

        async def two_requests() -> None:
            app = server.create_serve_app()
            async with _http_client(app) as client:
                first = await _post(client, "tools/list", request_id=1)
                second = await _post(client, "tools/list", request_id=2)
            assert first.status_code == 200, first.text
            assert second.status_code == 200, second.text

        asyncio.run(two_requests())
    finally:
        Connection.from_envelope = classmethod(original)

    assert len(observed) == 2, observed
    state_ids = [state_id for state_id, _leaked in observed]
    leaked = [was_present for _state_id, was_present in observed]
    assert leaked == [False, False] and state_ids[0] != state_ids[1], (
        "request Connection.state is not isolated: "
        f"sentinel_already_present={leaked} state_ids={state_ids}"
    )


def test_read_tool_runs_over_http(monkeypatch: pytest.MonkeyPatch) -> None:
    client, session = _client_with_stub_session()
    monkeypatch.setattr(server, "_client", client)
    expected_text = """\
[
  {
    "id": 0
  },
  {
    "id": 1
  },
  {
    "id": 2
  },
  {
    "id": 3
  },
  {
    "id": 4
  }
]"""

    async def call() -> dict[str, Any]:
        app = server.create_serve_app()
        async with _http_client(app) as http:
            response = await _post(
                http,
                "tools/call",
                {"name": "get_client", "arguments": {"client_id": 7}},
            )
        return _result(response)

    result = asyncio.run(call())
    assert session.calls == [
        ("https://example.invalid/redacted/v1/clients", {"$filter": "id eq 7"})
    ]
    assert result["isError"] is False
    assert result["content"] == [{"type": "text", "text": expected_text}]
    assert result["structuredContent"] == {"result": expected_text}


def test_allowed_hosts_refuse_other_host_and_bad_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BILL4TIME_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("BILL4TIME_MCP_ALLOWED_HOSTS", "bill4time.example")
    monkeypatch.setenv("BILL4TIME_MCP_ALLOWED_ORIGINS", "https://bill4time.example")
    app = server.create_serve_app()

    async def probe() -> tuple[int, int]:
        async with _http_client(app, "http://bill4time.example") as client:
            foreign_host = await _post(
                client,
                "tools/list",
                header_overrides={"host": "other.example"},
            )
            bad_origin = await _post(
                client,
                "tools/list",
                header_overrides={"origin": "https://evil.example"},
            )
        return foreign_host.status_code, bad_origin.status_code

    host_status, origin_status = asyncio.run(probe())
    assert host_status == 421
    assert origin_status == 403


def test_get_and_delete_are_method_not_allowed() -> None:
    async def methods() -> tuple[int, int]:
        app = server.create_serve_app()
        async with _http_client(app) as client:
            modern = {"mcp-protocol-version": PROTOCOL_VERSION}
            get_response = await client.get("/mcp", headers=modern)
            delete_response = await client.delete("/mcp", headers=modern)
        return get_response.status_code, delete_response.status_code

    assert asyncio.run(methods()) == (405, 405)


def test_discover_advertises_modern_protocol_and_version() -> None:
    async def discover() -> dict[str, Any]:
        app = server.create_serve_app()
        async with _http_client(app) as client:
            response = await _post(client, "server/discover")
        assert response.status_code == 200
        assert "mcp-session-id" not in response.headers
        return _result(response)

    result = asyncio.run(discover())
    assert PROTOCOL_VERSION in result["supportedVersions"]
    version = result["_meta"][SERVER_INFO_META_KEY]["version"]
    assert isinstance(version, str) and version
