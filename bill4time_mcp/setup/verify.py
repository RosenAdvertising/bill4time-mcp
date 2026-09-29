"""Verify Bill4Time MCP credentials."""

import logging
import sys

from bill4time_mcp.client import Bill4TimeClient, SafeToolFailure

logger = logging.getLogger(__name__)


def main():
    print("Verifying Bill4Time MCP credentials...")
    try:
        client = Bill4TimeClient()
        users = client.list_users(top=1)
        count = len(users) if isinstance(users, list) else "OK"
        print(f"✓ Connected. Users returned: {count}")
    except SafeToolFailure as e:
        # Fixed event label and exception class name only; no credential is logged.
        logger.warning(  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
            "credential_verification_rejected reason=classified_failure"
        )
        print(f"✗ Verification failed: {e}")
        sys.exit(1)
    except Exception:
        logger.warning("credential_verification_rejected reason=unexpected_failure")
        print("✗ Verification failed. Check the configuration and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
