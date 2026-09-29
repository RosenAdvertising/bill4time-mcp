# MCP 2026-07-28 migration

Bill4Time MCP targets protocol revision `2026-07-28`. The project requires the
Python MCP SDK `mcp>=2.2,<3`; `uv.lock` resolves both `mcp` and its companion
`mcp-types` to 2.2.0. The server uses `MCPServer` with application version
`0.2.0` and retains stdio startup, read-only Bill4Time tools, resources,
prompts, and the existing vendor API-key model.

The SDK handles protocol negotiation and modern request routing. Offline wire
tests cover `server/discover`, modern and legacy negotiation, required
`resultType`, private zero-TTL cache hints, deterministic tool listings, tool
schemas, resource reads, and the revised protocol errors. Production startup
uses stdio; the test suite creates an in-process Streamable HTTP app to check
routing headers. The [spec delta](SPEC-DELTA-2026-07-28.md) maps the protocol
changes to this server.

The migration also bounds list results to 50 by default and 200 at most, uses
an explicit sort, and keeps `skip` on general collection tools. Rejection logs
record reasons without vendor response bodies or credential values.

## Reproduce the local checks

With dependencies installed from `uv.lock` in `.venv`, run:

```bash
BILL4TIME_API_KEY=offline-test-placeholder BILL4TIME_MCP_USE_KEYRING=0 .venv/bin/pytest -q
.venv/bin/ruff check .
BILL4TIME_API_KEY=offline-test-placeholder BILL4TIME_MCP_USE_KEYRING=0 .venv/bin/python tests/spec_check.py --mcp-only
uv lock --check --offline
```

These tests use fake credentials, mocked Bill4Time responses, and in-process
protocol transports. They do not establish live vendor response shapes or
production deployment behavior. In particular, the dynamic list-wrapper stub
checks forwarding but cannot prove that every wrapper selects the intended
client method.

## Public error behavior

Tool calls return `isError=true` for classified failures. The server exposes
only fixed, actionable messages for known configuration, authorization,
not-found, rate-limit, transport, and input-validation failures. Unexpected
exceptions are masked as `Error executing tool <name>`. Resource reads use
classified safe messages when available and a fixed generic message otherwise.
Raw exception details, vendor response bodies, request URLs, and credentials are
not returned to clients or written to stderr.
