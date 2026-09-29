"""Exercise actual client failure paths through the MCP wire handler, offline."""

import asyncio
import logging

import pytest
import requests
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
        (302, {"message": PRIVATE}, None, "Bill4Time returned HTTP 302: request failed"),
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
            "Bill4Time access denied: the connected account lacks permission for this action (or the authorization expired; re-run bill4time-mcp-setup if so).",
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
            "Bill4Time rate limit reached. Retry after 300 seconds.",
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
        == "Error executing tool list_clients: Missing BILL4TIME_API_KEY. Set it or run bill4time-mcp-setup. Restart the MCP server after setup."
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


@pytest.mark.parametrize("failure", [requests.Timeout, requests.ConnectionError])
def test_read_transport_failure_is_safe_and_has_timeout(monkeypatch, caplog, failure):
    client, session = _client_with_stub_session()

    def fail(url, **kwargs):
        assert kwargs["timeout"] == client_module.REQUEST_TIMEOUT
        assert kwargs["allow_redirects"] is False
        raise failure(f"{PRIVATE} /b4t-api/key-secret/v1/users")

    monkeypatch.setattr(session, "get", fail)
    monkeypatch.setattr(server, "_client", client)
    with caplog.at_level(logging.WARNING):
        result = dispatch()
    assert result["isError"] is True
    assert result["content"][0]["text"] == (
        "Error executing tool list_clients: Bill4Time read failed because the connection timed out or was unavailable. Check the connection and retry."
    )
    assert PRIVATE not in str(result) + caplog.text
    assert "key-secret" not in str(result) + caplog.text


def test_path_segment_is_quoted_without_encoding_whole_path():
    client, session = _client_with_stub_session()
    client._get("../x")
    assert session.calls[0][0].endswith("/..%2Fx")


def test_redirect_response_is_not_reported_as_success():
    client, session = _client_with_stub_session()

    class RedirectResponse:
        status_code = 302
        ok = True
        headers = {"Location": "https://attacker.invalid/"}

        def json(self):
            return {"message": PRIVATE}

    def redirect(url, **kwargs):
        assert kwargs["allow_redirects"] is False
        return RedirectResponse()

    session.get = redirect
    with pytest.raises(SafeToolFailure) as raised:
        client.list_clients()
    assert str(raised.value) == "Bill4Time returned HTTP 302: request failed"
    assert PRIVATE not in str(raised.value)


def test_retry_after_large_hint_is_preserved_without_sleep(monkeypatch):
    client, session = _client_with_stub_session()
    monkeypatch.setattr(
        session,
        "get",
        lambda *args, **kwargs: ErrorResponse(429, {}, "300"),
    )
    with pytest.raises(SafeToolFailure) as raised:
        client.list_clients()
    assert str(raised.value) == "Bill4Time rate limit reached. Retry after 300 seconds."


def test_resource_boundary_suppresses_exception_chains_and_key(monkeypatch, caplog):
    class BadResourceClient:
        def list_clients_by_status(self, *args):
            raise RuntimeError("https://vendor.invalid/b4t-api/key-secret/v1/users")

    monkeypatch.setattr(server, "_client", BadResourceClient())
    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(Exception) as raised,
    ):
        asyncio.run(server.mcp.read_resource("bill4time://active_clients"))
    assert str(raised.value) == "Error reading resource"
    assert raised.value.__cause__ is None
    assert "key-secret" not in caplog.text
    assert "vendor.invalid" not in caplog.text


def test_resource_boundary_preserves_only_classified_safe_message(monkeypatch):
    class SafeResourceClient:
        def list_clients_by_status(self, *args):
            raise SafeToolFailure(
                "Bill4Time resource was not found. Check the requested record."
            )

    monkeypatch.setattr(server, "_client", SafeResourceClient())
    with pytest.raises(Exception) as raised:
        asyncio.run(server.mcp.read_resource("bill4time://active_clients"))
    assert (
        str(raised.value)
        == "Bill4Time resource was not found. Check the requested record."
    )
    assert raised.value.__cause__ is None


def test_verify_safe_failure_and_unknown_fallback(monkeypatch, capsys):
    from bill4time_mcp.setup import verify

    class MissingKey:
        def __init__(self):
            raise SafeToolFailure("Missing BILL4TIME_API_KEY. Run bill4time-mcp-setup.")

    monkeypatch.setattr(verify, "Bill4TimeClient", MissingKey)
    with pytest.raises(SystemExit) as raised:
        verify.main()
    assert raised.value.code == 1
    assert "Missing BILL4TIME_API_KEY" in capsys.readouterr().out

    class UnknownFailure:
        def __init__(self):
            raise RuntimeError(PRIVATE)

    monkeypatch.setattr(verify, "Bill4TimeClient", UnknownFailure)
    with pytest.raises(SystemExit) as raised:
        verify.main()
    output = capsys.readouterr().out
    assert raised.value.code == 1
    assert "Check the configuration" in output
    assert PRIVATE not in output


def test_setup_no_credential_and_bad_key_exit_without_traceback(
    monkeypatch, capsys, caplog
):
    import requests

    from bill4time_mcp.setup import setup_wizard

    monkeypatch.setattr(setup_wizard, "getpass", lambda _prompt: "")
    with pytest.raises(SystemExit) as raised:
        setup_wizard.main()
    assert raised.value.code == 1
    assert "API key is required" in capsys.readouterr().out

    monkeypatch.setattr(setup_wizard, "getpass", lambda _prompt: "bad-key")
    calls = []

    class RejectedKeyResponse:
        status_code = 403

    def reject_key(url, **kwargs):
        calls.append((url, kwargs))
        return RejectedKeyResponse()

    monkeypatch.setattr(requests, "get", reject_key)
    with pytest.raises(SystemExit) as raised:
        setup_wizard.main()
    output = capsys.readouterr().out
    assert raised.value.code == 1
    assert "verification failed" in output.lower()
    assert PRIVATE not in output
    assert "bad-key" not in output
    assert "bad-key" not in caplog.text
    assert calls[0][1]["timeout"] == client_module.REQUEST_TIMEOUT
    assert "bad-key" in calls[0][0]


def test_setup_eof_is_a_clear_nonzero_exit(monkeypatch, capsys):
    from bill4time_mcp.setup import setup_wizard

    monkeypatch.setattr(
        setup_wizard, "getpass", lambda _prompt: (_ for _ in ()).throw(EOFError)
    )
    with pytest.raises(SystemExit) as raised:
        setup_wizard.main()
    assert raised.value.code == 1
    assert "API key is required" in capsys.readouterr().out


def test_internal_validation_failure_stays_masked(monkeypatch, caplog):
    from pydantic import BaseModel

    class InternalResult(BaseModel):
        top: int

    class BrokenClient:
        def list_clients(self, *args):
            InternalResult.model_validate({"top": PRIVATE})

    monkeypatch.setattr(server, "_client", BrokenClient())
    result = dispatch()
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Error executing tool list_clients"
    assert PRIVATE not in str(result) + caplog.text


def test_api_key_path_is_escaped(monkeypatch):
    from bill4time_mcp.setup import setup_wizard

    calls = []

    def response(url, **kwargs):
        calls.append((url, kwargs))
        return ErrorResponse(200, [])

    monkeypatch.setattr(requests, "get", response)
    setup_wizard.test_api_key("../x")
    assert calls[0][0].endswith("/..%2Fx/v1/users")
    assert calls[0][1]["timeout"] == client_module.REQUEST_TIMEOUT
    assert calls[0][1]["allow_redirects"] is False
    monkeypatch.setattr(client_module, "API_KEY", "../x")
    assert client_module.Bill4TimeClient()._api_url.endswith("/..%2Fx/v1")


def test_fallback_credential_file_is_created_private(monkeypatch, tmp_path):
    from bill4time_mcp import credentials

    config_dir = tmp_path / "private-config"
    env_file = config_dir / ".env"
    monkeypatch.setattr(credentials, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(credentials, "ENV_FILE", env_file)
    credentials._write_env_file({"BILL4TIME_API_KEY": "fake-token"})
    assert env_file.read_text() == "BILL4TIME_API_KEY=fake-token\n"
    assert env_file.stat().st_mode & 0o777 == 0o600
