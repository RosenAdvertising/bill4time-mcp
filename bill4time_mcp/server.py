"""Bill4Time MCP server — MCPServer tools for the Bill4Time API."""

import asyncio
import json
import logging
import os
import threading
from importlib.metadata import version as package_version
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import (
    ResourceError,
    ResourceNotFoundError,
    ToolError,
    UnexpectedToolError,
)
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import CallToolResult, TextContent
from pydantic import Field, ValidationError
from starlette.applications import Starlette

from bill4time_mcp.client import (
    DEFAULT_LIST_LIMIT,
    DEFAULT_ORDERBY,
    MAX_LIST_LIMIT,
    Bill4TimeClient,
    SafeToolFailure,
)

logger = logging.getLogger(__name__)

STREAMABLE_HTTP_TRANSPORT = "streamable-http"
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class SafeMCPServer(MCPServer):
    """Keep the SDK's schemas while sanitizing its tool error boundary."""

    async def call_tool(self, name, arguments, context=None):
        try:
            return await super().call_tool(name, arguments, context)
        except Exception as exc:
            cause = exc.__cause__
            if isinstance(cause, SafeToolFailure) and not isinstance(
                exc, UnexpectedToolError
            ):
                text = f"Error executing tool {name}: {cause}"
                logger.info("tool_call_failed reason=expected_failure")
            elif (
                isinstance(exc, ToolError)
                and not isinstance(exc, UnexpectedToolError)
                and isinstance(cause, ValidationError)
            ):
                try:
                    fields = sorted(
                        {
                            str(e["loc"][0]) if e["loc"] else "argument"
                            for e in cause.errors()
                        }
                    )
                    tool = self._tool_manager.get_tool(name)
                    properties = tool.parameters.get("properties", {}) if tool else {}
                    field_name = (
                        fields[0] if fields and fields[0] in properties else "argument"
                    )
                    shape = _argument_shape(name, field_name)
                    text = (
                        f"Error executing tool {name}: Argument {field_name} {shape}."
                    )
                    logger.info("tool_call_failed reason=invalid_arguments")
                except Exception:
                    text = f"Error executing tool {name}"
                    logger.error("tool_call_failed reason=unexpected_exception")
            else:
                text = f"Error executing tool {name}"
                logger.error("tool_call_failed reason=unexpected_exception")
            return CallToolResult(
                content=[TextContent(type="text", text=text)], is_error=True
            )

    async def read_resource(self, uri, context=None):
        """Keep SDK resource wrapper exceptions and their chains out of logs/output."""
        try:
            return await super().read_resource(uri, context)
        except ResourceNotFoundError:
            raise ResourceNotFoundError("Bill4Time resource was not found.") from None
        except Exception as exc:
            cause = exc.__cause__
            if isinstance(cause, SafeToolFailure):
                raise ResourceError(str(cause)) from None
            raise ResourceError("Error reading resource") from None


def _argument_shape(tool_name: str, field_name: str) -> str:
    tool = mcp._tool_manager.get_tool(tool_name)
    prop = (tool.parameters.get("properties", {}) if tool else {}).get(field_name, {})
    expected = prop.get("type", "valid input")
    if expected == "integer":
        constraint = (
            " from 1 to 200"
            if field_name == "top"
            else " greater than or equal to 0"
            if field_name == "skip"
            else ""
        )
        return f"must be an integer{constraint}"
    if expected == "string":
        return "must be a string"
    return f"must match the expected {expected} shape"


ListLimit = Annotated[int, Field(ge=1, le=MAX_LIST_LIMIT)]
ListOffset = Annotated[int, Field(ge=0)]


def _package_version() -> str:
    return package_version("bill4time-mcp")


mcp = SafeMCPServer(
    "bill4time",
    title="Bill4Time",
    instructions=(
        "Bill4Time legal billing. Read-only access to clients, projects, time entries, "
        "expenses, invoices, payments, contacts, and trust accounting. "
        "Supports OData-style filtering on all resources."
    ),
    version=_package_version(),
)

_client: Bill4TimeClient | None = None
# requests.Session is not safe for overlapping calls. Stdio is one caller;
# stateless HTTP can overlap, so vendor calls take turns on the shared client.
_client_lock = threading.Lock()


def _c() -> Bill4TimeClient:
    """Return a cached Bill4TimeClient instance (one session, one connection pool)."""
    global _client
    with _client_lock:
        if _client is None:
            _client = Bill4TimeClient()
        return _client


def _call(fn, *args, **kwargs) -> str:
    """Invoke a client method; expected failures are safe MCP tool errors."""
    with _client_lock:
        return json.dumps(fn(*args, **kwargs), indent=2)


# ── Clients ────────────────────────────────────────────────────────────────────


@mcp.tool()
def list_clients(
    filter_expr: str = "",
    top: ListLimit = DEFAULT_LIST_LIMIT,
    skip: ListOffset = 0,
    orderby: str = DEFAULT_ORDERBY,
    select: str = "",
) -> str:
    """List clients. Use filter_expr for OData filtering, e.g. \"status eq 'Active'\"."""
    return _call(_c().list_clients, filter_expr, top, skip, orderby, select)


@mcp.tool()
def get_client(client_id: int) -> str:
    """Get a client by ID."""
    return _call(_c().get_client, client_id)


@mcp.tool()
def list_active_clients(
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all active clients."""
    return _call(_c().list_clients_by_status, "Active", top, orderby)


@mcp.tool()
def list_disabled_clients(
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all disabled clients."""
    return _call(_c().list_clients_by_status, "Disabled", top, orderby)


# ── Projects ───────────────────────────────────────────────────────────────────


@mcp.tool()
def list_projects(
    filter_expr: str = "",
    top: ListLimit = DEFAULT_LIST_LIMIT,
    skip: ListOffset = 0,
    orderby: str = DEFAULT_ORDERBY,
    select: str = "",
) -> str:
    """List projects. Use filter_expr for OData filtering, e.g. \"status eq 'Open'\"."""
    return _call(_c().list_projects, filter_expr, top, skip, orderby, select)


@mcp.tool()
def get_project(project_id: int) -> str:
    """Get a project by ID."""
    return _call(_c().get_project, project_id)


@mcp.tool()
def list_projects_for_client(
    client_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all projects for a specific client."""
    return _call(_c().list_projects_by_client, client_id, top, orderby)


@mcp.tool()
def list_open_projects(
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = "projectName asc",
) -> str:
    """List all open projects."""
    return _call(_c().list_projects_by_status, "Open", top, orderby)


@mcp.tool()
def list_closed_projects(
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all closed projects."""
    return _call(_c().list_projects_by_status, "Closed", top, orderby)


@mcp.tool()
def list_projects_by_billing_method(
    billing_method: str,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List projects by billing method. Values: Hourly, Flat Fee, Percentage."""
    return _call(_c().list_projects_by_billing_method, billing_method, top, orderby)


# ── Time Entries ───────────────────────────────────────────────────────────────


@mcp.tool()
def list_time_entries(
    filter_expr: str = "",
    top: ListLimit = DEFAULT_LIST_LIMIT,
    skip: ListOffset = 0,
    orderby: str = DEFAULT_ORDERBY,
    select: str = "",
) -> str:
    """List time entries. Use filter_expr for OData filtering."""
    return _call(_c().list_time_entries, filter_expr, top, skip, orderby, select)


@mcp.tool()
def get_time_entry(entry_id: int) -> str:
    """Get a time entry by ID."""
    return _call(_c().get_time_entry, entry_id)


@mcp.tool()
def list_time_entries_for_client(
    client_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all time entries for a specific client."""
    return _call(_c().list_time_entries_by_client, client_id, top, orderby)


@mcp.tool()
def list_time_entries_for_project(
    project_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all time entries for a specific project."""
    return _call(_c().list_time_entries_by_project, project_id, top, orderby)


@mcp.tool()
def list_time_entries_for_user(
    user_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all time entries for a specific user."""
    return _call(_c().list_time_entries_by_user, user_id, top, orderby)


@mcp.tool()
def list_time_entries_for_invoice(
    invoice_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all time entries attached to a specific invoice."""
    return _call(_c().list_time_entries_by_invoice, invoice_id, top, orderby)


@mcp.tool()
def list_time_entries_for_date_range(
    start_date: str,
    end_date: str,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List time entries within a date range (YYYY-MM-DD format)."""
    return _call(
        _c().list_time_entries_by_date_range, start_date, end_date, top, orderby
    )


@mcp.tool()
def list_time_entries_by_billing_status(
    billing_status: str,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List time entries by billing status.
    Values: Ready For Summary, Ready For Billing, Billing Complete, Pending Project Close."""
    return _call(_c().list_time_entries_by_billing_status, billing_status, top, orderby)


# ── Expenses ───────────────────────────────────────────────────────────────────


@mcp.tool()
def list_expenses(
    filter_expr: str = "",
    top: ListLimit = DEFAULT_LIST_LIMIT,
    skip: ListOffset = 0,
    orderby: str = DEFAULT_ORDERBY,
    select: str = "",
) -> str:
    """List expenses. Use filter_expr for OData filtering."""
    return _call(_c().list_expenses, filter_expr, top, skip, orderby, select)


@mcp.tool()
def get_expense(expense_id: int) -> str:
    """Get an expense by ID."""
    return _call(_c().get_expense, expense_id)


@mcp.tool()
def list_expenses_for_client(
    client_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all expenses for a specific client."""
    return _call(_c().list_expenses_by_client, client_id, top, orderby)


@mcp.tool()
def list_expenses_for_project(
    project_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all expenses for a specific project."""
    return _call(_c().list_expenses_by_project, project_id, top, orderby)


@mcp.tool()
def list_expenses_for_invoice(
    invoice_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all expenses attached to a specific invoice."""
    return _call(_c().list_expenses_by_invoice, invoice_id, top, orderby)


@mcp.tool()
def list_expenses_for_date_range(
    start_date: str,
    end_date: str,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List expenses within a date range (YYYY-MM-DD format)."""
    return _call(_c().list_expenses_by_date_range, start_date, end_date, top, orderby)


# ── Invoices ───────────────────────────────────────────────────────────────────


@mcp.tool()
def list_invoices(
    filter_expr: str = "",
    top: ListLimit = DEFAULT_LIST_LIMIT,
    skip: ListOffset = 0,
    orderby: str = DEFAULT_ORDERBY,
    select: str = "",
) -> str:
    """List invoices. Use filter_expr for OData filtering."""
    return _call(_c().list_invoices, filter_expr, top, skip, orderby, select)


@mcp.tool()
def get_invoice(invoice_id: int) -> str:
    """Get an invoice by ID."""
    return _call(_c().get_invoice, invoice_id)


@mcp.tool()
def list_invoices_for_client(
    client_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all invoices for a specific client."""
    return _call(_c().list_invoices_by_client, client_id, top, orderby)


@mcp.tool()
def list_invoices_for_project(
    project_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all invoices for a specific project."""
    return _call(_c().list_invoices_by_project, project_id, top, orderby)


@mcp.tool()
def list_prebill_invoices(
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all invoices in prebill status."""
    return _call(_c().list_invoices_by_status, "prebill", top, orderby)


@mcp.tool()
def list_finalized_invoices(
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all finalized invoices."""
    return _call(_c().list_invoices_by_status, "finalized", top, orderby)


@mcp.tool()
def list_unpaid_invoices(
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all unpaid invoices."""
    return _call(_c().list_invoices_by_paid_status, "Unpaid", top, orderby)


@mcp.tool()
def list_partially_paid_invoices(
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all partially paid invoices."""
    return _call(_c().list_invoices_by_paid_status, "Partially Paid", top, orderby)


@mcp.tool()
def list_paid_invoices(
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all fully paid invoices."""
    return _call(_c().list_invoices_by_paid_status, "Paid", top, orderby)


@mcp.tool()
def list_invoices_for_date_range(
    start_date: str,
    end_date: str,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List invoices within a date range (YYYY-MM-DD format)."""
    return _call(_c().list_invoices_by_date_range, start_date, end_date, top, orderby)


# ── Payments ───────────────────────────────────────────────────────────────────


@mcp.tool()
def list_payments(
    filter_expr: str = "",
    top: ListLimit = DEFAULT_LIST_LIMIT,
    skip: ListOffset = 0,
    orderby: str = DEFAULT_ORDERBY,
    select: str = "",
) -> str:
    """List payments. Use filter_expr for OData filtering."""
    return _call(_c().list_payments, filter_expr, top, skip, orderby, select)


@mcp.tool()
def get_payment(payment_id: int) -> str:
    """Get a payment by ID."""
    return _call(_c().get_payment, payment_id)


@mcp.tool()
def list_payments_for_client(
    client_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all payments for a specific client."""
    return _call(_c().list_payments_by_client, client_id, top, orderby)


@mcp.tool()
def list_payments_for_project(
    project_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all payments for a specific project."""
    return _call(_c().list_payments_by_project, project_id, top, orderby)


@mcp.tool()
def list_payments_for_date_range(
    start_date: str,
    end_date: str,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List payments within a date range (YYYY-MM-DD format)."""
    return _call(_c().list_payments_by_date_range, start_date, end_date, top, orderby)


# ── Payments Applied ───────────────────────────────────────────────────────────


@mcp.tool()
def list_payments_applied(
    filter_expr: str = "",
    top: ListLimit = DEFAULT_LIST_LIMIT,
    skip: ListOffset = 0,
    orderby: str = DEFAULT_ORDERBY,
    select: str = "",
) -> str:
    """List payments-applied records. Use filter_expr for OData filtering."""
    return _call(_c().list_payments_applied, filter_expr, top, skip, orderby, select)


@mcp.tool()
def get_payment_applied(record_id: int) -> str:
    """Get a payments-applied record by ID."""
    return _call(_c().get_payment_applied, record_id)


@mcp.tool()
def list_payments_applied_for_invoice(
    invoice_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all payment applications for a specific invoice."""
    return _call(_c().list_payments_applied_by_invoice, invoice_id, top, orderby)


@mcp.tool()
def list_payments_applied_for_payment(
    payment_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all invoice applications for a specific payment."""
    return _call(_c().list_payments_applied_by_payment, payment_id, top, orderby)


@mcp.tool()
def list_payments_applied_for_date_range(
    start_date: str,
    end_date: str,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List payments-applied within a date range (YYYY-MM-DD format)."""
    return _call(
        _c().list_payments_applied_by_date_range,
        start_date,
        end_date,
        top,
        orderby,
    )


# ── Users ──────────────────────────────────────────────────────────────────────


@mcp.tool()
def list_users(
    filter_expr: str = "",
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List users. Use filter_expr for OData filtering."""
    return _call(_c().list_users, filter_expr, top, orderby)


@mcp.tool()
def get_user(user_id: int) -> str:
    """Get a user by ID."""
    return _call(_c().get_user, user_id)


# ── Contacts ───────────────────────────────────────────────────────────────────


@mcp.tool()
def list_contacts(
    filter_expr: str = "",
    top: ListLimit = DEFAULT_LIST_LIMIT,
    skip: ListOffset = 0,
    orderby: str = DEFAULT_ORDERBY,
    select: str = "",
) -> str:
    """List contacts. Use filter_expr for OData filtering."""
    return _call(_c().list_contacts, filter_expr, top, skip, orderby, select)


@mcp.tool()
def get_contact(contact_id: int) -> str:
    """Get a contact by ID."""
    return _call(_c().get_contact, contact_id)


@mcp.tool()
def list_active_contacts(
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all active contacts."""
    return _call(_c().list_contacts_by_status, "Active", top, orderby)


@mcp.tool()
def list_contacts_for_date_range(
    start_date: str,
    end_date: str,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List contacts created within a date range (YYYY-MM-DD format)."""
    return _call(_c().list_contacts_by_date_range, start_date, end_date, top, orderby)


# ── Contact Connections ────────────────────────────────────────────────────────


@mcp.tool()
def list_contact_connections(
    filter_expr: str = "",
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all contact connections. Use filter_expr for OData filtering."""
    return _call(_c().list_contact_connections, filter_expr, top, orderby)


@mcp.tool()
def list_contact_connections_for_contact(
    contact_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all client/project connections for a specific contact."""
    return _call(_c().list_contact_connections_by_contact, contact_id, top, orderby)


@mcp.tool()
def list_contact_connections_for_client(
    client_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all contact connections for a specific client."""
    return _call(_c().list_contact_connections_by_client, client_id, top, orderby)


@mcp.tool()
def list_contact_connections_for_project(
    project_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all contact connections for a specific project."""
    return _call(_c().list_contact_connections_by_project, project_id, top, orderby)


# ── Trust Accounting ───────────────────────────────────────────────────────────


@mcp.tool()
def list_trust_records(
    filter_expr: str = "",
    top: ListLimit = DEFAULT_LIST_LIMIT,
    skip: ListOffset = 0,
    orderby: str = DEFAULT_ORDERBY,
    select: str = "",
) -> str:
    """List trust accounting records. Use filter_expr for OData filtering."""
    return _call(_c().list_trust_records, filter_expr, top, skip, orderby, select)


@mcp.tool()
def get_trust_record(record_id: int) -> str:
    """Get a trust accounting record by ID."""
    return _call(_c().get_trust_record, record_id)


@mcp.tool()
def list_trust_records_for_client(
    client_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all trust accounting records for a specific client."""
    return _call(_c().list_trust_records_by_client, client_id, top, orderby)


@mcp.tool()
def list_trust_records_for_project(
    project_id: int,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List all trust accounting records for a specific project."""
    return _call(_c().list_trust_records_by_project, project_id, top, orderby)


@mcp.tool()
def list_trust_records_for_date_range(
    start_date: str,
    end_date: str,
    top: ListLimit = DEFAULT_LIST_LIMIT,
    orderby: str = DEFAULT_ORDERBY,
) -> str:
    """List trust records created within a date range (YYYY-MM-DD format)."""
    return _call(
        _c().list_trust_records_by_date_range, start_date, end_date, top, orderby
    )


# ── Resources ─────────────────────────────────────────────────────────────────


@mcp.resource("bill4time://active_clients", mime_type="application/json")
def active_clients_resource() -> str:
    """Active clients from Bill4Time — read-only reference data."""
    return _call(_c().list_clients_by_status, "Active", 50)


@mcp.resource("bill4time://users", mime_type="application/json")
def users_resource() -> str:
    """Bill4Time users (timekeeper list) — read-only reference data."""
    return _call(_c().list_users, "", 50)


@mcp.resource("bill4time://security-notes", mime_type="text/markdown")
def security_notes_resource() -> str:
    """Security posture documentation for this Bill4Time MCP server."""
    return """\
# Bill4Time MCP — Security Notes

## API key in URL path (vendor design)

The Bill4Time REST API embeds the API key directly in the URL path:
`https://secure.bill4time.com/b4t-api/{API_KEY}/v1/...`

This is a vendor design decision, not a configurable option. Consequences:

- **Any proxy, log aggregator, load balancer, or HTTP access log** that records
  full request URLs will capture the API key in plaintext.
- **HTTPS mitigates passive eavesdropping** — the URL path is encrypted in transit
  — but does not protect against log exposure at the origin or proxy layer.

**Operational guidance:**
- Ensure that web server access logs, reverse-proxy logs (nginx, Cloudflare, etc.),
  and any observability pipeline (Datadog, Splunk, etc.) either redact URL paths
  or are access-controlled to the same degree as the key itself.
- Rotate the API key if you suspect it has been captured in logs accessible to
  unauthorized parties.
- This MCP does not log request URLs. The `BILL4TIME_API_KEY` env var is resolved
  at startup via the pluggable credentials store (OS keyring -> `.env`) and embedded
  in `self._api_url` on the client instance; it is never written to stdout/stderr.

## Read-only access

All tools in this MCP are read-only (GET requests only). There are no write,
create, or delete operations. The blast radius of a compromised API key is
limited to data exposure, not data modification.

## Authentication

`BILL4TIME_API_KEY` is loaded via the pluggable credentials store. It is never
logged or echoed by this server.
"""


# ── Prompts ───────────────────────────────────────────────────────────────────


@mcp.prompt()
def unbilled_time_report(start_date: str, end_date: str) -> str:
    """Report on unbilled time entries for a date range — billing status review workflow."""
    return f"""Generate an unbilled time report for {start_date} to {end_date}.

1. Call list_time_entries_for_date_range('{start_date}', '{end_date}').
2. Filter results to entries where billingStatus is 'Ready For Summary' or 'Ready For Billing'.
3. Group by client/project:
   - Client name
   - Project name
   - Total hours unbilled
   - Attorney/user responsible (userId)
4. Sort by total unbilled hours descending.
5. Flag any entry where billingStatus is 'Pending Project Close' — these may be at risk of not being billed.
6. Summary row: total unbilled hours, estimated revenue (if rates available), date range covered.
7. Recommend which clients to invoice first based on unbilled hours and project status."""


@mcp.prompt()
def client_billing_summary(client_id: int) -> str:
    """Full billing picture for a single client: projects, time, invoices, payments."""
    return f"""Build a billing summary for client ID {client_id}.

1. get_client({client_id}) — confirm client name and status.
2. list_projects_for_client({client_id}) — list all matters/projects.
3. list_time_entries_for_client({client_id}) — total hours by project.
4. list_invoices_for_client({client_id}) — outstanding invoice amounts and paid status.
5. list_payments_for_client({client_id}) — payments received.
6. Compute: total billed, total paid, outstanding balance.
7. For each project: hours logged, billed, unbilled.
8. Flag: unpaid invoices older than 30 days, open projects with no recent time entries."""


@mcp.prompt()
def trust_account_review(client_id: int) -> str:
    """Review trust accounting records for a client — compliance-oriented workflow."""
    return f"""Review trust account for client ID {client_id}.

1. list_trust_records_for_client({client_id}) — all trust transactions.
2. Separate deposits from disbursements (check transaction type field).
3. Compute running balance chronologically.
4. Flag:
   - Any disbursement that would overdraw the trust account.
   - Trust balance below $0 at any point.
   - Large disbursements without a corresponding invoice.
5. Cross-reference with list_invoices_for_client({client_id}) to confirm disbursements match billed work.
6. Output: transaction log table, current trust balance, any compliance flags."""


def _requested_transport() -> str:
    return os.environ.get("BILL4TIME_MCP_TRANSPORT", "stdio").strip().lower() or "stdio"


def _host() -> str:
    return os.environ.get("BILL4TIME_MCP_HOST", "127.0.0.1").strip() or "127.0.0.1"


def _port() -> int:
    raw = os.environ.get("PORT", "8080").strip()
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"PORT must be an integer, got {raw!r}") from None


def _csv_env(name: str) -> list[str]:
    return [
        item.strip() for item in os.environ.get(name, "").split(",") if item.strip()
    ]


def _transport_security() -> TransportSecuritySettings | None:
    host = _host()
    if host in _LOOPBACK_HOSTS:
        return None
    allowed_hosts = _csv_env("BILL4TIME_MCP_ALLOWED_HOSTS")
    if not allowed_hosts:
        raise SystemExit(
            "BILL4TIME_MCP_ALLOWED_HOSTS is required when BILL4TIME_MCP_HOST "
            f"is {host!r} (not a loopback address)."
        )
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=_csv_env("BILL4TIME_MCP_ALLOWED_ORIGINS"),
    )


def create_serve_app() -> Starlette:
    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        host=_host(),
        stateless_http=True,
        transport_security=_transport_security(),
    )


async def _serve_streamable_http() -> None:
    import uvicorn

    config = uvicorn.Config(
        create_serve_app(),
        host=_host(),
        port=_port(),
        log_level=mcp.settings.log_level.lower(),
        access_log=False,
    )
    await uvicorn.Server(config).serve()


def main():
    transport = _requested_transport()
    if transport == "stdio":
        mcp.run()
        return
    if transport == STREAMABLE_HTTP_TRANSPORT:
        asyncio.run(_serve_streamable_http())
        return
    raise SystemExit(
        "Unsupported BILL4TIME_MCP_TRANSPORT "
        f"{transport!r}; expected 'stdio' or '{STREAMABLE_HTTP_TRANSPORT}'."
    )


if __name__ == "__main__":
    main()
