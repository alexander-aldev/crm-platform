"""Tell the CRM frontend which extension modules to load.

The CRM page (/crm, rendered from crm/www/crm.html) writes every key of its
`boot` dict into `window`, and Frappe runs `update_website_context` hooks after
the page's own get_context. So without touching the CRM, this hook adds
`window.crm_extensions`: the URLs that crm-patches/0001 imports before the app
mounts.

Any installed app can contribute modules through a `crm_frontend_extensions`
hook (a list of /assets/... URLs). Each URL gets a version parameter: the newest
modification time of anything in that app's public folder, so a change to a
module or to a stylesheet it loads reaches browsers without a cache flush.
"""

import os

import frappe


def add_crm_extensions(context):
	boot = context.get("boot")
	request = getattr(frappe.local, "request", None)
	if not isinstance(boot, dict) or not request or not request.path.startswith("/crm"):
		return
	boot["crm_extensions"] = [_versioned(url) for url in frappe.get_hooks("crm_frontend_extensions")]


def _versioned(url):
	"""/assets/<app>/<path> -> /assets/<app>/<path>?v=<newest mtime in the app's public folder>."""
	parts = url.split("/", 3)  # ["", "assets", app, path]
	if len(parts) == 4 and parts[1] == "assets":
		try:
			public = frappe.get_app_path(parts[2], "public")
			newest = max(
				os.path.getmtime(os.path.join(root, name))
				for root, _, files in os.walk(public)
				for name in files
			)
			return f"{url}?v={int(newest)}"
		except Exception:
			pass
	return url
