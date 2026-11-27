from unittest.mock import MagicMock, patch

import frappe
import requests

try:  # Frappe v16
	from frappe.tests import IntegrationTestCase as TestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as TestCase

from crm_platform.api.note_title import MAX_LENGTH, clean, suggest
from crm_platform.api.note_title_mock import mock_subject

CONTEXT = {
	"task": {"name": "7", "title": "Follow up", "due_date": None, "priority": "Low"},
	"status_from": "Todo",
	"status_to": "Done",
	"parent": {"doctype": "CRM Deal", "name": "CRM-DEAL-1", "title": "Matson", "status": "Proposal"},
	"names": {"deal": "Matson", "contact": "Ana Lead"},
	"content": "Quoted 45k USD for a 3-month project.",
}
URL = "https://titles.example.com/v1/note-title"


def _reply(payload=None, error=None, not_json=False):
	response = MagicMock()
	response.json.return_value = payload
	if not_json:
		response.json.side_effect = ValueError("not JSON")
	response.raise_for_status.side_effect = error
	return response


class TestSuggest(TestCase):
	def test_off_without_a_url(self):
		with patch.dict(frappe.conf, {"masquetu_note_title_url": None}), patch("requests.post") as post:
			self.assertIsNone(suggest(CONTEXT))
		post.assert_not_called()

	def test_posts_the_context_with_the_site_and_the_key(self):
		conf = {"masquetu_note_title_url": URL, "masquetu_api_key": "secret"}
		reply = _reply({"subject": "Quoted 45k USD, 3-month project"})
		with patch.dict(frappe.conf, conf), patch("requests.post", return_value=reply) as post:
			result = suggest(CONTEXT)

		self.assertEqual(result, "Quoted 45k USD, 3-month project")
		args, kwargs = post.call_args
		self.assertEqual(args, (URL,))
		self.assertEqual(kwargs["headers"], {"Authorization": "Bearer secret"})
		self.assertEqual(kwargs["json"]["content"], CONTEXT["content"])
		self.assertEqual(kwargs["json"]["site"], frappe.local.site)
		self.assertEqual(kwargs["timeout"], 3)

	def test_no_key_no_authorization_header(self):
		with (
			patch.dict(frappe.conf, {"masquetu_note_title_url": URL, "masquetu_api_key": None}),
			patch("requests.post", return_value=_reply({"subject": "x"})) as post,
		):
			suggest(CONTEXT)
		self.assertEqual(post.call_args.kwargs["headers"], {})

	def test_nothing_when_the_service_is_slow_down_or_wrong(self):
		failures = [
			{"side_effect": requests.Timeout()},
			{"side_effect": requests.ConnectionError()},
			{"return_value": _reply(error=requests.HTTPError("502"))},
			{"return_value": _reply(not_json=True)},
			{"return_value": _reply({"other": 1})},
			{"return_value": _reply(["not", "a", "dict"])},
		]
		for failure in failures:
			with patch.dict(frappe.conf, {"masquetu_note_title_url": URL}), patch("requests.post", **failure):
				self.assertIsNone(suggest(CONTEXT), failure)

	def test_mock_url_uses_the_local_mock(self):
		with patch.dict(frappe.conf, {"masquetu_note_title_url": "mock"}), patch("requests.post") as post:
			self.assertEqual(suggest(CONTEXT), "Quoted 45k USD for a 3-month project")
		post.assert_not_called()


class TestClean(TestCase):
	def test_one_line_without_quotes_or_closing_full_stop(self):
		self.assertEqual(clean('  "Budget\n approved." '), "Budget approved")

	def test_leaves_inner_punctuation(self):
		self.assertEqual(clean("PoC floor 20k held, ~7.5k SaaS"), "PoC floor 20k held, ~7.5k SaaS")

	def test_long_subjects_are_cut_at_a_word(self):
		cleaned = clean("word " * 30)
		self.assertTrue(cleaned.endswith("…"))
		self.assertLessEqual(len(cleaned), MAX_LENGTH + 1)
		self.assertNotIn("wor…", cleaned)

	def test_nothing_usable(self):
		for value in (None, "", "  ", '""', 7, ["x"]):
			self.assertIsNone(clean(value), value)


class TestMockSubject(TestCase):
	def test_first_sentence_in_seven_words(self):
		subject = mock_subject({"content": "They were unable to commit to a budget. Will retry in Q1."})
		self.assertEqual(subject, "They were unable to commit to a")

	def test_drops_the_opening_about_the_call(self):
		html = "<p>We had a short call with Ivan Petrov, where he asked for a demo.</p>"
		self.assertEqual(mock_subject({"content": html}), "He asked for a demo")
		# nothing left once the opening is dropped
		self.assertIsNone(mock_subject({"content": "We had a call."}))
		note = {"content": "We had a call where Ivan asked for a demo"}
		self.assertEqual(mock_subject(note), "Ivan asked for a demo")

	def test_leaves_out_the_deal_and_contact_the_title_names(self):
		names = {"deal": "Matson", "contact": "Ana Lead"}
		note = {"content": "Matson asked for a revised quote.", "names": names}
		self.assertEqual(mock_subject(note), "Asked for a revised quote")
		note = {"content": "Ana Lead (Matson) will confirm the budget.", "names": names}
		self.assertEqual(mock_subject(note), "Will confirm the budget")
		# only whole names
		note = {"content": "Matsons asked for a quote", "names": names}
		self.assertEqual(mock_subject(note), "Matsons asked for a quote")

	def test_empty_note_gives_nothing(self):
		self.assertIsNone(mock_subject({"content": ""}))
		self.assertIsNone(mock_subject({}))
