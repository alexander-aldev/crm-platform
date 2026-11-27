"""A stand-in for the Másquetú note title service, for development.

The real service is in masquetu-platform and writes the subject with an LLM. This one
only trims the note: its first sentence, without "We had a call with Ivan, where" and
without the deal and contact the title already names, cut to seven words. The CRM puts the
subject between the new status and those names: "Done, <subject> / Deal, Contact". It answers the same request as the real one, so the CRM, the hook and the
dialog can be tried end to end:

	bench --site <site> set-config masquetu_note_title_url mock
	# or, over HTTP, to exercise the request itself:
	bench --site <site> set-config masquetu_note_title_url \
		http://localhost:8000/api/method/crm_platform.api.note_title_mock.suggest

It only runs in developer mode.
"""

import re

import frappe
from frappe import _
from frappe.utils import strip_html_tags

MAX_WORDS = 7

# "We had a short call with Ivan Petrov, where ..." -> "..."
OPENER = re.compile(
	r"^(we|i)\s+(had|have|did|made)\s+(a|an|another|yet another)\s+(\w+\s+)?"
	r"(call|meeting|chat|discussion|email)\s*(with\s+(?-i:[A-Z]\w*(\s+[A-Z]\w*)?))?\s*[,:]?\s*"
	r"(where|and|that|in which)?\s*",
	re.IGNORECASE,
)


def mock_subject(context: dict) -> str | None:
	text = strip_html_tags(context.get("content") or "")
	sentence = re.split(r"(?<=[.!?])\s|\n", text.strip(), maxsplit=1)[0]
	sentence = OPENER.sub("", sentence).strip()
	sentence = without_names(sentence, (context.get("names") or {}).values())
	words = sentence.split()[:MAX_WORDS]
	subject = " ".join(words).strip(" .,;:!-")
	return subject[:1].upper() + subject[1:] if subject else None


def without_names(sentence: str, names) -> str:
	"""The sentence without the given names (whole, any case) and what they leave dangling."""
	for name in filter(None, names):
		sentence = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", "", sentence, flags=re.IGNORECASE)
	sentence = re.sub(r"\(\s*\)", "", sentence)
	sentence = re.sub(r"\s+", " ", sentence)
	sentence = re.sub(r"^[\s,;:\-–—|/@&]+", "", sentence)
	return sentence.strip()


@frappe.whitelist(allow_guest=True)
def suggest():
	"""POST the hook's context as JSON; answers `{"subject": ...}` like the real service."""
	if not frappe.conf.developer_mode:
		frappe.throw(_("The mock note title service only runs in developer mode"), frappe.PermissionError)
	key = frappe.conf.get("masquetu_api_key")
	if key and frappe.get_request_header("Authorization") != f"Bearer {key}":
		frappe.throw(_("Invalid API key"), frappe.AuthenticationError)

	# put at the top level of the response, not under "message" like a return value
	frappe.response["subject"] = mock_subject(frappe.request.get_json(silent=True) or {})
