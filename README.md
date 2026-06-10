# bill4time-mcp

[![PyPI version](https://img.shields.io/pypi/v/bill4time-mcp.svg)](https://pypi.org/project/bill4time-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MCP server for [Bill4Time](https://bill4time.com) — API coverage for legal billing and time tracking. Use Bill4Time from Claude Desktop with natural language.

## What you can do

- **Clients** — list, filter by status, search active/disabled
- **Projects** — list, filter by client, status, billing method
- **Time Entries** — list by client, project, user, invoice, date range, billing status
- **Expenses** — list by client, project, invoice, date range
- **Invoices** — list by status (prebill/finalized), paid status, client, project, date range
- **Payments** — list by client, project, date range
- **Payments Applied** — track payment-to-invoice applications
- **Users** — list and look up users
- **Contacts** — list by status, date range, contact connections
- **Trust Accounting** — list trust records by client, project, date range

All resources support OData-style filtering via `filter_expr` parameter for advanced queries.

## Requirements

- Python 3.10+
- Claude Desktop (or any MCP-compatible client)
- Bill4Time API key (create in Settings → API tab)

> **Note:** The Bill4Time API is currently read-only. All tools retrieve data only.

## Installation

```bash
pip install bill4time-mcp
```

## Setup

```bash
bill4time-mcp-setup
```

This prompts for your API key and tests the connection. Credentials saved to `~/.bill4time-mcp/`.

Verify:

```bash
bill4time-mcp-verify
```

## Claude Desktop Configuration

```json
{
  "mcpServers": {
    "bill4time": {
      "command": "bill4time-mcp"
    }
  }
}
```

## Authentication Notes

Bill4Time uses an API key embedded directly in the URL path:

```text
https://secure.bill4time.com/b4t-api/{api_key}/v1/{resource}
```

No OAuth or token refresh required. Create API keys from **Settings → API** in your Bill4Time account.

## OData Filtering

All `list_*` tools accept a `filter_expr` parameter for advanced filtering:

```text
"status eq 'Active'"
"clientId eq 751"
"invoiceDate ge '2024-01-01' AND invoiceDate le '2024-12-31'"
"billingStatus eq 'Ready For Billing'"
```

Supported operators: `eq`, `ne`, `gt`, `ge`, `lt`, `le`

Use `top` to limit results, `orderby` to sort, `skip` for pagination.

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

**API key in URL path.** Bill4Time's API design embeds the API key directly as a path segment in every request URL (`/b4t-api/{api_key}/v1/...`). This is a Bill4Time API architecture constraint — the MCP loads your key from a local env file and never commits it to this repository. However, the key-in-URL design has the following implications you should be aware of:

- **Server/proxy access logs** on any machine between your client and Bill4Time's servers will record the full request URL, including the API key, for the duration of their log retention policy.
- **Network monitoring tools** that capture request URLs (e.g. HTTP proxies, security appliances, debugging tools) will expose the key in logged URLs.
- **If your key is compromised**, all API access to your Bill4Time account — billing data, client records, invoices, payments — is accessible until the key is rotated.

**Recommended practices:**

1. **Rotate your API key periodically** (quarterly at minimum) from **Settings → API** in your Bill4Time account.
2. **Keep access logs on this machine private** — ensure `~/.bill4time-mcp/` is not world-readable, and that any HTTP proxy or network capture tool running on this machine is restricted to authorised users.
3. **Rotate immediately** if you suspect the key has been exposed (e.g. via a shared log file, a network trace, or an accidental `curl -v` paste).
4. **Use least-privilege** — if Bill4Time offers read-only API keys in the future, prefer those for this MCP (all current tools are read-only).

## License

MIT
