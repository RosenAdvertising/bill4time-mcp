# MCP 2026-07-28 protocol notes

Bill4Time MCP requires `mcp>=2.2,<3`; the lock resolves `mcp` and `mcp-types`
to 2.2.0. The server uses `MCPServer` and starts over stdio. The SDK implements
the protocol mechanics; the repository's offline tests check the behavior below.

| Protocol change                                          | Bill4Time handling                                                                                                                                                                    |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Modern per-request metadata and `server/discover`        | The in-process HTTP test checks discovery identity, supported revision, capabilities, and the absence of a session header. A client test also checks legacy `2025-11-25` negotiation. |
| `resultType` on results                                  | Wire tests check `complete` on discovery, listings, resource reads, and tool results.                                                                                                 |
| `ttlMs` and `cacheScope` on cacheable results            | List and resource-read tests check the SDK's private, zero-TTL defaults.                                                                                                              |
| Deterministic tool lists and JSON Schema 2020-12 support | Tests compare repeated tool listings and inspect object input schemas, including list limits.                                                                                         |
| Resource-not-found error                                 | The unknown-resource regression checks `-32602` Invalid Params.                                                                                                                       |
| Revised errors and HTTP routing headers                  | Wire tests check header mismatch `-32020`, unsupported version `-32022`, unknown method `-32601`, and required `Mcp-Method` / `Mcp-Name` headers.                                     |
| Capability extensions                                    | Discovery checks that no unused extension is advertised.                                                                                                                              |

Production does not expose HTTP, subscriptions, an event publisher, MCP OAuth,
server-initiated requests, or browser pages. The HTTP assertions use an
in-process app only. Bill4Time authentication is a separate downstream API key.

The [official changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog)
describes the protocol revision. See the [migration report](SPEC-MIGRATION-REPORT.md)
for reproducible local checks and their limits.
