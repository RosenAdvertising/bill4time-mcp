#!/usr/bin/env python3
"""Verify Bill4Time MCP credentials."""

import json
import sys
from bill4time_mcp.client import Bill4TimeClient


def main():
    print("Verifying Bill4Time MCP credentials...")
    try:
        client = Bill4TimeClient()
        users = client.list_users(top=1)
        print(f"✓ Connected. Sample response:")
        print(json.dumps(users, indent=2))
    except Exception as e:
        print(f"✗ Verification failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
