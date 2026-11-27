"""Suggest the title of the note written when a task changes status.

Implements the `crm_task_note_title` hook of crm-patches/0003 (see crm-patches/README.md):
the CRM sends the task, the status change and the note's text, and gets back a short
subject that the CRM puts after the verb: "Done: <subject>".

The subject comes from a Másquetú service (kept in masquetu-platform, reached over
HTTP like everything that lives outside the AGPL code). Site config:

	masquetu_note_title_url   endpoint to POST to; unset turns suggestions off.
	                          "mock" uses the local mock in note_title_mock.py (developer mode)
	masquetu_api_key          sent as `Authorization: Bearer <key>`

Request body (JSON): the hook context (`task`, `status_from`, `status_to`, `parent`,
`content`) plus `site` and `lang`. Response (JSON): `{"subject": "<text>"}`.
The note's text leaves the site in that request, so the service must be hosted in the EU.
"""

import re

import frappe
import requests

TIMEOUT = 3  # seconds; the CRM stops waiting after 4, and keeps the filled-in title
MAX_LENGTH = 60


def suggest(context: dict) -> str | None:
	url = frappe.conf.get("masquetu_note_title_url")
	if not url:
		return None

	if url == "mock":
		from crm_platform.api.note_title_mock import mock_subject

		return clean(mock_subject(context))

	headers = {}
	if key := frappe.conf.get("masquetu_api_key"):
		headers["Authorization"] = f"Bearer {key}"
	body = {**context, "site": frappe.local.site, "lang": frappe.local.lang}
	try:
		response = requests.post(url, json=body, headers=headers, timeout=TIMEOUT)
		response.raise_for_status()
		subject = response.json().get("subject")
	except (requests.RequestException, ValueError, AttributeError) as e:
		# slow or down: the CRM keeps the title it filled in, so this is not an error to log
		frappe.logger("crm_platform").warning(f"note title service: {e!r}")
		return None
	return clean(subject)


def clean(subject) -> str | None:
	"""One line, no surrounding quotes or closing full stop, at most MAX_LENGTH characters."""
	if not isinstance(subject, str):
		return None
	subject = re.sub(r"\s+", " ", subject).strip().strip("\"'“”‘’«»").strip()
	subject = re.sub(r"[.。]+$", "", subject).strip()
	if len(subject) > MAX_LENGTH:
		cut = subject[:MAX_LENGTH]
		subject = cut.rsplit(" ", 1)[0] if " " in cut else cut
		subject = subject.rstrip(",;:- ") + "…"
	return subject or None
