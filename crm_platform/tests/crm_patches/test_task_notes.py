"""Tests for crm-patches/<tag>/0003-task-notes.patch.

They need a CRM with that patch applied and skip themselves on one without it.
A note written on a task is an FCRM Note that references the task, so none of this
changes a schema.
"""

import importlib.util
import unittest
from unittest.mock import patch

import frappe

try:  # Frappe v16
	from frappe.tests import IntegrationTestCase as TestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as TestCase

PATCHED = importlib.util.find_spec("crm.api.task") is not None


def _note_filters(task):
	return {"reference_doctype": "CRM Task", "reference_docname": str(task.name)}


@unittest.skipUnless(PATCHED, "crm-patches 0003-task-notes is not applied")
class TestTaskNotes(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_a_note_on_a_task_shows_on_the_tasks_deal(self):
		from crm.api.activities import get_linked_notes

		deal = make_deal("Task Notes Org")
		task = make_task("Call", deal)

		note = add_note(task, "Done: Call", "<p>Budget approved</p>")

		self.assertEqual((note.reference_doctype, note.reference_docname), ("CRM Task", str(task.name)))
		listed = [n for n in get_linked_notes(deal.name) if n.name == note.name]
		self.assertEqual(len(listed), 1)
		self.assertEqual((listed[0].task, listed[0].task_title), (str(task.name), "Call"))

	def test_the_deals_own_notes_are_not_marked_as_task_notes(self):
		from crm.api.activities import get_linked_notes

		deal = make_deal("Plain Notes Org")
		make_task("Call", deal)
		own = frappe.get_doc(
			{
				"doctype": "FCRM Note",
				"title": "On the deal",
				"reference_doctype": "CRM Deal",
				"reference_docname": deal.name,
			}
		).insert()

		listed = {n.name: n for n in get_linked_notes(deal.name)}
		self.assertNotIn("task", listed[own.name])

	def test_notes_follow_the_task_to_another_deal(self):
		from crm.api.activities import get_linked_notes

		first, second = make_deal("First Org"), make_deal("Second Org")
		task = make_task("Move me", first)
		note = add_note(task, "Context")

		task = frappe.get_doc("CRM Task", task.name)
		task.reference_docname = second.name
		task.save()

		self.assertNotIn(note.name, [n.name for n in get_linked_notes(first.name)])
		self.assertIn(note.name, [n.name for n in get_linked_notes(second.name)])

	def test_get_notes_lists_only_that_tasks_notes_newest_first(self):
		from crm.api.task import get_notes

		deal = make_deal("Task List Org")
		task, other = make_task("One", deal), make_task("Two", deal)
		first = add_note(task, "First")
		second = add_note(task, "Second")
		add_note(other, "Elsewhere")
		frappe.db.set_value("FCRM Note", first.name, "creation", "2026-01-01 10:00:00")

		self.assertEqual([n.name for n in get_notes(task.name)], [second.name, first.name])

	def test_deleting_a_task_keeps_its_notes_on_the_deal(self):
		deal = make_deal("Delete Task Org")
		task = make_task("Delete me", deal)
		note = add_note(task, "Outcome")

		frappe.delete_doc("CRM Task", task.name)

		kept = frappe.db.get_value("FCRM Note", note.name, ["reference_doctype", "reference_docname"])
		self.assertEqual(kept, ("CRM Deal", deal.name))

	def test_deleting_a_task_without_a_parent_deletes_its_notes(self):
		task = make_task("Loose task")
		note = add_note(task, "Remember")

		frappe.delete_doc("CRM Task", task.name)

		self.assertFalse(frappe.db.exists("FCRM Note", note.name))

	def test_a_task_note_belongs_to_the_tasks_deal_for_mentions(self):
		deal = make_deal("Mention Org")
		note = frappe.get_doc(
			{
				"doctype": "FCRM Note",
				"title": "x",
				"reference_doctype": "CRM Task",
				"reference_docname": str(make_task("Call", deal).name),
			}
		)
		self.assertEqual(note.parent_reference(), ("CRM Deal", deal.name))

		on_deal = frappe.get_doc(
			{
				"doctype": "FCRM Note",
				"title": "y",
				"reference_doctype": "CRM Deal",
				"reference_docname": deal.name,
			}
		)
		self.assertEqual(on_deal.parent_reference(), ("CRM Deal", deal.name))


@unittest.skipUnless(PATCHED, "crm-patches 0003-task-notes is not applied")
class TestSetStatus(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_writes_the_status_and_the_note_together(self):
		from crm.api.task import set_status

		task = make_task("Close me", status="Todo")
		set_status(task.name, "Done", {"title": "Done: Close me", "content": "<p>ok</p>"})

		self.assertEqual(frappe.db.get_value("CRM Task", task.name, "status"), "Done")
		self.assertEqual(frappe.db.get_value("FCRM Note", _note_filters(task), "title"), "Done: Close me")

	def test_without_a_note_changes_only_the_status(self):
		from crm.api.task import set_status

		task = make_task("Skip note", status="Todo")
		set_status(task.name, "In Progress")

		self.assertEqual(frappe.db.get_value("CRM Task", task.name, "status"), "In Progress")
		self.assertFalse(frappe.db.exists("FCRM Note", _note_filters(task)))

	def test_an_untitled_note_changes_nothing(self):
		from crm.api.task import set_status

		task = make_task("Strict", status="Todo")
		with self.assertRaises(frappe.ValidationError):
			set_status(task.name, "Done", {"title": "  ", "content": "x"})

		self.assertEqual(frappe.db.get_value("CRM Task", task.name, "status"), "Todo")


@unittest.skipUnless(PATCHED, "crm-patches 0003-task-notes is not applied")
class TestSuggestNoteTitle(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_passes_the_task_and_note_to_the_hook(self):
		from crm.api.task import suggest_note_title

		deal = make_deal("Suggest Org")
		task = make_task("Follow up", deal)
		seen = {}

		def hook(context):
			seen.update(context)
			return "  Budget approved "

		with patch("crm.api.task._title_suggester", return_value=hook):
			result = suggest_note_title(task.name, "Todo", "Done", "<p>Budget <b>approved</b></p>")

		self.assertEqual(result, {"subject": "  Budget approved "})
		self.assertEqual(seen["content"], "Budget approved")
		self.assertEqual(seen["task"]["title"], "Follow up")
		self.assertEqual(seen["parent"]["title"], "Suggest Org")
		self.assertEqual(seen["names"], {"deal": "Suggest Org", "contact": None})
		self.assertEqual((seen["status_from"], seen["status_to"]), ("Todo", "Done"))

	def test_none_without_a_hook(self):
		from crm.api.task import suggest_note_title

		task = make_task("Follow up")
		with patch("crm.api.task._title_suggester", return_value=None):
			self.assertIsNone(suggest_note_title(task.name, "Todo", "Done", "text"))

	def test_none_and_logged_when_the_hook_fails(self):
		from crm.api.task import suggest_note_title

		task = make_task("Follow up")

		def failing(context):
			raise RuntimeError("boom")

		with (
			patch("crm.api.task._title_suggester", return_value=failing),
			patch("frappe.log_error") as log_error,
		):
			self.assertIsNone(suggest_note_title(task.name, "Todo", "Done", "text"))
		log_error.assert_called_once()

	def test_none_when_the_hook_returns_nothing_usable(self):
		from crm.api.task import suggest_note_title

		task = make_task("Follow up")
		for value in (None, "", "   ", 5):
			with patch("crm.api.task._title_suggester", return_value=lambda context, v=value: v):
				self.assertIsNone(suggest_note_title(task.name, "Todo", "Done", "text"))


@unittest.skipUnless(PATCHED, "crm-patches 0003-task-notes is not applied")
class TestGetTitleContext(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_names_the_deal_and_its_primary_contact(self):
		from crm.api.task import get_title_context

		deal = make_deal("Context Org")
		add_contact(deal, "Second", "Person")
		primary = add_contact(deal, "Primary", "Person")
		deal.set_primary_contact(primary.name)
		deal.save()
		task = make_task("Follow up", deal)

		self.assertEqual(
			get_title_context(task.name), {"deal": "Context Org", "contact": "Primary Person"}
		)

	def test_the_first_contact_is_the_primary_one_until_another_is_chosen(self):
		from crm.api.task import get_title_context

		deal = make_deal("First Contact Org")
		add_contact(deal, "First", "Person")
		add_contact(deal, "Later", "Person")
		task = make_task("Follow up", deal)

		self.assertEqual(get_title_context(task.name)["contact"], "First Person")

	def test_a_deal_without_contacts_has_only_its_name(self):
		from crm.api.task import get_title_context

		task = make_task("Follow up", make_deal("Lonely Org"))

		self.assertEqual(get_title_context(task.name), {"deal": "Lonely Org", "contact": None})

	def test_a_lead_is_its_organization_and_person(self):
		from crm.api.task import get_title_context

		lead = frappe.get_doc(
			{"doctype": "CRM Lead", "first_name": "Ana", "last_name": "Lead", "organization": "Lead Org"}
		).insert()
		task = frappe.get_doc(
			{"doctype": "CRM Task", "title": "Call", "reference_doctype": "CRM Lead", "reference_docname": lead.name}
		).insert()

		self.assertEqual(get_title_context(task.name), {"deal": "Lead Org", "contact": "Ana Lead"})

	def test_a_task_without_a_parent_has_no_names(self):
		from crm.api.task import get_title_context

		task = make_task("Loose")

		self.assertEqual(get_title_context(task.name), {"deal": None, "contact": None})


def make_deal(organization_name):
	org = frappe.get_doc({"doctype": "CRM Organization", "organization_name": organization_name}).insert()
	return frappe.get_doc({"doctype": "CRM Deal", "organization": org.name}).insert()


def make_task(title, deal=None, **kwargs):
	data = {"doctype": "CRM Task", "title": title, **kwargs}
	if deal:
		data.update(reference_doctype="CRM Deal", reference_docname=deal.name)
	return frappe.get_doc(data).insert()


def add_note(task, title, content=None):
	from crm.api.task import add_note as _add_note

	return frappe.get_doc("FCRM Note", _add_note(task.name, title, content)["name"])


def add_contact(deal, first_name, last_name):
	contact = frappe.get_doc({"doctype": "Contact", "first_name": first_name, "last_name": last_name}).insert()
	deal.append("contacts", {"contact": contact.name})
	deal.save()
	return contact
