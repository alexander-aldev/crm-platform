"""Data for the Másquetú deal board that the CRM's own board response lacks.

The CRM's `crm.api.doc.get_data` returns 20 cards per column and nothing else.
The deal card (public/js/masquetu.js) also needs column totals over
*all* matching deals, and per card: the display title, lead source, owner,
primary contact and next activity (the earliest open CRM Task). `board_meta`
returns those in one call. Spec: docs/deal-card-activity-indicator.md.
"""

import re
from html import unescape

import frappe
from frappe import _

from crm.api.doc import convert_filter_to_tuple

OPEN_TASK_STATUSES = ("Backlog", "Todo", "In Progress")
CLOSED_STATUS_TYPES = ("Won", "Lost")
TITLE_FIELD = "custom_pipedrive_title"  # set by the Pipedrive migration; absent on other sites
VALUE_FIELDS = ["expected_deal_value", "deal_value"]  # first non-zero wins: imports set the first, the CRM's own forms often only the second
# Two-level lead source (roadmap B.7); read when the fields exist, absent until then
SOURCE_DETAIL_FIELD = "source_detail"
DIRECTION_FIELD = "direction"
DESCRIPTION_CHARS = 300  # the pop-up shows 3 lines
MAX_NAMES = 1000


@frappe.whitelist()
def board_meta(
	doctype: str,
	column_field: str,
	filters: dict | str | None = None,
	default_filters: dict | str | None = None,
	names: list | str | None = None,
):
	if doctype != "CRM Deal":
		return {}
	if not frappe.has_permission(doctype, "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not frappe.get_meta(doctype).has_field(column_field):
		frappe.throw(_("Unknown column field {0}").format(column_field))

	filters = _resolve_filters(filters, default_filters)
	names = frappe.parse_json(names or "[]")[:MAX_NAMES]
	closed = set(frappe.get_all("CRM Deal Status", filters={"type": ["in", CLOSED_STATUS_TYPES]}, pluck="name"))

	columns, board = _totals(doctype, column_field, filters, closed)
	return {
		"columns": columns,
		"board": board,
		"cards": _cards(names, closed, board["currency"]),
	}


def _resolve_filters(filters, default_filters):
	"""Mirror crm.api.doc.get_data: resolve @me and merge the view's default filters."""
	filters = frappe._dict(frappe.parse_json(filters or "{}"))
	user = frappe.session.user
	for key, value in filters.items():
		if isinstance(value, list):
			filters[key] = [user if v == "@me" else f"%{user}%" if v == "%@me%" else v for v in value]
		elif value == "@me":
			filters[key] = user
	if default_filters:
		filters.update(frappe.parse_json(default_filters))
	return filters


def _value(deal):
	return next((deal.get(f) for f in VALUE_FIELDS if deal.get(f)), 0)


def _totals(doctype, column_field, filters, closed):
	"""Sum each deal's value per column, converted with the deal's stored exchange rate.

	Rows are summed in Python rather than with SQL SUM(): the aggregate syntax differs
	between Frappe v15 and v16, and each deal carries its own rate.
	"""
	rows = frappe.get_list(
		doctype,
		filters=convert_filter_to_tuple(doctype, filters),
		fields=[column_field, *VALUE_FIELDS, "exchange_rate"],
		limit_page_length=0,
	)
	columns = {}
	board = {"total": 0.0, "count": 0}
	for r in rows:
		value = _value(r) * (r.exchange_rate or 1)
		col = columns.setdefault(r.get(column_field) or "", {"total": 0.0, "count": 0})
		col["total"] += value
		col["count"] += 1
		if r.get(column_field) not in closed:
			board["total"] += value
			board["count"] += 1
	board["currency"] = frappe.db.get_single_value("FCRM Settings", "currency") or "USD"
	return columns, board


def _cards(names, closed, base_currency):
	if not names:
		return {}
	meta = frappe.get_meta("CRM Deal")
	optional = [f for f in (TITLE_FIELD, SOURCE_DETAIL_FIELD, DIRECTION_FIELD) if meta.has_field(f)]
	fields = ["name", *VALUE_FIELDS, "currency", "status", "source", "deal_owner", *optional]
	deals = frappe.get_list("CRM Deal", filters={"name": ["in", names]}, fields=fields, limit_page_length=0)
	deal_names = [d.name for d in deals]
	next_steps = _next_steps(deal_names)
	contacts = _contacts(deal_names)
	users = _users({d.deal_owner for d in deals} | {s["assigned_to"] for s in next_steps.values()})
	for step in next_steps.values():
		step["assigned_to"] = users.get(step["assigned_to"])
	return {
		d.name: {
			"title": d.get(TITLE_FIELD) or d.name,
			"value": _value(d),
			"currency": d.currency or base_currency,
			"closed": d.status in closed,
			"source": d.source,
			"source_detail": d.get(SOURCE_DETAIL_FIELD),
			"direction": d.get(DIRECTION_FIELD),
			"owner": users.get(d.deal_owner),
			"contact": contacts.get(d.name),
			"next_step": next_steps.get(d.name),
		}
		for d in deals
	}


def _contacts(names):
	"""Each deal's primary contact's full name; the first linked contact if none is primary."""
	if not names:
		return {}
	rows = frappe.get_all(
		"CRM Contacts",
		filters={"parenttype": "CRM Deal", "parentfield": "contacts", "parent": ["in", names]},
		fields=["parent", "contact", "full_name", "is_primary", "idx"],
		order_by="is_primary desc, idx asc",
	)
	result = {}
	for r in rows:
		result.setdefault(r.parent, r.full_name or r.contact)
	return result


def _users(names):
	"""Full name and photo for each user, for avatars and the task's assignee."""
	names = [n for n in names if n]
	if not names:
		return {}
	rows = frappe.get_all(
		"User", filters={"name": ["in", names]}, fields=["name", "full_name", "user_image"]
	)
	return {u.name: {"name": u.name, "full_name": u.full_name or u.name, "image": u.user_image} for u in rows}


def _next_steps(names):
	"""Earliest open task per deal: soonest due date first, undated tasks last, then oldest."""
	if not names:
		return {}
	tasks = frappe.get_list(
		"CRM Task",
		filters={
			"reference_doctype": "CRM Deal",
			"reference_docname": ["in", names],
			"status": ["in", OPEN_TASK_STATUSES],
		},
		fields=["name", "title", "due_date", "assigned_to", "description", "reference_docname", "creation"],
		limit_page_length=0,
	)
	tasks.sort(key=lambda t: (t.due_date is None, t.due_date or t.creation, t.creation))
	result = {}
	for t in tasks:
		if t.reference_docname in result:
			continue
		description = " ".join(unescape(re.sub(r"<[^>]*>", " ", t.description or "")).split())
		result[t.reference_docname] = {
			"task": t.name,
			"title": t.title,
			"due_date": str(t.due_date) if t.due_date else None,
			"assigned_to": t.assigned_to,
			"description": description[:DESCRIPTION_CHARS],
		}
	return result
