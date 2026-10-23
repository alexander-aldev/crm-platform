# crm-patches: the frontend extension interface for Frappe CRM

These patches are the only changes we make to `apps/crm`. They add a **generic extension interface** to the CRM frontend and nothing Másquetú-specific. All Másquetú code (theme, deal card, column totals, board header) is in `crm_platform` and plugs into named extension points. The patches are written so they could go to `frappe/crm` upstream; once accepted, nothing is patched any more.

The patches live in one directory per upstream release, `crm-patches/<tag>/` (now `v1.84.0`); the directory name is the tag they target. To apply a set to a checkout of `frappe/crm` at that tag:

```bash
cd apps/crm
git checkout <tag>
for p in <path-to>/crm-patches/<tag>/*.patch; do git apply --check "$p" && git apply "$p"; done
cd ../.. && bench build --app crm
```

Patches are applied once, when a bench or image is built, never to a running one. To change the set, rebuild from a clean checkout of the tag.

Why patch at all: the CRM frontend is a standalone Vue SPA with no plugin mechanism, so a companion app can't reach it. The alternative to a full fork: patch once, deliberately, as a small reviewed set.

## The patches

| Patch | Files | What it does |
|---|---|---|
| `<tag>/0001-frontend-extensions.patch` | new `src/extensions.js`, `src/main.js` | Before the app mounts, imports every module listed in `window.crm_extensions` and calls its default export with a versioned API (below). A module that fails or takes over 5s is skipped; the CRM still starts |
| `<tag>/0002-kanban-extension-points.patch` | `components/Kanban/KanbanView.vue` | Extension points `kanban.board-head`, `kanban.column-meta`, `kanban.card`, resolved per doctype; without a registered extension the board renders as before. Stable `data-part` attributes for styling |

## The extension interface (version 1)

**Loading.** An app lists modules in a `crm_frontend_extensions` hook. `crm_platform`'s `update_website_context` hook (`crm_platform/extensions.py`) puts them into the `/crm` page's boot data as `window.crm_extensions`, each with a `?v=` cache-busting parameter. This needs no server-side patch.

**API passed to each module's default export:**

| Member | What it is |
|---|---|
| `version` | `1`. Check it and do nothing on an unknown version |
| `register(point, component, { doctype })` | Register a component for an extension point; `doctype` omitted means every doctype |
| `vue` | The CRM's own Vue module. Use it instead of bundling Vue |
| `ui` | frappe-ui: `Avatar`, `Badge`, `Button`, `Dropdown`, `Tooltip`, `call`, `createResource`, `dayjs`, `dayjsLocal` |
| `services.showModal(options)` | The CRM's create/edit dialog (`{ doctype, title, defaults, callbacks }`) |
| `services.translate(message, args)` | The CRM's `__()` |

**Extension points and the props they receive:**

| Point | Where | Props |
|---|---|---|
| `kanban.board-head` | Above the columns | `board` |
| `kanban.column-meta` | In each column header, before the column tools | `board`, `column: { name, count, allCount }` |
| `kanban.card` | Replaces the card body; the card stays a link to the record and stays draggable | `board`, `column` (name), `item` (the record as loaded for the board) |

`board` is `{ doctype, columnField, filters, defaultFilters, columns: [{ name, count, allCount, items: [record names] }] }`, a new object whenever the board reloads.

**Styling hooks** (`data-part`): `board`, `board-scroll`, `columns`, `column`, `column-head`, `column-title`, `column-color`, `column-action`, `cards`, `card`.

Treat this table as the contract: changing a name or a prop breaks extensions, so bump `version` when you do.

## Rebasing onto a new CRM release

On a bench (or a plain clone of `frappe/crm`):

```bash
cd apps/crm
git fetch --depth 1 upstream refs/tags/<new-tag>:refs/tags/<new-tag>
git checkout -b extensions <new-tag>
for p in <path-to>/crm-patches/<old-tag>/*.patch; do git am --3way "$p" || break; done
# fix any conflicts, `git am --continue`, then rebuild and test (below)
git format-patch <new-tag>..extensions --zero-commit --no-signature -o /tmp/new-patches
```

Rename the generated files to the names above and put them in a new `crm-patches/<new-tag>/`. Keep the old directory while deployments still run the old tag; remove it once none do. (Másquetú: also record the move in the platform repo's `docs/baseline.md`.)

What to re-check after a rebase:

- `KanbanView.vue` still gets `params.doctype`, `params.filters`, `params.default_filters` and `data.column_field` from its model (the `board` object is built from them).
- `useDoctypeModal().showModal` and the frappe-ui exports listed above still exist.
- frappe-ui: if it was bumped, re-run `scripts/gen_theme_tokens.py`, and check that the solid button is still `bg-surface-gray-10` (see the primary-button rule in `masquetu-crm.css`).

## Testing a change

1. `git apply --check` each patch against a clean checkout of the tag.
2. `bench build --app crm`, open `/crm/deals/view/kanban`, and compare with `docs/kanban/*.png` at 1440px and 390px wide, in light and dark mode.
3. Open a board with no extension (Leads): it should look like upstream, plus the theme.
4. Drag a card between columns, use "Load More", and open the `+` menu on a deal card (New Note, New Task).
5. `node --test crm_platform/tests/js/*.test.mjs` (set `CRM_FRONTEND` to `apps/crm/frontend`) and `bench --site <site> run-tests --app crm_platform`.
