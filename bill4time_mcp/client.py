#!/usr/bin/env python3
"""Bill4Time API client. API key embedded in URL path. Read-only OData API."""

import os
import sys
import time
import requests
from datetime import date
from pathlib import Path

CONFIG_DIR = Path.home() / ".bill4time-mcp"
BASE = "https://secure.bill4time.com/b4t-api"


def _load_env():
    env_file = CONFIG_DIR / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip())


_load_env()

API_KEY = os.environ.get("BILL4TIME_API_KEY", "")


class Bill4TimeClient:
    def __init__(self):
        if not API_KEY:
            raise RuntimeError("BILL4TIME_API_KEY not set. Run bill4time-mcp-setup.")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self._api_url = f"{BASE}/{API_KEY}/v1"

    def _get(self, resource: str, params: dict = None):
        url = f"{self._api_url}/{resource}"
        for attempt in range(3):
            resp = self.session.get(url, params=params)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 10))
                print(f"Rate limited. Waiting {retry_after}s...", file=sys.stderr)
                time.sleep(retry_after)
                continue
            if not resp.ok:
                raise RuntimeError(f"Bill4Time API error {resp.status_code}: {resp.text[:400]}")
            return resp.json()
        raise RuntimeError("Max retries exceeded")

    def _build_params(self, filter_expr: str = "", top: int = 0, skip: int = 0,
                      orderby: str = "", select: str = "", count: bool = False) -> dict:
        params = {}
        if filter_expr:
            params["$filter"] = filter_expr
        if top:
            params["$top"] = top
        if skip:
            params["$skip"] = skip
        if orderby:
            params["$orderby"] = orderby
        if select:
            params["$select"] = select
        if count:
            params["$count"] = "true"
        return params

    @staticmethod
    def _odata_str(value: str) -> str:
        """Escape a string value for safe embedding in an OData filter expression."""
        return "'" + value.replace("'", "''") + "'"

    @staticmethod
    def _parse_date(value: str) -> str:
        """Validate and normalise an ISO-8601 date string (YYYY-MM-DD).
        Raises ValueError if the format is invalid."""
        return date.fromisoformat(value).isoformat()

    # ── Clients ───────────────────────────────────────────────────────────────

    def list_clients(self, filter_expr: str = "", top: int = 0, skip: int = 0,
                     orderby: str = "", select: str = ""):
        return self._get("clients", self._build_params(filter_expr, top, skip, orderby, select))

    def get_client(self, client_id: int):
        return self._get("clients", {"$filter": f"id eq {client_id}"})

    def list_clients_by_status(self, status: str, top: int = 0, orderby: str = ""):
        return self._get("clients", self._build_params(
            f"status eq {self._odata_str(status)}", top, orderby=orderby))

    # ── Projects ──────────────────────────────────────────────────────────────

    def list_projects(self, filter_expr: str = "", top: int = 0, skip: int = 0,
                      orderby: str = "", select: str = ""):
        return self._get("projects", self._build_params(filter_expr, top, skip, orderby, select))

    def get_project(self, project_id: int):
        return self._get("projects", {"$filter": f"id eq {project_id}"})

    def list_projects_by_client(self, client_id: int, top: int = 0):
        return self._get("projects", self._build_params(f"clientId eq {client_id}", top))

    def list_projects_by_status(self, status: str, top: int = 0, orderby: str = ""):
        return self._get("projects", self._build_params(
            f"status eq {self._odata_str(status)}", top, orderby=orderby))

    def list_projects_by_billing_method(self, billing_method: str, top: int = 0):
        return self._get("projects", self._build_params(
            f"billingMethod eq {self._odata_str(billing_method)}", top))

    # ── Time Entries ──────────────────────────────────────────────────────────

    def list_time_entries(self, filter_expr: str = "", top: int = 0, skip: int = 0,
                          orderby: str = "", select: str = ""):
        return self._get("timeEntries", self._build_params(filter_expr, top, skip, orderby, select))

    def get_time_entry(self, entry_id: int):
        return self._get("timeEntries", {"$filter": f"id eq {entry_id}"})

    def list_time_entries_by_client(self, client_id: int, top: int = 0):
        return self._get("timeEntries", self._build_params(f"clientId eq {client_id}", top))

    def list_time_entries_by_project(self, project_id: int, top: int = 0):
        return self._get("timeEntries", self._build_params(f"projectId eq {project_id}", top))

    def list_time_entries_by_user(self, user_id: int, top: int = 0):
        return self._get("timeEntries", self._build_params(f"userId eq {user_id}", top))

    def list_time_entries_by_invoice(self, invoice_id: int):
        return self._get("timeEntries", {"$filter": f"invoiceId eq {invoice_id}"})

    def list_time_entries_by_date_range(self, start_date: str, end_date: str, top: int = 0):
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        return self._get("timeEntries", self._build_params(
            f"entryDate ge '{start}' AND entryDate le '{end}'", top))

    def list_time_entries_by_billing_status(self, billing_status: str, top: int = 0):
        return self._get("timeEntries", self._build_params(
            f"billingStatus eq {self._odata_str(billing_status)}", top))

    # ── Expenses ──────────────────────────────────────────────────────────────

    def list_expenses(self, filter_expr: str = "", top: int = 0, skip: int = 0,
                      orderby: str = "", select: str = ""):
        return self._get("expenses", self._build_params(filter_expr, top, skip, orderby, select))

    def get_expense(self, expense_id: int):
        return self._get("expenses", {"$filter": f"id eq {expense_id}"})

    def list_expenses_by_client(self, client_id: int, top: int = 0):
        return self._get("expenses", self._build_params(f"clientId eq {client_id}", top))

    def list_expenses_by_project(self, project_id: int, top: int = 0):
        return self._get("expenses", self._build_params(f"projectId eq {project_id}", top))

    def list_expenses_by_invoice(self, invoice_id: int):
        return self._get("expenses", {"$filter": f"invoiceId eq {invoice_id}"})

    def list_expenses_by_date_range(self, start_date: str, end_date: str, top: int = 0):
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        return self._get("expenses", self._build_params(
            f"expenseDate ge '{start}' AND expenseDate le '{end}'", top))

    # ── Invoices ──────────────────────────────────────────────────────────────

    def list_invoices(self, filter_expr: str = "", top: int = 0, skip: int = 0,
                      orderby: str = "", select: str = ""):
        return self._get("invoices", self._build_params(filter_expr, top, skip, orderby, select))

    def get_invoice(self, invoice_id: int):
        return self._get("invoices", {"$filter": f"id eq {invoice_id}"})

    def list_invoices_by_client(self, client_id: int, top: int = 0):
        return self._get("invoices", self._build_params(f"clientId eq {client_id}", top))

    def list_invoices_by_project(self, project_id: int, top: int = 0):
        return self._get("invoices", self._build_params(f"projectId eq {project_id}", top))

    def list_invoices_by_status(self, status: str, top: int = 0):
        return self._get("invoices", self._build_params(
            f"status eq {self._odata_str(status)}", top))

    def list_invoices_by_paid_status(self, paid_status: str, top: int = 0):
        return self._get("invoices", self._build_params(
            f"paidStatus eq {self._odata_str(paid_status)}", top))

    def list_invoices_by_date_range(self, start_date: str, end_date: str, top: int = 0):
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        return self._get("invoices", self._build_params(
            f"invoiceDate ge '{start}' AND invoiceDate le '{end}'", top))

    # ── Payments ──────────────────────────────────────────────────────────────

    def list_payments(self, filter_expr: str = "", top: int = 0, skip: int = 0,
                      orderby: str = "", select: str = ""):
        return self._get("payments", self._build_params(filter_expr, top, skip, orderby, select))

    def get_payment(self, payment_id: int):
        return self._get("payments", {"$filter": f"id eq {payment_id}"})

    def list_payments_by_client(self, client_id: int, top: int = 0):
        return self._get("payments", self._build_params(f"clientId eq {client_id}", top))

    def list_payments_by_project(self, project_id: int, top: int = 0):
        return self._get("payments", self._build_params(f"projectId eq {project_id}", top))

    def list_payments_by_date_range(self, start_date: str, end_date: str, top: int = 0):
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        return self._get("payments", self._build_params(
            f"paymentDate ge '{start}' AND paymentDate le '{end}'", top))

    # ── Payments Applied ──────────────────────────────────────────────────────

    def list_payments_applied(self, filter_expr: str = "", top: int = 0, skip: int = 0,
                              orderby: str = "", select: str = ""):
        return self._get("paymentsApplied", self._build_params(
            filter_expr, top, skip, orderby, select))

    def get_payment_applied(self, record_id: int):
        return self._get("paymentsApplied", {"$filter": f"id eq {record_id}"})

    def list_payments_applied_by_invoice(self, invoice_id: int):
        return self._get("paymentsApplied", {"$filter": f"invoiceId eq {invoice_id}"})

    def list_payments_applied_by_payment(self, payment_id: int):
        return self._get("paymentsApplied", {"$filter": f"paymentId eq {payment_id}"})

    def list_payments_applied_by_date_range(self, start_date: str, end_date: str, top: int = 0):
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        return self._get("paymentsApplied", self._build_params(
            f"dateApplied ge '{start}' AND dateApplied le '{end}'", top))

    # ── Users ─────────────────────────────────────────────────────────────────

    def list_users(self, filter_expr: str = "", top: int = 0):
        return self._get("users", self._build_params(filter_expr, top))

    def get_user(self, user_id: int):
        return self._get("users", {"$filter": f"id eq {user_id}"})

    # ── Contacts ──────────────────────────────────────────────────────────────

    def list_contacts(self, filter_expr: str = "", top: int = 0, skip: int = 0,
                      orderby: str = "", select: str = ""):
        return self._get("contacts", self._build_params(filter_expr, top, skip, orderby, select))

    def get_contact(self, contact_id: int):
        return self._get("contacts", {"$filter": f"id eq {contact_id}"})

    def list_contacts_by_status(self, status: str, top: int = 0):
        return self._get("contacts", self._build_params(
            f"status eq {self._odata_str(status)}", top))

    def list_contacts_by_date_range(self, start_date: str, end_date: str, top: int = 0):
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        return self._get("contacts", self._build_params(
            f"creationDate ge '{start}' AND creationDate le '{end}'", top))

    # ── Contact Connections ───────────────────────────────────────────────────

    def list_contact_connections(self, filter_expr: str = "", top: int = 0):
        return self._get("contactConnections", self._build_params(filter_expr, top))

    def list_contact_connections_by_contact(self, contact_id: int):
        return self._get("contactConnections", {"$filter": f"contactId eq {contact_id}"})

    def list_contact_connections_by_client(self, client_id: int):
        return self._get("contactConnections", {"$filter": f"clientId eq {client_id}"})

    def list_contact_connections_by_project(self, project_id: int):
        return self._get("contactConnections", {"$filter": f"projectId eq {project_id}"})

    # ── Trust Accounting ──────────────────────────────────────────────────────

    def list_trust_records(self, filter_expr: str = "", top: int = 0, skip: int = 0,
                           orderby: str = "", select: str = ""):
        return self._get("trustAccounting", self._build_params(
            filter_expr, top, skip, orderby, select))

    def get_trust_record(self, record_id: int):
        return self._get("trustAccounting", {"$filter": f"id eq {record_id}"})

    def list_trust_records_by_client(self, client_id: int, top: int = 0):
        return self._get("trustAccounting", self._build_params(f"clientId eq {client_id}", top))

    def list_trust_records_by_project(self, project_id: int, top: int = 0):
        return self._get("trustAccounting", self._build_params(f"projectId eq {project_id}", top))

    def list_trust_records_by_date_range(self, start_date: str, end_date: str, top: int = 0):
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        return self._get("trustAccounting", self._build_params(
            f"dateCreated ge '{start}' AND dateCreated le '{end}'", top))
