"""Brand the CRM as Másquetú through FCRM Settings.

Done in code rather than as a fixture: FCRM Settings is a Single, and a fixture
would overwrite every other setting on the site with the exported values.
"""

from pathlib import Path

import frappe

BRAND_NAME = "Másquetú"
IMAGES = Path(__file__).parent / "public" / "images"


def apply():
	settings = frappe.get_single("FCRM Settings")
	settings.brand_name = BRAND_NAME
	# Only point at brand images once they exist in public/images/.
	if (IMAGES / "logo.svg").exists():
		settings.brand_logo = "/assets/crm_platform/images/logo.svg"
	if (IMAGES / "favicon.png").exists():
		settings.favicon = "/assets/crm_platform/images/favicon.png"
	settings.flags.ignore_permissions = True
	settings.save()
