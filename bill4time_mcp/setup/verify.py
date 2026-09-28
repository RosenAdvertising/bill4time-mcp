"""Verify Bill4Time MCP credentials."""

import logging
import sys

import requests

from bill4time_mcp.client import Bill4TimeClient

logger = logging.getLogger(__name__)


def main():
    print("Verifying Bill4Time MCP credentials...")
    try:
        client = Bill4TimeClient()
        users = client.list_users(top=1)
        count = len(users) if isinstance(users, list) else "OK"
        print(f"✓ Connected. Users returned: {count}")
    except (RuntimeError, ValueError, requests.RequestException) as e:
        logger.warning("credential_verification_rejected reason=%s", type(e).__name__)
        print(f"✗ Verification failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
