"""Canary regressions for list caps, ordering, and rejection logs."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any

import pytest

from bill4time_mcp import server
from bill4time_mcp.client import Bill4TimeClient


class StubResponse:
    status_code = 200
    ok = True
    headers: dict[str, str] = {}

    def json(self) -> list[dict[str, int]]:
        return [{"id": item} for item in range(5)]


class StubSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get(self, url: str, params: dict[str, Any] | None = None) -> StubResponse:
        self.calls.append((url, params))
        return StubResponse()


def _client_with_stub_session() -> tuple[Bill4TimeClient, StubSession]:
    client = Bill4TimeClient.__new__(Bill4TimeClient)
    session = StubSession()
    client.session = session
    client._api_url = "https://example.invalid/redacted/v1"
    return client, session


def test_vendor_response_is_capped_and_order_is_forwarded() -> None:
    client, session = _client_with_stub_session()
    result = client.list_clients(top=2, orderby="id desc")

    assert result == [{"id": 0}, {"id": 1}]
    assert len(session.calls) == 1
    assert session.calls[0][1] == {"$top": 2, "$orderby": "id desc"}


def test_list_controls_reject_invalid_values_with_reason_only_logs(caplog) -> None:
    client, _session = _client_with_stub_session()
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ValueError, match="between 1 and 200"):
            client._build_params(top=201)
        with pytest.raises(ValueError, match="non-negative"):
            client._build_params(skip=-1)
        with pytest.raises(ValueError, match="must not be empty"):
            client._build_params(orderby="")

    assert "reason=invalid_top" in caplog.text
    assert "reason=negative_skip" in caplog.text
    assert "reason=missing_orderby" in caplog.text
    assert "201" not in caplog.text


def test_all_list_tool_schemas_enforce_cap_and_explicit_order() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    list_tools = [tool for tool in tools if tool.name.startswith("list_")]

    assert len(list_tools) == 49
    for tool in list_tools:
        properties = tool.input_schema["properties"]
        assert properties["top"] == {
            "default": 50,
            "maximum": 200,
            "minimum": 1,
            "title": "Top",
            "type": "integer",
        }
        assert properties["orderby"]["default"]


def test_all_list_wrappers_propagate_the_requested_order(monkeypatch) -> None:
    class RecordingClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

        def __getattr__(self, name: str):
            def call(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                return []

            return call

    fake = RecordingClient()
    monkeypatch.setattr(server, "_client", fake)

    tools = asyncio.run(server.mcp.list_tools())
    for tool in tools:
        if not tool.name.startswith("list_"):
            continue
        function = getattr(server, tool.name)
        kwargs: dict[str, Any] = {"top": 7, "orderby": "probe desc"}
        for name, parameter in inspect.signature(function).parameters.items():
            if parameter.default is inspect.Parameter.empty:
                kwargs[name] = 1 if name.endswith("_id") else "2026-01-01"

        output = json.loads(function(**kwargs))
        called_args = fake.calls[-1][1]
        called_kwargs = fake.calls[-1][2]
        assert output == []
        assert "probe desc" in called_args or "probe desc" in called_kwargs.values()

    assert len(fake.calls) == 49


def test_tool_rejection_log_omits_exception_message(caplog) -> None:
    private_value = "person@example.invalid"

    def reject() -> None:
        raise ValueError(private_value)

    with caplog.at_level(logging.WARNING):
        result = json.loads(server._call(reject))

    assert result == {"error": private_value}
    assert "reason=ValueError" in caplog.text
    assert private_value not in caplog.text
