#!/usr/bin/env python3
"""Bill4Time MCP setup — API key configuration."""

import json
import sys
import requests

from bill4time_mcp import credentials

BASE = "https://secure.bill4time.com/b4t-api"


def test_api_key(api_key: str) -> dict:
    url = f"{BASE}/{api_key}/v1/users"
    resp = requests.get(url, headers={"Accept": "application/json"}, params={"$top": 1})
    if resp.status_code == 200:
        return resp.json()
    raise RuntimeError(f"API test failed ({resp.status_code}): {resp.text[:200]}")


def main():
    print("Bill4Time MCP Setup")
    print("===================")
    print("Create an API key in Bill4Time: Settings → API tab.")
    print()

    api_key = input("API Key (UUID): ").strip()
    if not api_key:
        print("API key is required.")
        sys.exit(1)

    print()
    print("Testing API key...")
    try:
        result = test_api_key(api_key)
        count = len(result) if isinstance(result, list) else "OK"
        print(f"✓ Connected. Users returned: {count}")
    except RuntimeError as e:
        print(f"✗ Failed: {e}")
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
