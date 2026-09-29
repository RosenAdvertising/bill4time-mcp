"""Bill4Time MCP setup — API key configuration."""

import json
import logging
import sys
from getpass import getpass
from urllib.parse import quote

import requests

from bill4time_mcp import credentials
from bill4time_mcp.client import SafeToolFailure

BASE = "https://secure.bill4time.com/b4t-api"
logger = logging.getLogger(__name__)


def test_api_key(api_key: str) -> dict:
    url = f"{BASE}/{quote(str(api_key), safe='')}/v1/users"
    resp = requests.get(
        url,
        headers={"Accept": "application/json"},
        params={"$top": 1},
        timeout=15,
        allow_redirects=False,
    )
    if resp.status_code == 200:
        return resp.json()
    if resp.status_code == 403:
        raise SafeToolFailure(
            "Bill4Time access denied: the connected account lacks permission for this action "
            "(or the authorization expired; re-run bill4time-mcp-setup if so)."
        )
    if resp.status_code == 401:
        raise SafeToolFailure(
            "Bill4Time authorization was rejected or expired. Reauthorize with bill4time-mcp-setup."
        )
    # Fixed event label and HTTP status only; no API key value is logged.
    logger.warning(  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        "setup_api_key_rejected reason=vendor_http_error status=%s", resp.status_code
    )
    raise RuntimeError(f"API test failed ({resp.status_code})")


def main():
    print("Bill4Time MCP Setup")
    print("===================")
    print("Create an API key in Bill4Time: Settings → API tab.")
    print()

    try:
        api_key = getpass("API Key (UUID): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("API key is required.")
        sys.exit(1)
    if not api_key:
        logger.warning("setup_api_key_rejected reason=empty_input")
        print("API key is required.")
        sys.exit(1)

    print()
    print("Testing API key...")
    try:
        result = test_api_key(api_key)
        count = len(result) if isinstance(result, list) else "OK"
        print(f"✓ Connected. Users returned: {count}")
    except SafeToolFailure as exc:
        print(f"✗ API key verification failed: {exc}")
        sys.exit(1)
    except Exception:
        logger.warning("setup_api_key_rejected reason=verification_failed")
        print("✗ API key verification failed. Check the key and try again.")
        sys.exit(1)

    backend = credentials.set_secret("BILL4TIME_API_KEY", api_key)

    if backend == "keyring":
        print(f"✓ API key saved to the OS keyring ({credentials.storage_backend()}).")
    else:
        print(f"✓ API key saved to {credentials.ENV_FILE} (0600).")
    print()
    print("Add to your Claude Desktop config:")
    print(
        json.dumps(
            {"mcpServers": {"bill4time": {"command": "bill4time-mcp"}}}, indent=2
        )
    )


if __name__ == "__main__":
    main()
