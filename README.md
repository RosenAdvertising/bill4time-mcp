# Bill4Time MCP server

[![CI](https://github.com/RosenAdvertising/bill4time-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/RosenAdvertising/bill4time-mcp/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP 2026-07-28](https://img.shields.io/badge/MCP-2026--07--28-7C3AED.svg)](https://modelcontextprotocol.io)
[![PyPI version](https://img.shields.io/pypi/v/bill4time-mcp.svg)](https://pypi.org/project/bill4time-mcp/)

Give Claude and other MCP clients read-only access to Bill4Time billing, time and trust data.

Bill4Time MCP server is a [Model Context Protocol](https://modelcontextprotocol.io) server for [Bill4Time](https://bill4time.com), the time tracking and billing platform. It registers 59 tools, all read-only. It runs over stdio by default, for desktop clients such as Claude Desktop, and offers an opt-in stateless Streamable HTTP mode that implements MCP specification 2026-07-28. Bill4Time credentials stay on the machine that runs the server: they come from the setup command and your operating system's keyring, never from the client. The Bill4Time API is currently read-only.

## Features

- **Clients**: list clients, filter by status, and look up active or disabled clients.
- **Projects**: list projects, and filter by client, status or billing method.
- **Time entries**: list by client, project, user, invoice, date range or billing status.
- **Expenses**: list by client, project, invoice or date range.
- **Invoices**: list by status (prebill, finalized, paid, partially paid, unpaid), client, project or date range.
- **Payments**: list payments by client, project or date range, and see which invoices each payment was applied to.
- **Contacts and users**: list contacts by status or date range, list contact connections, and look up users.
- **Trust accounting**: list trust records by client, project or date range.
- **Filtering**: pass OData-style `filter_expr` expressions to the general list tools for advanced queries.

## Tools

The server registers 59 tools, all of them read-only.

<details>
<summary>All 59 tools</summary>

- `get_client`
- `get_contact`
- `get_expense`
- `get_invoice`
- `get_payment`
- `get_payment_applied`
- `get_project`
- `get_time_entry`
- `get_trust_record`
- `get_user`
- `list_active_clients`
- `list_active_contacts`
- `list_clients`
- `list_closed_projects`
- `list_contact_connections`
- `list_contact_connections_for_client`
- `list_contact_connections_for_contact`
- `list_contact_connections_for_project`
- `list_contacts`
- `list_contacts_for_date_range`
- `list_disabled_clients`
- `list_expenses`
- `list_expenses_for_client`
- `list_expenses_for_date_range`
- `list_expenses_for_invoice`
- `list_expenses_for_project`
- `list_finalized_invoices`
- `list_invoices`
- `list_invoices_for_client`
- `list_invoices_for_date_range`
- `list_invoices_for_project`
- `list_open_projects`
- `list_paid_invoices`
- `list_partially_paid_invoices`
- `list_payments`
- `list_payments_applied`
- `list_payments_applied_for_date_range`
- `list_payments_applied_for_invoice`
- `list_payments_applied_for_payment`
- `list_payments_for_client`
- `list_payments_for_date_range`
- `list_payments_for_project`
- `list_prebill_invoices`
- `list_projects`
- `list_projects_by_billing_method`
- `list_projects_for_client`
- `list_time_entries`
- `list_time_entries_by_billing_status`
- `list_time_entries_for_client`
- `list_time_entries_for_date_range`
- `list_time_entries_for_invoice`
- `list_time_entries_for_project`
- `list_time_entries_for_user`
- `list_trust_records`
- `list_trust_records_for_client`
- `list_trust_records_for_date_range`
- `list_trust_records_for_project`
- `list_unpaid_invoices`
- `list_users`

</details>

### Prompts and resources

The server also registers three prompts and three resources.

| Prompt | What it does |
| --- | --- |
| `client_billing_summary` | Builds the full billing picture for one client: projects, time, invoices and payments. Takes `client_id`. |
| `trust_account_review` | Reviews a client's trust accounting records for compliance. Takes `client_id`. |
| `unbilled_time_report` | Reports unbilled time entries for a date range. Takes `start_date` and `end_date`. |

| Resource | What it provides |
| --- | --- |
| `bill4time://active_clients` | Active clients. |
| `bill4time://users` | Bill4Time users (the timekeeper list). |
| `bill4time://security-notes` | Security notes for the server, including the API key in the URL path. |

## Requirements

- Python 3.10 or later.
- A Bill4Time account with an API key (create one in Settings → API tab).
- An MCP client such as Claude Desktop.

## Installation

Install [uv](https://docs.astral.sh/uv/), then clone the repository and install its locked dependencies:

```bash
git clone https://github.com/RosenAdvertising/bill4time-mcp.git
cd bill4time-mcp
uv sync --locked
```

Releases are also published to PyPI: `pip install bill4time-mcp` installs version 0.3.0, which predates the HTTP mode described below. Install from source to use HTTP mode.

## Configuration

Run the setup command once. It prompts for your API key, tests the connection, and saves the key to your operating system's keyring (see [Credential storage](#credential-storage)):

```bash
uv run bill4time-mcp-setup
```

After changing the API key, restart the MCP server or client session so the new key is loaded.

Check the connection:

```bash
uv run bill4time-mcp-verify
```

Server messages that say to run `bill4time-mcp-setup` mean `uv run bill4time-mcp-setup` from your clone.

The server reads these variables, which you can also set in its environment:

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `BILL4TIME_API_KEY` | Yes (saved by setup) | Credential store | Bill4Time API key. |
| `BILL4TIME_MCP_USE_KEYRING` | No | `1` | Set to `0` to skip the operating system keyring and use the environment and the `.env` file fallback. |

### Credential storage

By default the API key is stored in your operating system's native secret store
via the cross-platform [`keyring`](https://github.com/jaraco/keyring) library:

| OS      | Backend                                  |
| ------- | ---------------------------------------- |
| macOS   | Keychain                                 |
| Windows | Credential Manager                       |
| Linux   | Secret Service (GNOME Keyring / KWallet) |

The secret is saved under the service name `bill4time-mcp`. Nothing is written to
disk in clear text.

**File fallback.** On a host with no keyring backend (e.g. a headless Linux box
without Secret Service), or if you set `BILL4TIME_MCP_USE_KEYRING=0`, the key
falls back to a `~/.bill4time-mcp/.env` file with `0600` permissions.

On Windows, the file is stored in the user's profile and protected by Windows'
default per-user access rules. On POSIX, files are created with `0600` permissions
and writes fail closed if private permissions cannot be established.

**Read order.** A key already set in the process environment wins. Otherwise the server reads the OS keyring, then the `.env` file fallback. To make a key rotated in the keyring take effect, unset `BILL4TIME_API_KEY` in the shell that starts the server.

**Pluggable backend.** `keyring` lets you point at any secret store. For example,
install [`keyrings.cryptfile`](https://pypi.org/project/keyrings.cryptfile/) for
an encrypted file backend, or a cloud backend, then select it with the standard
`PYTHON_KEYRING_BACKEND` environment variable or a `keyringrc.cfg`. See the
[keyring configuration docs](https://github.com/jaraco/keyring#configuring).

## Usage with Claude Desktop

Add the server to Claude Desktop's configuration file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "bill4time": {
      "command": "uv",
      "args": ["run", "--locked", "--directory", "/absolute/path/to/bill4time-mcp", "bill4time-mcp"]
    }
  }
}
```

Replace `/absolute/path/to/bill4time-mcp` with the path of your clone, then restart Claude Desktop. Any other stdio MCP client uses the same command and arguments.

## HTTP mode

Stdio is the default. Set `BILL4TIME_MCP_TRANSPORT=streamable-http` to serve the stateless Streamable HTTP transport from MCP specification 2026-07-28 at `/mcp`. Each request stands alone: no initialization handshake and no `Mcp-Session-Id`. Clients on earlier protocol versions are served on the same endpoint.

> **Security: this endpoint has no authentication and no TLS.** Anyone who can reach the port can run every tool with this server's vendor credentials. Keep the default loopback bind (`127.0.0.1`), or put the server behind an authenticating TLS proxy on a private network. `BILL4TIME_MCP_ALLOWED_HOSTS` and `BILL4TIME_MCP_ALLOWED_ORIGINS` protect against browser DNS rebinding, not against direct callers. A proxy in front of it needs connection and idle timeouts: a legacy-style `GET /mcp` with `Accept: text/event-stream` holds a stream open until the client disconnects.

| Variable | Default | Purpose |
| --- | --- | --- |
| `BILL4TIME_MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http`. |
| `BILL4TIME_MCP_HOST` | `127.0.0.1` | Bind address. `127.0.0.1`, `localhost` and `::1` use the SDK's built-in Host and Origin checks; any other value requires `BILL4TIME_MCP_ALLOWED_HOSTS`. |
| `PORT` | `8080` | Port; must be an integer. |
| `BILL4TIME_MCP_ALLOWED_HOSTS` | unset | Comma-separated `Host` header values accepted on a non-loopback bind, such as `mcp.example.com:8080` or `mcp.example.com:*`. |
| `BILL4TIME_MCP_ALLOWED_ORIGINS` | unset | Comma-separated `Origin` values accepted on a non-loopback bind, such as `https://client.example.com`. Requests without an `Origin` header are accepted. |

Bill4Time credentials come from the same configuration as stdio (see [Configuration](#configuration)), never from the request.

```bash
BILL4TIME_MCP_TRANSPORT=streamable-http PORT=8080 uv run --locked bill4time-mcp
```

Point the MCP client at `http://127.0.0.1:8080/mcp`.

## Error handling

A failed tool call returns an MCP error result (`isError`). Expected failures return a fixed message prefixed with `Error executing tool` and the tool name, for example "Error executing tool list_clients: Bill4Time resource was not found. Check the requested record." The server never passes a Bill4Time response body, a request URL or the API key back to the client.

| Situation | What the tool returns |
| --- | --- |
| API key missing | "Missing BILL4TIME_API_KEY. Set it or run bill4time-mcp-setup. Restart the MCP server after setup." |
| HTTP 401 | "Bill4Time authorization was rejected or expired. Reauthorize with bill4time-mcp-setup." |
| HTTP 403 | "Bill4Time access denied: the connected account lacks permission for this action (or the authorization expired; re-run bill4time-mcp-setup if so)." |
| HTTP 404, or a `get_` tool that finds no matching record | "Bill4Time resource was not found. Check the requested record." |
| HTTP 429 | "Bill4Time rate limit reached. Retry after N seconds." where N comes from the `Retry-After` header, or "Retry later." when the header is missing or unusable. |
| Any other error status, or a redirect | "Bill4Time returned HTTP 500: server error" (the status varies). The reason after the colon comes from a fixed list: invalid API key, authorization rejected, access denied, resource not found, rate limit reached, service temporarily unavailable, server error, or request failed. |
| Timeout or connection failure | "Bill4Time read failed because the connection timed out or was unavailable. Check the connection and retry." |
| Response that is not JSON | "Bill4Time returned an unreadable response. Try again later." |
| Invalid arguments | A message such as "Argument top must be an integer from 1 to 200." or "Argument start_date must use YYYY-MM-DD format." |
| Anything else | "Error executing tool list_clients" (the tool name) with no detail. |

Every Bill4Time request has a 30-second timeout. The server does not retry failed requests and does not follow redirects. A failed resource read returns the same fixed messages, "Bill4Time resource was not found." for an unknown resource and "Error reading resource" for an unexpected failure.

At startup the server exits with a message on stderr and a non-zero status when `BILL4TIME_MCP_TRANSPORT` is neither `stdio` nor `streamable-http`, when `PORT` is not an integer, or when a non-loopback `BILL4TIME_MCP_HOST` is set without `BILL4TIME_MCP_ALLOWED_HOSTS`.

## Authentication notes

Bill4Time uses an API key embedded directly in the URL path:

```text
https://secure.bill4time.com/b4t-api/{api_key}/v1/{resource}
```

No OAuth or token refresh required. Create API keys from **Settings → API** in your Bill4Time account.

## OData filtering

General collection list tools accept a `filter_expr` parameter for advanced filtering:

```text
"status eq 'Active'"
"clientId eq 751"
"invoiceDate ge '2024-01-01' AND invoiceDate le '2024-12-31'"
"billingStatus eq 'Ready For Billing'"
```

Supported operators: `eq`, `ne`, `gt`, `ge`, `lt`, `le`

Every list tool defaults to 50 records and an explicit deterministic sort
(`id desc`, except the alphabetical open-project view). Use `top` to choose a
total result cap from 1 through 200, `orderby` to override the sort, and `skip`
for pagination on the general collection tools.

## Example usage in Claude

> "Show all unpaid invoices"
>
> "List time entries for project 456 this month"
>
> "Get all payments received from client 123 in 2024"
>
> "Show trust account activity for client 789"
>
> "List open projects ordered by project name"

## Security note

**API key in URL path.** Bill4Time's API design embeds the API key directly as a path segment in every request URL (`/b4t-api/{api_key}/v1/...`). This is a Bill4Time API architecture constraint. The MCP resolves the key from the OS keyring, process environment, or a local file fallback; it never logs the key. However, the key-in-URL design has the following implications you should be aware of:

- **Server/proxy access logs** on any machine between your client and Bill4Time's servers will record the full request URL, including the API key, for the duration of their log retention policy.

- **Network monitoring tools** that capture request URLs (e.g. HTTP proxies, security appliances, debugging tools) will expose the key in logged URLs.

- **If your key is compromised**, all API access to your Bill4Time account — billing data, client records, invoices, payments — is accessible until the key is rotated.

**Recommended practices:**

1. **Rotate your API key periodically** (quarterly at minimum) from **Settings → API** in your Bill4Time account.

2. **Keep access logs on this machine private** — ensure `~/.bill4time-mcp/` is not world-readable, and that any HTTP proxy or network capture tool running on this machine is restricted to authorised users.

3. **Rotate immediately** if you suspect the key has been exposed (e.g. via a shared log file, a network trace, or an accidental `curl -v` paste).

4. **Use least-privilege** — if Bill4Time offers read-only API keys in the future, prefer those for this MCP (all current tools are read-only).

## Testing

The test suite runs offline and needs no Bill4Time account: every Bill4Time API call is answered by an in-process stub session or by a stub HTTP server on 127.0.0.1. It covers list tool arguments and limits, error handling, credential file handling, the setup and verify commands, the stdio server, and the Streamable HTTP transport including the 2026-07-28 wire format, Host and Origin checks and stateless requests.

```bash
uv sync --locked
uv run --locked pytest -q
```

CI runs the suite on every push and pull request to `main`.

## License

MIT. See [LICENSE](LICENSE).
