"""Offline guard for the MCP protocol revision targeted by the locked SDK."""

from __future__ import annotations

import argparse

from mcp.types import LATEST_PROTOCOL_VERSION

EXPECTED_MCP_PROTOCOL_VERSION = "2026-07-28"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mcp-only",
        action="store_true",
        help="Check the installed MCP protocol revision",
    )
    args = parser.parse_args()
    if not args.mcp_only:
        parser.error("--mcp-only is required")

    if LATEST_PROTOCOL_VERSION != EXPECTED_MCP_PROTOCOL_VERSION:
        print(
            "Spec check: FAIL\n"
            f"Expected {EXPECTED_MCP_PROTOCOL_VERSION}, got {LATEST_PROTOCOL_VERSION}"
        )
        return 1

    print(f"Spec check: PASS ({EXPECTED_MCP_PROTOCOL_VERSION})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
