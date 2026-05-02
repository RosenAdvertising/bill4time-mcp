# bill4time-mcp

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

```
https://secure.bill4time.com/b4t-api/{api_key}/v1/{resource}
```

No OAuth or token refresh required. Create API keys from **Settings → API** in your Bill4Time account.

## OData Filtering

All `list_*` tools accept a `filter_expr` parameter for advanced filtering:

```
"status eq 'Active'"
"clientId eq 751"
"invoiceDate ge '2024-01-01' AND invoiceDate le '2024-12-31'"
"billingStatus eq 'Ready For Billing'"
```

Supported operators: `eq`, `ne`, `gt`, `ge`, `lt`, `le`

Use `top` to limit results, `orderby` to sort, `skip` for pagination.

## Example usage in Claude

> "Show all unpaid invoices"

> "List time entries for project 456 this month"

> "Get all payments received from client 123 in 2024"

> "Show trust account activity for client 789"

> "List open projects ordered by project name"

## License

MIT
