app_name = "crm_platform"
app_title = "CRM Platform"
app_publisher = "Másquetú"
app_description = "Másquetú companion app for Frappe CRM: theme, board data and branding"
app_license = "AGPLv3"

required_apps = ["crm"]

# The CRM frontend is a standalone SPA, so app_include_* hooks don't reach it.
# Instead, update_website_context puts the modules listed under
# crm_frontend_extensions (by any app) into the /crm page, and the CRM loads them
# through its extension interface (crm-patches/0001, src/extensions.js).
update_website_context = "crm_platform.extensions.add_crm_extensions"

# Másquetú theme, deal card, column totals and board header
crm_frontend_extensions = ["/assets/crm_platform/js/masquetu.js"]

after_install = "crm_platform.branding.apply"
after_migrate = "crm_platform.branding.apply"
