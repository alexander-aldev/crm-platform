import frappe

try:  # Frappe v16
	from frappe.tests import IntegrationTestCase as TestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as TestCase

from crm_platform.api.kanban import board_meta


def _status(type_):
	return frappe.get_all("CRM Deal Status", filters={"type": type_}, pluck="name", limit=1)[0]


class TestBoardMeta(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.org = frappe.get_doc(
			{"doctype": "CRM Organization", "organization_name": f"Board Test {frappe.generate_hash(length=6)}"}
		).insert()
		self.open_status = _status("Open")
		self.won_status = _status("Won")
		self.deals = [
			self._deal(1200, self.open_status),
			self._deal(800, self.open_status),
			self._deal(4500, self.won_status),
		]

	def tearDown(self):
		frappe.db.rollback()

	def _deal(self, value, status, **extra):
		doc = frappe.get_doc(
			{
				"doctype": "CRM Deal",
				"organization": self.org.name,
				"status": status,
				"expected_deal_value": value,
				**extra,
			}
		).insert()
		# Pin the rate so totals don't depend on an exchange-rate API.
		doc.db_set("exchange_rate", extra.get("exchange_rate", 1))
		return doc

	def _task(self, deal, title, due_date=None, status="Todo", **extra):
		return frappe.get_doc(
			{
				"doctype": "CRM Task",
				"title": title,
				"status": status,
				"due_date": due_date,
				"reference_doctype": "CRM Deal",
				"reference_docname": deal.name,
				**extra,
			}
		).insert()

	def _contact(self, first_name):
		return frappe.get_doc({"doctype": "Contact", "first_name": first_name}).insert()

	def _link_contacts(self, deal, *rows):
		"""rows: (contact, is_primary). Written directly, without the CRM's primary-contact logic."""
		for idx, (contact, is_primary) in enumerate(rows, start=1):
			frappe.get_doc(
				{
					"doctype": "CRM Contacts",
					"parenttype": "CRM Deal",
					"parentfield": "contacts",
					"parent": deal.name,
					"idx": idx,
					"contact": contact.name,
					"full_name": contact.first_name,
					"is_primary": is_primary,
				}
			).db_insert()

	def _meta(self, **kw):
		return board_meta(
			"CRM Deal",
			"status",
			filters={"organization": self.org.name},
			names=[d.name for d in self.deals],
			**kw,
		)

	def test_column_totals_cover_filtered_deals(self):
		meta = self._meta()
		self.assertEqual(meta["columns"][self.open_status], {"total": 2000.0, "count": 2})
		self.assertEqual(meta["columns"][self.won_status], {"total": 4500.0, "count": 1})

	def test_board_total_excludes_won_and_lost(self):
		board = self._meta()["board"]
		self.assertEqual((board["total"], board["count"]), (2000.0, 2))

	def test_other_currency_converted_with_stored_rate(self):
		self.deals.append(self._deal(1000, self.open_status, exchange_rate=0.5))
		self.assertEqual(self._meta()["columns"][self.open_status]["total"], 2500.0)

	def test_deal_value_used_when_expected_value_empty(self):
		deal = self._deal(0, self.open_status, deal_value=700)
		self.deals.append(deal)
		meta = self._meta()
		self.assertEqual(meta["columns"][self.open_status]["total"], 2700.0)
		self.assertEqual(meta["cards"][deal.name]["value"], 700)

	def test_next_step_is_earliest_open_task_with_undated_last(self):
		deal = self.deals[0]
		self._task(deal, "No date")
		self._task(deal, "Later", "2030-01-10 09:00:00")
		self._task(deal, "Done already", "2020-01-01 09:00:00", status="Done")
		self._task(deal, "Canceled", "2020-01-01 09:00:00", status="Canceled")
		self._task(deal, "Soonest", "2030-01-05 09:00:00")
		step = self._meta()["cards"][deal.name]["next_step"]
		self.assertEqual(step["title"], "Soonest")

	def test_undated_task_used_when_no_dated_task(self):
		deal = self.deals[1]
		self._task(deal, "Call back")
		step = self._meta()["cards"][deal.name]["next_step"]
		self.assertEqual((step["title"], step["due_date"]), ("Call back", None))

	def test_card_fields(self):
		cards = self._meta()["cards"]
		self.assertEqual(cards[self.deals[0].name]["value"], 1200)
		self.assertFalse(cards[self.deals[0].name]["closed"])
		self.assertTrue(cards[self.deals[2].name]["closed"])
		self.assertIsNone(cards[self.deals[2].name]["next_step"])
		self.assertNotIn("organization", cards[self.deals[0].name])

	def test_title_falls_back_to_deal_id_not_organization(self):
		if frappe.get_meta("CRM Deal").has_field("custom_pipedrive_title"):
			self.deals[0].db_set("custom_pipedrive_title", None)
		self.assertEqual(self._meta()["cards"][self.deals[0].name]["title"], self.deals[0].name)

	def test_source_and_owner(self):
		source = frappe.get_all("CRM Lead Source", pluck="name", limit=1)
		if not source:
			source = [frappe.get_doc({"doctype": "CRM Lead Source", "source_name": "Board Test Source"}).insert().name]
		self.deals[0].db_set({"source": source[0], "deal_owner": "Administrator"})
		card = self._meta()["cards"][self.deals[0].name]
		self.assertEqual(card["source"], source[0])
		self.assertEqual(card["owner"]["name"], "Administrator")
		self.assertTrue(card["owner"]["full_name"])
		self.assertIn("image", card["owner"])

	def test_contact_is_primary_else_first(self):
		ana, ben = self._contact("Ana"), self._contact("Ben")
		self._link_contacts(self.deals[0], (ana, 0), (ben, 1))
		self._link_contacts(self.deals[1], (ana, 0), (ben, 0))
		cards = self._meta()["cards"]
		self.assertEqual(cards[self.deals[0].name]["contact"], "Ben")
		self.assertEqual(cards[self.deals[1].name]["contact"], "Ana")
		self.assertIsNone(cards[self.deals[2].name]["contact"])

	def test_next_step_has_assignee_and_plain_description(self):
		deal = self.deals[0]
		self._task(
			deal, "Call", "2030-01-05 09:00:00",
			assigned_to="Administrator", description="<p>Ask about&nbsp;<b>Q1</b></p><p>budget</p>",
		)
		step = self._meta()["cards"][deal.name]["next_step"]
		self.assertEqual(step["assigned_to"]["name"], "Administrator")
		self.assertEqual(step["description"], "Ask about Q1 budget")

	def test_other_doctypes_return_nothing(self):
		self.assertEqual(board_meta("CRM Lead", "status"), {})

	def test_unknown_column_field_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			board_meta("CRM Deal", "no_such_field")
