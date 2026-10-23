# crm_platform

The Másquetú companion app for Frappe CRM: a sibling app installed next to `crm` on every site. For now it holds the theme, the Kanban deal card and the board data behind it. Seat limits, deal aging and webhooks to the Másquetú platform come later.

It reaches the CRM frontend through the extension interface added by `crm-patches/` (see `crm-patches/README.md` for the API and extension points).

## Repository layout

| Path | What it is |
|---|---|
| `crm_platform/` | The Frappe app (Python package, hooks, public assets, tests) |
| `crm-patches/` | The reviewed patch sets for `apps/crm`, one directory per upstream tag (`crm-patches/<tag>/`) |
| `scripts/` | `gen_theme_tokens.py` (theme tokens) |
| `docs/` | The deal card spec and the Kanban design reference (`docs/kanban/`) |

## The app

| Path | What it is |
|---|---|
| `crm_platform/public/js/masquetu.js` | The Másquetú frontend extension: adds the stylesheet and registers the deal card (activity state, chips, owner, next-activity pop-up), column totals and board header for `CRM Deal`. A plain ES module, no build step |
| `crm_platform/public/css/masquetu-crm.css` | The theme: fonts, accent, and the board and deal card from `docs/kanban/`. Applies to light and dark mode |
| `crm_platform/public/css/_tokens.generated.css` | frappe-ui's light gray tokens re-pointed at the Másquetú warm ramp. Generated; don't edit |
| `crm_platform/extensions.py` | `update_website_context` hook: lists the apps' `crm_frontend_extensions` modules in the `/crm` page |
| `crm_platform/api/kanban.py` | `board_meta`: column totals, and per deal card the title, lead source, owner, primary contact and earliest open task (spec: `docs/deal-card-activity-indicator.md`) |
| `crm_platform/branding.py` | Sets the brand name in FCRM Settings on install and migrate, plus the logo and favicon once `public/images/logo.svg` and `favicon.png` exist |

## Installing

On a bench running Frappe CRM at a tag that has a `crm-patches/<tag>/` directory:

```bash
git -C apps/crm apply $(ls <path-to>/crm-patches/<tag>/*.patch)   # the extension interface, see crm-patches/README.md
bench get-app crm_platform <path-to-this-repository>
bench --site <site> install-app crm_platform
bench build --app crm
```

Changes to `public/js` or `public/css` need only a browser reload when the bench serves this folder through a symlink: the module URL carries the newest file time as its version.

## Tests

```bash
bench --site <site> run-tests --app crm_platform                           # board data (Python)
CRM_FRONTEND=<bench>/apps/crm/frontend node --test crm_platform/tests/js/*.test.mjs   # card formatting (JS)
```

## After a frappe-ui upgrade

```bash
python3 scripts/gen_theme_tokens.py \
    <bench>/apps/crm/frontend/node_modules/frappe-ui/tailwind/generated/colors.json
```

## Licence

AGPL-3.0, the same as Frappe CRM. See `LICENSE`. The Másquetú name and logo are not covered by it: see `TRADEMARKS.md`.
