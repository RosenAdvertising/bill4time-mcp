# MCP 2026-07-28 migration report

## Result

`bill4time-mcp` now targets MCP `2026-07-28`, up from `2025-11-25`.
The direct Python SDK dependency changed from `mcp>=1.28.1,<2` (locked to
1.28.1) to the exact migration release `mcp==2.0.0`. The refreshed lock adds
the SDK v2 dependency split, including `mcp-types==2.0.0`.

This was a migration, not a no-op. The starting server constructed v1
`FastMCP`, relied on its default protocol target, and had no protocol guard or
tracked tests. The authoritative repository-specific classification is in
[`SPEC-DELTA-2026-07-28.md`](SPEC-DELTA-2026-07-28.md).

No deployment, live Bill4Time account, or remote Git repository was touched.

## Implementation

- Replaced `FastMCP` with SDK v2 `MCPServer`, preserving the 59 registered
  read-only tools, three resources, three prompts, stdio startup, cached vendor
  client, credential precedence, and downstream Bill4Time API-key model.
- Added explicit server version `0.2.0`; SDK v2 supplies dual-era negotiation,
  modern discovery, result metadata, cache hints, and revised wire errors.
- Kept production transport stdio-only. Streamable HTTP is constructed only in
  offline conformance tests to verify the revision's required routing headers.
- Added an explicit Ruff policy for the declared Python 3.10 floor and a locked
  dev group for reproducible pytest/Ruff runs.

## AFFECTS-US mapping

| AFFECTS-US item | Handling | Commit |
| --- | --- | --- |
| Modern request metadata and discovery | SDK v2 dispatcher plus sessionless raw-wire discovery assertions | `feat: migrate server to MCP 2026-07-28`; `test: prove MCP 2026-07-28 conformance` |
| Required `resultType` | Discovery, lists, resource reads, and tool results assert `complete` | `test: prove MCP 2026-07-28 conformance` |
| Capability extensions | Discovery proves no unused extension is advertised | `test: prove MCP 2026-07-28 conformance` |
| Required list/read cache hints | SDK defaults `ttlMs: 0`, `cacheScope: private`; every applicable list and a resource read are asserted | `test: prove MCP 2026-07-28 conformance` |
| Deterministic tools and JSON Schema 2020-12 | Repeated 59-tool listings match; all tool schemas are objects; 49 list schemas carry bounded totals and explicit ordering | `feat: migrate server to MCP 2026-07-28`; `test: prove MCP 2026-07-28 conformance` |
| Resource-not-found `-32602` | Unknown Bill4Time resource regression asserts Invalid Params | `test: prove MCP 2026-07-28 conformance` |
| Revised protocol error allocation | Header mismatch `-32020`, unsupported version `-32022`, and unknown method `-32601` are asserted | `test: prove MCP 2026-07-28 conformance` |
| Legacy compatibility | SDK v2 client regression negotiates `2025-11-25` in legacy mode | `test: prove MCP 2026-07-28 conformance` |

## Canary sibling checks

| Check | Result | Finding and handling |
| --- | --- | --- |
| A. List limit/order | **FIXED** | All 49 list tools previously defaulted to unlimited `top=0`; many omitted `orderby`. Every list now defaults to a total cap of 50, schema-enforces 1 through 200, forwards a non-empty explicit sort, and truncates an overfilled vendor list response. General collection tools retain `skip`; there is no auto-pagination. |
| B. Silent rejections | **FIXED** | `_call`, vendor HTTP/JSON failures, list/date validation, credential-backend fallbacks, setup rejection, and verification rejection now emit PII-free reason logs. Tests prove invalid list controls and tool rejection logging. |
| C. Origin/CSP ceremony | **N/A** | The executable is a stdio MCP server and the repository contains no browser pages, HTML templates, or browser-facing application. The HTTP app exists only inside offline protocol tests. |
| D. PII in logs | **FIXED/CLEAN** | Vendor response bodies were removed from propagated setup/client errors, verification no longer prints a user record, and rejection logs include reason/type/status only. A source sweep found no subject, email, or user-name value passed to a logger. |

## Test inventory

Baseline before changes:

- `pytest -q`: **0/0 tests collected** (exit 5; no tracked tests existed).
- Ruff: **failed with 12 pre-existing findings**.

Final locked-environment verification:

- `uv sync --frozen`: **pass** (`mcp==2.0.0`, `mcp-types==2.0.0`).
- `uv run pytest -q tests/test_spec_2026_07_28.py`: **6/6 passed**.
- `uv run pytest -q`: **11/11 passed**.
- `uv run ruff check .`: **pass**.
- `uv run python tests/spec_check.py --mcp-only`: **pass**, pinned to
  `2026-07-28`.

The migration suite covers modern discovery, required HTTP headers, modern and
legacy negotiation, cache/result semantics, deterministic listing and schemas,
resource reads and `-32602`, and the revised transport/method errors. Canary
tests cover all list schemas, cap enforcement against an overfilled response,
order propagation through every list wrapper, and reason-only rejection logs.

## Judgment calls and remaining verification

- Cache behavior remains conservative (`private`, zero TTL); no positive cache
  or data-retention behavior was introduced.
- No MRTR, tasks, extension, tracing integration, publisher, subscription bus,
  MCP OAuth role, or browser surface was added because none existed.
- `id desc` is the default vendor order except the existing open-project view,
  which remains explicitly alphabetical; callers may override every sort.
- Live Bill4Time behavior was not tested because the task required no
  credentials. Vendor calls are method-verified with offline stubs only.
- The sandbox denied writes to the supplied checkout's `.git`. The complete
  local branch therefore lives in the granted scratch clone at
  `/private/tmp/claude-501/-Users-tobyrosen-Cowork-RA-Projects/7c2bbcf3-be6b-4bd4-bbc9-3870b657affb/scratchpad/fanout/bill4time-mcp`.
  It was created from default branch `origin/main` at `e75e6b2`; nothing was
  pushed. The original checkout's tracked files were not changed.

## Branch log

Before this report commit:

```text
80f37e2 test: prove MCP 2026-07-28 conformance
550d004 feat: migrate server to MCP 2026-07-28
aa5cfb2 docs: document MCP 2026-07-28 delta
e75e6b2 chore(deps): update actions/setup-python action to v7 (#35)
```

This document is committed as `docs: report MCP 2026-07-28 migration`; its
hash necessarily becomes available only after the commit is created.
