#!/usr/bin/env python3
"""Bill4Time MCP server — FastMCP tools for the Bill4Time API."""

import json
from mcp.server.fastmcp import FastMCP
from bill4time_mcp.client import Bill4TimeClient

mcp = FastMCP(
    "bill4time",
    instructions=(
        "Bill4Time legal billing. Read-only access to clients, projects, time entries, "
        "expenses, invoices, payments, contacts, and trust accounting. "
        "Supports OData-style filtering on all resources."
    ),
)


def _c():
    return Bill4TimeClient()


# ── Clients ────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_clients(
    filter_expr: str = "",
    top: int = 0,
    skip: int = 0,
    orderby: str = "",
    select: str = "",
) -> str:
    """List clients. Use filter_expr for OData filtering, e.g. \"status eq 'Active'\"."""
    return json.dumps(_c().list_clients(filter_expr, top, skip, orderby, select), indent=2)


@mcp.tool()
def get_client(client_id: int) -> str:
    """Get a client by ID."""
    return json.dumps(_c().get_client(client_id), indent=2)


@mcp.tool()
def list_active_clients(top: int = 0, orderby: str = "") -> str:
    """List all active clients."""
    return json.dumps(_c().list_clients_by_status("Active", top, orderby), indent=2)


@mcp.tool()
def list_disabled_clients(top: int = 0) -> str:
    """List all disabled clients."""
    return json.dumps(_c().list_clients_by_status("Disabled", top), indent=2)


# ── Projects ───────────────────────────────────────────────────────────────────

@mcp.tool()
def list_projects(
    filter_expr: str = "",
    top: int = 0,
    skip: int = 0,
    orderby: str = "",
    select: str = "",
) -> str:
    """List projects. Use filter_expr for OData filtering, e.g. \"status eq 'Open'\"."""
    return json.dumps(_c().list_projects(filter_expr, top, skip, orderby, select), indent=2)


@mcp.tool()
def get_project(project_id: int) -> str:
    """Get a project by ID."""
    return json.dumps(_c().get_project(project_id), indent=2)


@mcp.tool()
def list_projects_for_client(client_id: int, top: int = 0) -> str:
    """List all projects for a specific client."""
    return json.dumps(_c().list_projects_by_client(client_id, top), indent=2)


@mcp.tool()
def list_open_projects(top: int = 0, orderby: str = "projectName") -> str:
    """List all open projects."""
    return json.dumps(_c().list_projects_by_status("Open", top, orderby), indent=2)


@mcp.tool()
def list_closed_projects(top: int = 0, orderby: str = "") -> str:
    """List all closed projects."""
    return json.dumps(_c().list_projects_by_status("Closed", top, orderby), indent=2)


@mcp.tool()
def list_projects_by_billing_method(billing_method: str, top: int = 0) -> str:
    """List projects by billing method. Values: Hourly, Flat Fee, Percentage."""
    return json.dumps(_c().list_projects_by_billing_method(billing_method, top), indent=2)


# ── Time Entries ───────────────────────────────────────────────────────────────

@mcp.tool()
def list_time_entries(
    filter_expr: str = "",
    top: int = 0,
    skip: int = 0,
    orderby: str = "",
    select: str = "",
) -> str:
    """List time entries. Use filter_expr for OData filtering."""
    return json.dumps(_c().list_time_entries(filter_expr, top, skip, orderby, select), indent=2)


@mcp.tool()
def get_time_entry(entry_id: int) -> str:
    """Get a time entry by ID."""
    return json.dumps(_c().get_time_entry(entry_id), indent=2)


@mcp.tool()
def list_time_entries_for_client(client_id: int, top: int = 0) -> str:
    """List all time entries for a specific client."""
    return json.dumps(_c().list_time_entries_by_client(client_id, top), indent=2)


@mcp.tool()
def list_time_entries_for_project(project_id: int, top: int = 0) -> str:
    """List all time entries for a specific project."""
    return json.dumps(_c().list_time_entries_by_project(project_id, top), indent=2)


@mcp.tool()
def list_time_entries_for_user(user_id: int, top: int = 0) -> str:
    """List all time entries for a specific user."""
    return json.dumps(_c().list_time_entries_by_user(user_id, top), indent=2)


@mcp.tool()
def list_time_entries_for_invoice(invoice_id: int) -> str:
    """List all time entries attached to a specific invoice."""
    return json.dumps(_c().list_time_entries_by_invoice(invoice_id), indent=2)


@mcp.tool()
def list_time_entries_for_date_range(start_date: str, end_date: str, top: int = 0) -> str:
    """List time entries within a date range (YYYY-MM-DD format)."""
    return json.dumps(_c().list_time_entries_by_date_range(start_date, end_date, top), indent=2)


@mcp.tool()
def list_time_entries_by_billing_status(billing_status: str, top: int = 0) -> str:
    """List time entries by billing status.
    Values: Ready For Summary, Ready For Billing, Billing Complete, Pending Project Close."""
    return json.dumps(_c().list_time_entries_by_billing_status(billing_status, top), indent=2)


# ── Expenses ───────────────────────────────────────────────────────────────────

@mcp.tool()
def list_expenses(
    filter_expr: str = "",
    top: int = 0,
    skip: int = 0,
    orderby: str = "",
    select: str = "",
) -> str:
    """List expenses. Use filter_expr for OData filtering."""
    return json.dumps(_c().list_expenses(filter_expr, top, skip, orderby, select), indent=2)


@mcp.tool()
def get_expense(expense_id: int) -> str:
    """Get an expense by ID."""
    return json.dumps(_c().get_expense(expense_id), indent=2)


@mcp.tool()
def list_expenses_for_client(client_id: int, top: int = 0) -> str:
    """List all expenses for a specific client."""
    return json.dumps(_c().list_expenses_by_client(client_id, top), indent=2)


@mcp.tool()
def list_expenses_for_project(project_id: int, top: int = 0) -> str:
    """List all expenses for a specific project."""
    return json.dumps(_c().list_expenses_by_project(project_id, top), indent=2)


@mcp.tool()
def list_expenses_for_invoice(invoice_id: int) -> str:
    """List all expenses attached to a specific invoice."""
    return json.dumps(_c().list_expenses_by_invoice(invoice_id), indent=2)


@mcp.tool()
def list_expenses_for_date_range(start_date: str, end_date: str, top: int = 0) -> str:
    """List expenses within a date range (YYYY-MM-DD format)."""
    return json.dumps(_c().list_expenses_by_date_range(start_date, end_date, top), indent=2)


# ── Invoices ───────────────────────────────────────────────────────────────────

@mcp.tool()
def list_invoices(
    filter_expr: str = "",
    top: int = 0,
    skip: int = 0,
    orderby: str = "",
    select: str = "",
) -> str:
    """List invoices. Use filter_expr for OData filtering."""
    return json.dumps(_c().list_invoices(filter_expr, top, skip, orderby, select), indent=2)


@mcp.tool()
def get_invoice(invoice_id: int) -> str:
    """Get an invoice by ID."""
    return json.dumps(_c().get_invoice(invoice_id), indent=2)


@mcp.tool()
def list_invoices_for_client(client_id: int, top: int = 0) -> str:
    """List all invoices for a specific client."""
    return json.dumps(_c().list_invoices_by_client(client_id, top), indent=2)


@mcp.tool()
def list_invoices_for_project(project_id: int, top: int = 0) -> str:
    """List all invoices for a specific project."""
    return json.dumps(_c().list_invoices_by_project(project_id, top), indent=2)


@mcp.tool()
def list_prebill_invoices(top: int = 0) -> str:
    """List all invoices in prebill status."""
    return json.dumps(_c().list_invoices_by_status("prebill", top), indent=2)


@mcp.tool()
def list_finalized_invoices(top: int = 0) -> str:
    """List all finalized invoices."""
    return json.dumps(_c().list_invoices_by_status("finalized", top), indent=2)


@mcp.tool()
def list_unpaid_invoices(top: int = 0) -> str:
    """List all unpaid invoices."""
    return json.dumps(_c().list_invoices_by_paid_status("Unpaid", top), indent=2)


@mcp.tool()
def list_partially_paid_invoices(top: int = 0) -> str:
    """List all partially paid invoices."""
    return json.dumps(_c().list_invoices_by_paid_status("Partially Paid", top), indent=2)


@mcp.tool()
def list_paid_invoices(top: int = 0) -> str:
    """List all fully paid invoices."""
    return json.dumps(_c().list_invoices_by_paid_status("Paid", top), indent=2)


@mcp.tool()
def list_invoices_for_date_range(start_date: str, end_date: str, top: int = 0) -> str:
    """List invoices within a date range (YYYY-MM-DD format)."""
    return json.dumps(_c().list_invoices_by_date_range(start_date, end_date, top), indent=2)


# ── Payments ───────────────────────────────────────────────────────────────────

@mcp.tool()
def list_payments(
    filter_expr: str = "",
    top: int = 0,
    skip: int = 0,
    orderby: str = "",
    select: str = "",
) -> str:
    """List payments. Use filter_expr for OData filtering."""
    return json.dumps(_c().list_payments(filter_expr, top, skip, orderby, select), indent=2)


@mcp.tool()
def get_payment(payment_id: int) -> str:
    """Get a payment by ID."""
    return json.dumps(_c().get_payment(payment_id), indent=2)


@mcp.tool()
def list_payments_for_client(client_id: int, top: int = 0) -> str:
    """List all payments for a specific client."""
    return json.dumps(_c().list_payments_by_client(client_id, top), indent=2)


@mcp.tool()
def list_payments_for_project(project_id: int, top: int = 0) -> str:
    """List all payments for a specific project."""
    return json.dumps(_c().list_payments_by_project(project_id, top), indent=2)


@mcp.tool()
def list_payments_for_date_range(start_date: str, end_date: str, top: int = 0) -> str:
    """List payments within a date range (YYYY-MM-DD format)."""
    return json.dumps(_c().list_payments_by_date_range(start_date, end_date, top), indent=2)


# ── Payments Applied ───────────────────────────────────────────────────────────

@mcp.tool()
def list_payments_applied(
    filter_expr: str = "",
    top: int = 0,
    skip: int = 0,
    orderby: str = "",
    select: str = "",
) -> str:
    """List payments-applied records. Use filter_expr for OData filtering."""
    return json.dumps(_c().list_payments_applied(filter_expr, top, skip, orderby, select), indent=2)


@mcp.tool()
def get_payment_applied(record_id: int) -> str:
    """Get a payments-applied record by ID."""
    return json.dumps(_c().get_payment_applied(record_id), indent=2)


@mcp.tool()
def list_payments_applied_for_invoice(invoice_id: int) -> str:
    """List all payment applications for a specific invoice."""
    return json.dumps(_c().list_payments_applied_by_invoice(invoice_id), indent=2)


@mcp.tool()
def list_payments_applied_for_payment(payment_id: int) -> str:
    """List all invoice applications for a specific payment."""
    return json.dumps(_c().list_payments_applied_by_payment(payment_id), indent=2)


@mcp.tool()
def list_payments_applied_for_date_range(start_date: str, end_date: str, top: int = 0) -> str:
    """List payments-applied within a date range (YYYY-MM-DD format)."""
    return json.dumps(_c().list_payments_applied_by_date_range(start_date, end_date, top), indent=2)


# ── Users ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_users(filter_expr: str = "", top: int = 0) -> str:
    """List users. Use filter_expr for OData filtering."""
    return json.dumps(_c().list_users(filter_expr, top), indent=2)


@mcp.tool()
def get_user(user_id: int) -> str:
    """Get a user by ID."""
    return json.dumps(_c().get_user(user_id), indent=2)


# ── Contacts ───────────────────────────────────────────────────────────────────

@mcp.tool()
def list_contacts(
    filter_expr: str = "",
    top: int = 0,
    skip: int = 0,
    orderby: str = "",
    select: str = "",
) -> str:
    """List contacts. Use filter_expr for OData filtering."""
    return json.dumps(_c().list_contacts(filter_expr, top, skip, orderby, select), indent=2)


@mcp.tool()
def get_contact(contact_id: int) -> str:
    """Get a contact by ID."""
    return json.dumps(_c().get_contact(contact_id), indent=2)


@mcp.tool()
def list_active_contacts(top: int = 0) -> str:
    """List all active contacts."""
    return json.dumps(_c().list_contacts_by_status("Active", top), indent=2)


@mcp.tool()
def list_contacts_for_date_range(start_date: str, end_date: str, top: int = 0) -> str:
    """List contacts created within a date range (YYYY-MM-DD format)."""
    return json.dumps(_c().list_contacts_by_date_range(start_date, end_date, top), indent=2)


# ── Contact Connections ────────────────────────────────────────────────────────

@mcp.tool()
def list_contact_connections(filter_expr: str = "", top: int = 0) -> str:
    """List all contact connections. Use filter_expr for OData filtering."""
    return json.dumps(_c().list_contact_connections(filter_expr, top), indent=2)


@mcp.tool()
def list_contact_connections_for_contact(contact_id: int) -> str:
    """List all client/project connections for a specific contact."""
    return json.dumps(_c().list_contact_connections_by_contact(contact_id), indent=2)


@mcp.tool()
def list_contact_connections_for_client(client_id: int) -> str:
    """List all contact connections for a specific client."""
    return json.dumps(_c().list_contact_connections_by_client(client_id), indent=2)


@mcp.tool()
def list_contact_connections_for_project(project_id: int) -> str:
    """List all contact connections for a specific project."""
    return json.dumps(_c().list_contact_connections_by_project(project_id), indent=2)


# ── Trust Accounting ───────────────────────────────────────────────────────────

@mcp.tool()
def list_trust_records(
    filter_expr: str = "",
    top: int = 0,
    skip: int = 0,
    orderby: str = "",
    select: str = "",
) -> str:
    """List trust accounting records. Use filter_expr for OData filtering."""
    return json.dumps(_c().list_trust_records(filter_expr, top, skip, orderby, select), indent=2)


@mcp.tool()
def get_trust_record(record_id: int) -> str:
    """Get a trust accounting record by ID."""
    return json.dumps(_c().get_trust_record(record_id), indent=2)


@mcp.tool()
def list_trust_records_for_client(client_id: int, top: int = 0) -> str:
    """List all trust accounting records for a specific client."""
    return json.dumps(_c().list_trust_records_by_client(client_id, top), indent=2)


@mcp.tool()
def list_trust_records_for_project(project_id: int, top: int = 0) -> str:
    """List all trust accounting records for a specific project."""
    return json.dumps(_c().list_trust_records_by_project(project_id, top), indent=2)


@mcp.tool()
def list_trust_records_for_date_range(start_date: str, end_date: str, top: int = 0) -> str:
    """List trust records created within a date range (YYYY-MM-DD format)."""
    return json.dumps(_c().list_trust_records_by_date_range(start_date, end_date, top), indent=2)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
