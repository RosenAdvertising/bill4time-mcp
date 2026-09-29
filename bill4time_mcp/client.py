"""Bill4Time API client. API key embedded in URL path. Read-only OData API."""

import logging
import math
import os
import re
from datetime import date
from urllib.parse import quote

import requests
from mcp.server.mcpserver.exceptions import ToolError

from bill4time_mcp import credentials

BASE = "https://secure.bill4time.com/b4t-api"
DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200
DEFAULT_ORDERBY = "id desc"
REQUEST_TIMEOUT = 30
logger = logging.getLogger(__name__)


class SafeToolFailure(ToolError):
    """A failure with deliberately safe, client-visible guidance."""


_SAFE_VENDOR_REASONS = {
    "invalid_api_key": "invalid API key",
    "unauthorized": "authorization rejected",
    "forbidden": "access denied",
    "not_found": "resource not found",
    "rate_limit_exceeded": "rate limit reached",
    "service_unavailable": "service temporarily unavailable",
    "internal_server_error": "server error",
}


def _safe_vendor_reason(resp) -> str:
    """Use only recognized generic vendor reason codes; never echo vendor text."""
    try:
        code = resp.json().get("code", "")
    except (ValueError, AttributeError, TypeError):
        code = ""
    if isinstance(code, str):
        return _SAFE_VENDOR_REASONS.get(code.strip().lower(), "request failed")
    return "request failed"


# Resolve credentials through the pluggable store (OS keyring -> .env file).
credentials.load_into_environ(["BILL4TIME_API_KEY"])

API_KEY = os.environ.get("BILL4TIME_API_KEY", "")


def _retry_after_seconds(resp):
    try:
        raw = resp.headers.get("Retry-After", "")
        if not re.fullmatch(r"\s*\d+(?:\.\d+)?\s*", str(raw)):
            return None
        delay = float(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return delay if math.isfinite(delay) and delay >= 0 else None


def _json_response(resp):
    try:
        return resp.json()
    except ValueError as exc:
        logger.warning(
            "bill4time_response_rejected reason=non_json status=%s", resp.status_code
        )
        raise SafeToolFailure(
            "Bill4Time returned an unreadable response. Try again later."
        ) from exc


def _apply_total_cap(data, params: dict | None):
    """Enforce the requested list cap even if an upstream response overfills it."""
    if not params or "$top" not in params:
        return data
    top = params["$top"]
    if isinstance(data, list):
        return data[:top]
    return data


class Bill4TimeClient:
    def __init__(self):
        if not API_KEY:
            logger.error("bill4time_client_rejected reason=missing_api_key")
            raise SafeToolFailure(
                "Missing BILL4TIME_API_KEY. Set it or run bill4time-mcp-setup. Restart the MCP server after setup."
            )
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        self._api_url = f"{BASE}/{quote(str(API_KEY), safe='')}/v1"

    def _get(self, resource: str, params: dict | None = None):
        url = f"{self._api_url}/{quote(str(resource), safe='')}"
        try:
            resp = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            logger.warning("bill4time_request_failed reason=transport_error")
            raise SafeToolFailure(
                "Bill4Time read failed because the connection timed out or was unavailable. Check the connection and retry."
            ) from exc
        if resp.status_code == 429:
            retry_after = _retry_after_seconds(resp)
            logger.warning(
                "bill4time_request_delayed reason=rate_limit retry_after_seconds=%s",
                retry_after,
            )
            hint = (
                f"Retry after {retry_after:g} seconds."
                if retry_after is not None
                else "Retry later."
            )
            raise SafeToolFailure(f"Bill4Time rate limit reached. {hint}")
        if not resp.ok:
            logger.warning(
                "bill4time_request_rejected reason=vendor_http_error status=%s",
                resp.status_code,
            )
            if resp.status_code == 401:
                raise SafeToolFailure(
                    "Bill4Time authorization was rejected or expired. Reauthorize with bill4time-mcp-setup."
                )
            if resp.status_code == 403:
                raise SafeToolFailure(
                    "Bill4Time access denied: the connected account lacks permission for this action (or the authorization expired; re-run bill4time-mcp-setup if so)."
                )
            if resp.status_code == 404:
                raise SafeToolFailure(
                    "Bill4Time resource was not found. Check the requested record."
                )
            raise SafeToolFailure(
                f"Bill4Time returned HTTP {resp.status_code}: {_safe_vendor_reason(resp)}"
            )
        data = _json_response(resp)
        if (
            isinstance(data, list)
            and not data
            and params
            and len(params) == 1
            and isinstance(params.get("$filter"), str)
            and params["$filter"].startswith("id eq ")
            and params["$filter"][7:].isdigit()
        ):
            raise SafeToolFailure(
                "Bill4Time resource was not found. Check the requested record."
            )
        return _apply_total_cap(data, params)

    def _build_params(
        self,
        filter_expr: str = "",
        top: int = DEFAULT_LIST_LIMIT,
        skip: int = 0,
        orderby: str = DEFAULT_ORDERBY,
        select: str = "",
        count: bool = False,
    ) -> dict:
        if not 1 <= top <= MAX_LIST_LIMIT:
            logger.warning("list_request_rejected reason=invalid_top")
            raise SafeToolFailure(
                f"Argument top must be an integer from 1 to {MAX_LIST_LIMIT}."
            )
        if skip < 0:
            logger.warning("list_request_rejected reason=negative_skip")
            raise SafeToolFailure("Argument skip must be a non-negative integer.")
        if not orderby.strip():
            logger.warning("list_request_rejected reason=missing_orderby")
            raise SafeToolFailure("Argument orderby must be a non-empty string.")

        params = {"$top": top, "$orderby": orderby}
        if filter_expr:
            params["$filter"] = filter_expr
        if skip:
            params["$skip"] = skip
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
    def _parse_date(value: str, argument: str = "date") -> str:
        """Validate and normalise an ISO-8601 date string (YYYY-MM-DD).
        Raises SafeToolFailure if the format is invalid."""
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as exc:
            logger.warning("list_request_rejected reason=invalid_date")
            raise SafeToolFailure(
                f"Argument {argument} must use YYYY-MM-DD format."
            ) from exc

    # ── Clients ───────────────────────────────────────────────────────────────

    def list_clients(
        self,
        filter_expr: str = "",
        top: int = DEFAULT_LIST_LIMIT,
        skip: int = 0,
        orderby: str = DEFAULT_ORDERBY,
        select: str = "",
    ):
        return self._get(
            "clients", self._build_params(filter_expr, top, skip, orderby, select)
        )

    def get_client(self, client_id: int):
        return self._get("clients", {"$filter": f"id eq {client_id}"})

    def list_clients_by_status(
        self,
        status: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "clients",
            self._build_params(
                f"status eq {self._odata_str(status)}", top, orderby=orderby
            ),
        )

    # ── Projects ──────────────────────────────────────────────────────────────

    def list_projects(
        self,
        filter_expr: str = "",
        top: int = DEFAULT_LIST_LIMIT,
        skip: int = 0,
        orderby: str = DEFAULT_ORDERBY,
        select: str = "",
    ):
        return self._get(
            "projects", self._build_params(filter_expr, top, skip, orderby, select)
        )

    def get_project(self, project_id: int):
        return self._get("projects", {"$filter": f"id eq {project_id}"})

    def list_projects_by_client(
        self,
        client_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "projects",
            self._build_params(f"clientId eq {client_id}", top, orderby=orderby),
        )

    def list_projects_by_status(
        self,
        status: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "projects",
            self._build_params(
                f"status eq {self._odata_str(status)}", top, orderby=orderby
            ),
        )

    def list_projects_by_billing_method(
        self,
        billing_method: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "projects",
            self._build_params(
                f"billingMethod eq {self._odata_str(billing_method)}",
                top,
                orderby=orderby,
            ),
        )

    # ── Time Entries ──────────────────────────────────────────────────────────

    def list_time_entries(
        self,
        filter_expr: str = "",
        top: int = DEFAULT_LIST_LIMIT,
        skip: int = 0,
        orderby: str = DEFAULT_ORDERBY,
        select: str = "",
    ):
        return self._get(
            "timeEntries", self._build_params(filter_expr, top, skip, orderby, select)
        )

    def get_time_entry(self, entry_id: int):
        return self._get("timeEntries", {"$filter": f"id eq {entry_id}"})

    def list_time_entries_by_client(
        self,
        client_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "timeEntries",
            self._build_params(f"clientId eq {client_id}", top, orderby=orderby),
        )

    def list_time_entries_by_project(
        self,
        project_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "timeEntries",
            self._build_params(f"projectId eq {project_id}", top, orderby=orderby),
        )

    def list_time_entries_by_user(
        self,
        user_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "timeEntries",
            self._build_params(f"userId eq {user_id}", top, orderby=orderby),
        )

    def list_time_entries_by_invoice(
        self,
        invoice_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "timeEntries",
            self._build_params(f"invoiceId eq {invoice_id}", top, orderby=orderby),
        )

    def list_time_entries_by_date_range(
        self,
        start_date: str,
        end_date: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        start = self._parse_date(start_date, "start_date")
        end = self._parse_date(end_date, "end_date")
        return self._get(
            "timeEntries",
            self._build_params(
                f"entryDate ge '{start}' AND entryDate le '{end}'",
                top,
                orderby=orderby,
            ),
        )

    def list_time_entries_by_billing_status(
        self,
        billing_status: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "timeEntries",
            self._build_params(
                f"billingStatus eq {self._odata_str(billing_status)}",
                top,
                orderby=orderby,
            ),
        )

    # ── Expenses ──────────────────────────────────────────────────────────────

    def list_expenses(
        self,
        filter_expr: str = "",
        top: int = DEFAULT_LIST_LIMIT,
        skip: int = 0,
        orderby: str = DEFAULT_ORDERBY,
        select: str = "",
    ):
        return self._get(
            "expenses", self._build_params(filter_expr, top, skip, orderby, select)
        )

    def get_expense(self, expense_id: int):
        return self._get("expenses", {"$filter": f"id eq {expense_id}"})

    def list_expenses_by_client(
        self,
        client_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "expenses",
            self._build_params(f"clientId eq {client_id}", top, orderby=orderby),
        )

    def list_expenses_by_project(
        self,
        project_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "expenses",
            self._build_params(f"projectId eq {project_id}", top, orderby=orderby),
        )

    def list_expenses_by_invoice(
        self,
        invoice_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "expenses",
            self._build_params(f"invoiceId eq {invoice_id}", top, orderby=orderby),
        )

    def list_expenses_by_date_range(
        self,
        start_date: str,
        end_date: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        start = self._parse_date(start_date, "start_date")
        end = self._parse_date(end_date, "end_date")
        return self._get(
            "expenses",
            self._build_params(
                f"expenseDate ge '{start}' AND expenseDate le '{end}'",
                top,
                orderby=orderby,
            ),
        )

    # ── Invoices ──────────────────────────────────────────────────────────────

    def list_invoices(
        self,
        filter_expr: str = "",
        top: int = DEFAULT_LIST_LIMIT,
        skip: int = 0,
        orderby: str = DEFAULT_ORDERBY,
        select: str = "",
    ):
        return self._get(
            "invoices", self._build_params(filter_expr, top, skip, orderby, select)
        )

    def get_invoice(self, invoice_id: int):
        return self._get("invoices", {"$filter": f"id eq {invoice_id}"})

    def list_invoices_by_client(
        self,
        client_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "invoices",
            self._build_params(f"clientId eq {client_id}", top, orderby=orderby),
        )

    def list_invoices_by_project(
        self,
        project_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "invoices",
            self._build_params(f"projectId eq {project_id}", top, orderby=orderby),
        )

    def list_invoices_by_status(
        self,
        status: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "invoices",
            self._build_params(
                f"status eq {self._odata_str(status)}", top, orderby=orderby
            ),
        )

    def list_invoices_by_paid_status(
        self,
        paid_status: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "invoices",
            self._build_params(
                f"paidStatus eq {self._odata_str(paid_status)}",
                top,
                orderby=orderby,
            ),
        )

    def list_invoices_by_date_range(
        self,
        start_date: str,
        end_date: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        start = self._parse_date(start_date, "start_date")
        end = self._parse_date(end_date, "end_date")
        return self._get(
            "invoices",
            self._build_params(
                f"invoiceDate ge '{start}' AND invoiceDate le '{end}'",
                top,
                orderby=orderby,
            ),
        )

    # ── Payments ──────────────────────────────────────────────────────────────

    def list_payments(
        self,
        filter_expr: str = "",
        top: int = DEFAULT_LIST_LIMIT,
        skip: int = 0,
        orderby: str = DEFAULT_ORDERBY,
        select: str = "",
    ):
        return self._get(
            "payments", self._build_params(filter_expr, top, skip, orderby, select)
        )

    def get_payment(self, payment_id: int):
        return self._get("payments", {"$filter": f"id eq {payment_id}"})

    def list_payments_by_client(
        self,
        client_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "payments",
            self._build_params(f"clientId eq {client_id}", top, orderby=orderby),
        )

    def list_payments_by_project(
        self,
        project_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "payments",
            self._build_params(f"projectId eq {project_id}", top, orderby=orderby),
        )

    def list_payments_by_date_range(
        self,
        start_date: str,
        end_date: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        start = self._parse_date(start_date, "start_date")
        end = self._parse_date(end_date, "end_date")
        return self._get(
            "payments",
            self._build_params(
                f"paymentDate ge '{start}' AND paymentDate le '{end}'",
                top,
                orderby=orderby,
            ),
        )

    # ── Payments Applied ──────────────────────────────────────────────────────

    def list_payments_applied(
        self,
        filter_expr: str = "",
        top: int = DEFAULT_LIST_LIMIT,
        skip: int = 0,
        orderby: str = DEFAULT_ORDERBY,
        select: str = "",
    ):
        return self._get(
            "paymentsApplied",
            self._build_params(filter_expr, top, skip, orderby, select),
        )

    def get_payment_applied(self, record_id: int):
        return self._get("paymentsApplied", {"$filter": f"id eq {record_id}"})

    def list_payments_applied_by_invoice(
        self,
        invoice_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "paymentsApplied",
            self._build_params(f"invoiceId eq {invoice_id}", top, orderby=orderby),
        )

    def list_payments_applied_by_payment(
        self,
        payment_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "paymentsApplied",
            self._build_params(f"paymentId eq {payment_id}", top, orderby=orderby),
        )

    def list_payments_applied_by_date_range(
        self,
        start_date: str,
        end_date: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        start = self._parse_date(start_date, "start_date")
        end = self._parse_date(end_date, "end_date")
        return self._get(
            "paymentsApplied",
            self._build_params(
                f"dateApplied ge '{start}' AND dateApplied le '{end}'",
                top,
                orderby=orderby,
            ),
        )

    # ── Users ─────────────────────────────────────────────────────────────────

    def list_users(
        self,
        filter_expr: str = "",
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get("users", self._build_params(filter_expr, top, orderby=orderby))

    def get_user(self, user_id: int):
        return self._get("users", {"$filter": f"id eq {user_id}"})

    # ── Contacts ──────────────────────────────────────────────────────────────

    def list_contacts(
        self,
        filter_expr: str = "",
        top: int = DEFAULT_LIST_LIMIT,
        skip: int = 0,
        orderby: str = DEFAULT_ORDERBY,
        select: str = "",
    ):
        return self._get(
            "contacts", self._build_params(filter_expr, top, skip, orderby, select)
        )

    def get_contact(self, contact_id: int):
        return self._get("contacts", {"$filter": f"id eq {contact_id}"})

    def list_contacts_by_status(
        self,
        status: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "contacts",
            self._build_params(
                f"status eq {self._odata_str(status)}", top, orderby=orderby
            ),
        )

    def list_contacts_by_date_range(
        self,
        start_date: str,
        end_date: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        start = self._parse_date(start_date, "start_date")
        end = self._parse_date(end_date, "end_date")
        return self._get(
            "contacts",
            self._build_params(
                f"creationDate ge '{start}' AND creationDate le '{end}'",
                top,
                orderby=orderby,
            ),
        )

    # ── Contact Connections ───────────────────────────────────────────────────

    def list_contact_connections(
        self,
        filter_expr: str = "",
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "contactConnections",
            self._build_params(filter_expr, top, orderby=orderby),
        )

    def list_contact_connections_by_contact(
        self,
        contact_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "contactConnections",
            self._build_params(f"contactId eq {contact_id}", top, orderby=orderby),
        )

    def list_contact_connections_by_client(
        self,
        client_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "contactConnections",
            self._build_params(f"clientId eq {client_id}", top, orderby=orderby),
        )

    def list_contact_connections_by_project(
        self,
        project_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "contactConnections",
            self._build_params(f"projectId eq {project_id}", top, orderby=orderby),
        )

    # ── Trust Accounting ──────────────────────────────────────────────────────

    def list_trust_records(
        self,
        filter_expr: str = "",
        top: int = DEFAULT_LIST_LIMIT,
        skip: int = 0,
        orderby: str = DEFAULT_ORDERBY,
        select: str = "",
    ):
        return self._get(
            "trustAccounting",
            self._build_params(filter_expr, top, skip, orderby, select),
        )

    def get_trust_record(self, record_id: int):
        return self._get("trustAccounting", {"$filter": f"id eq {record_id}"})

    def list_trust_records_by_client(
        self,
        client_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "trustAccounting",
            self._build_params(f"clientId eq {client_id}", top, orderby=orderby),
        )

    def list_trust_records_by_project(
        self,
        project_id: int,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        return self._get(
            "trustAccounting",
            self._build_params(f"projectId eq {project_id}", top, orderby=orderby),
        )

    def list_trust_records_by_date_range(
        self,
        start_date: str,
        end_date: str,
        top: int = DEFAULT_LIST_LIMIT,
        orderby: str = DEFAULT_ORDERBY,
    ):
        start = self._parse_date(start_date, "start_date")
        end = self._parse_date(end_date, "end_date")
        return self._get(
            "trustAccounting",
            self._build_params(
                f"dateCreated ge '{start}' AND dateCreated le '{end}'",
                top,
                orderby=orderby,
            ),
        )
