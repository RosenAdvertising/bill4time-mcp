# MCP specification delta: 2025-11-25 to 2026-07-28

Research date: 2026-08-09. Sources are limited to the official MCP
specification and the official MCP Python SDK documentation and release notes.

## Current target and migration release

The repository currently targets MCP `2025-11-25`:

- `pyproject.toml` declares `mcp>=1.28.1,<2`, and `uv.lock` resolves MCP Python
  SDK 1.28.1.
- `bill4time_mcp/server.py` constructs v1 `FastMCP` and calls `run()` with its
  default stdio transport. It does not override protocol negotiation or expose
  Streamable HTTP.
- The repository has no tracked tests and no MCP protocol-version guard.

The official changelog says `2026-07-28` follows `2025-11-25`
([spec changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)).
The implementation release is MCP Python SDK `2.0.0`, whose release notes say
it supports `2026-07-28` and every earlier revision from one server
([SDK v2.0.0 release notes](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.0.0)).
The API migration follows the official
[v1-to-v2 migration guide](https://py.sdk.modelcontextprotocol.io/migration/).

Verdicts mean:

- **AFFECTS-US**: this server exposes or relies on the changed surface. The SDK
  may implement the wire behavior, but the migration must still pin or test it.
- **NOT-APPLICABLE**: the feature or transport is not implemented here and will
  not be added merely because the new revision permits it.

## Protocol negotiation and lifecycle

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Protocol-level sessions and `Mcp-Session-Id` are removed for modern Streamable HTTP. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The executable exposes stdio only and keeps no MCP session state. A transport-level SDK regression test will still prove that the server can be built in stateless HTTP mode without a session header. |
| Modern requests replace `initialize` with per-request protocol version, client capabilities, and optional identity metadata; mismatches use `UnsupportedProtocolVersionError`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | The stdio server must accept modern self-describing requests while retaining v2's promised legacy negotiation. |
| Servers MUST implement `server/discover`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | Discovery is required for every modern server and must report this server's real identity, versions, and capabilities. |
| All results require `resultType`, normally `"complete"`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **AFFECTS-US** | Bill4Time returns tool, resource, prompt, list, and discovery results. |
| Server-initiated requests are replaced by Multi Round-Trip Requests (MRTR). [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | No handler uses roots, sampling, elicitation, or another server-to-client request. |
| `ping`, `logging/setLevel`, and `notifications/roots/list_changed` are removed; logging becomes per-request opt-in. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | Application code implements none of those protocol methods and sends no MCP log notifications. |

## Transports and notifications

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Streamable HTTP POST requests require `Mcp-Method` and, for named operations, `Mcp-Name`; tool parameters may opt into `x-mcp-header`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | Production startup is stdio-only. The migration suite will nevertheless exercise a generated stateless HTTP app and assert required routing-header behavior without adding an HTTP deployment mode. No tool opts into `x-mcp-header`. |
| HTTP GET and resource subscribe/unsubscribe are replaced by opt-in `subscriptions/listen`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | There is no HTTP endpoint, notification publisher, event store, or application subscription logic. SDK-managed capability declarations will not be expanded. |
| SSE resumability and redelivery are removed. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | The server uses stdio and has no event store or SSE resumption logic. |
| Legacy HTTP+SSE is deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | The server does not expose HTTP+SSE. |

## Capabilities and extensions

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Client and server capabilities gain an `extensions` field. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | `server/discover` exposes the capability shape; the server must not advertise an unused extension. |
| Experimental core tasks move to `io.modelcontextprotocol/tasks`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#major-changes) | **NOT-APPLICABLE** | No task handlers or task-augmented tools exist, and SDK v2.0.0 does not implement the extension. |
| Roots, Sampling, and Logging are deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | None is declared or used by application code. |
| Sampling `includeContext` values `thisServer` and `allServers` are deprecated. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | Sampling is not used. |

## Tools, resources, prompts, and cache semantics

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Tool, prompt, resource, resource-template list results and resource reads require `ttlMs` and `cacheScope`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The server exposes tools, resources, and prompts. Tests will assert the SDK's conservative private, zero-TTL defaults on every applicable result. There are no resource templates. |
| `tools/list` SHOULD be deterministic. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The large decorator-registered tool set must retain stable registration order. |
| Tool schemas accept all JSON Schema 2020-12 keywords and structured content may be any JSON value. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | SDK-generated schemas describe every tool. Migration tests will assert valid object schemas and the new limit bounds without widening the tools' string return contract. |
| Resource-not-found changes to `-32602` Invalid Params. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | The server exposes three static resources; an unknown URI must use the revised code. |
| URL elicitation completion and `elicitationId` are removed. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The server performs no elicitation. |
| Generated schema numeric keywords now use numbers rather than integers. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#other-schema-changes) | **NOT-APPLICABLE** | The repository neither vendors the MCP schema nor validates against its numeric meta-schema; SDK v2 absorbs the correction. |

## Authorization and security

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| Authorization servers SHOULD return RFC 9207 `iss`, and MCP clients validate it. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | Bill4Time MCP is neither an MCP authorization server nor an MCP OAuth client. Its vendor API key is independent downstream authentication. |
| MCP clients using Dynamic Client Registration send `application_type`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | No MCP client registration exists. |
| Persisted MCP client credentials are bound to their authorization-server issuer. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The server persists only a Bill4Time vendor API key, not MCP client credentials. |
| Dynamic Client Registration is deprecated in favor of Client ID Metadata Documents. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#deprecated) | **NOT-APPLICABLE** | The repository does not host or consume MCP DCR. |

## Errors, metadata, and observability

| Normative change | Verdict | Repository-specific reason |
| --- | --- | --- |
| MCP reserves `-32020..-32099`; header mismatch, missing capability, and unsupported version become `-32020`, `-32021`, and `-32022`; unknown methods use `-32601`. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **AFFECTS-US** | Modern stdio requests can hit unsupported-version and unknown-method paths; a transport-only HTTP regression covers header mismatch. No handler requires a new client capability, so `-32021` is not manufactured. |
| `_meta` formally carries W3C trace context. [Source](https://modelcontextprotocol.io/specification/2026-07-28/changelog#minor-changes) | **NOT-APPLICABLE** | The repository has no MCP metadata tracing integration of its own. SDK v2 owns its built-in propagation. |

The changelog's governance and SEP process changes impose no runtime behavior,
so they are excluded from the implementation verdicts. The migration also does
not adopt any newly deprecated feature.
