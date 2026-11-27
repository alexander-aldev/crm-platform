# crm-patches: the frontend extension interface for Frappe CRM

These patches are the only changes we make to `apps/crm`. They add a **generic extension interface** to the CRM frontend, and notes on tasks with a title suggestion hook, and nothing Másquetú-specific. All Másquetú code (theme, deal card, column totals, board header) is in `crm_platform` and plugs into named extension points. The patches are written so they could go to `frappe/crm` upstream; once accepted, nothing is patched any more.

The patches live in one directory per upstream release, `crm-patches/<tag>/` (now only `v16.0.4`, on Frappe v16); the directory name is the tag they target. To apply a set to a checkout of `frappe/crm` at that tag:

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
| `<tag>/0003-task-notes.patch` | new `crm/api/task.py` and `TaskNotes.vue`; `crm/api/activities.py`, `crm_task.py`, `fcrm_note.py`, `NoteArea.vue`, `DoctypeModal.vue` | A note can be written on a task, and shows on the task's lead or deal. **No DocType or schema change** (see below) |
| `<tag>/0004-task-status-note-prompt.patch` | new `TaskStatusNoteModal.vue`, `utils/taskNoteTitle.js`, `composables/taskStatusNote.js`; `AllModals.vue`, `ViewControls.vue`, `DoctypeModal.vue`, `TextEditorControl.vue` | Changing a task's status asks for a note (skippable), with its title filled in from the deal, task, new status and contact. Calls the `crm_task_note_title` hook for a better title once there is text |

The tests of 0003 and 0004 are not in the patches but in `crm_platform/tests/crm_patches/` (see Testing a change).

## Notes on tasks (0003, 0004)

**No schema change.** A note written on a task is an ordinary `FCRM Note` whose `reference_doctype` is `CRM Task` and `reference_docname` the task. Nothing is added to a DocType or a table, so there is no migration, and a CRM upgrade that changes either DocType does not conflict with the patch. What this means:

- `get_linked_notes` (the lead and deal Notes tab and timeline) also returns the notes of the record's tasks, each with `task` and `task_title`. They follow the task if it moves to another record.
- The status change a note was written for is in its title ("Done, Follow up / ..."), not in a field, so a note card shows no status icon.
- Deleting a task re-points its notes to its lead or deal (`CRMTask.on_trash`); a task with none takes its notes with it. Without that, the dynamic link would stop the delete.
- @mentions in a task note notify and link to the task's lead or deal.
- CRM's search index only covers notes on leads and deals, so task notes are not searchable. Contact and Organization pages don't use `get_linked_notes`, so they don't list task notes.

**Where a status change asks for a note:** the status menu on a lead or deal's Tasks tab, dragging a task on the Tasks board, and changing the status in the Task dialog. Not: list bulk edit, the desk, the API or imports. The dialog's Skip changes the status without a note; Cancel (or Esc) leaves it unchanged. `crm.api.task.set_status` writes the status and the note in one request, so both happen or neither.

**The title** is `{New status}, {Task} / {Deal}, {Contact}` (`utils/taskNoteTitle.js`), for example "Done, Follow up / Kuehne + Nagel, Shirish Ekbote". The status is the new one as it is, the task is its title tidied up, the deal is the organization of the task's deal or lead, and the contact is the deal's primary contact (a lead's person). A part that is not known is left out. A deal or contact name that the task's title also contains is taken out of the task part ("Follow up: Shirish Ekbote, Kuehne + Nagel" becomes "Follow up"), together with a dangling "with" or comma, and the task part is dropped if the names were all it said. The task is cut if the title would pass the note title's 140 characters. The dialog opens with the task and status and adds the deal and contact a moment later, from `crm.api.task.get_title_context`, unless the title has been edited by then. Once the note has 20 characters of text, a second after typing stops, the dialog calls `crm.api.task.suggest_note_title`; the answer replaces the task part ("Done, Budget frozen until Q3 / Kuehne + Nagel, Shirish Ekbote"), but only while nobody has edited the title. Names in the suggestion are taken out as in the task's title, and if nothing is left the task's title stays. The Notes section of the Task dialog starts a new note from the same title (without the suggestion), following the status as it is in the form until the title is edited.

### Server hook: `crm_task_note_title`

An app lists a function under `crm_task_note_title` in its `hooks.py` (the last one listed wins). It gets one dict and returns a short subject, or None:

| Key | What it is |
|---|---|
| `task` | `{name, title, due_date, priority}` |
| `status_from`, `status_to` | The change |
| `parent` | `{doctype, name, title, status}` of the task's lead or deal, or None |
| `names` | `{deal, contact}`, each maybe None: the names the title already says, so the subject need not |
| `content` | The note's text, without markup |

The CRM puts the subject in the title in place of the task, after the new status and before the deal and contact, so it should leave out all three. An error, a None or an empty string keeps the filled-in title and is logged; the dialog stops waiting after 4 seconds. `crm_platform` implements the hook (`crm_platform/api/note_title.py`).

Treat the hook's name and its dict as part of the contract, like the extension interface below.

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
| `kanban.card` | Replaces the card body; the card stays a link to the record and stays draggable. Since v16.0.4 the link is an overlay under the body: clicks on the component fall through to it, except on buttons, links and tooltip triggers (`[data-slot=trigger]`) | `board`, `column` (name), `item` (the record as loaded for the board) |

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
- The card's markup: `masquetu-crm.css` styles `[data-part="card"]`, its `> a` link overlay and the `kanban.card` root as a direct child (`:has(> .mq-deal)`).

From CRM v16 the frontend imports Frappe's own UI source (`@framework/ui`, resolved to `../../frappe/ui/src`), so a plain clone of `frappe/crm` only builds with a `frappe/frappe` checkout of the matching v16 release beside it (`<dir>/crm`, `<dir>/frappe`), as in a bench's `apps/`.

## Testing a change

1. `git apply --check` each patch against a clean checkout of the tag.
2. `bench build --app crm`, open `/crm/deals/view/kanban`, and compare with `docs/kanban/*.png` at 1440px and 390px wide, in light and dark mode.
3. Open a board with no extension (Leads): it should look like upstream, plus the theme.
4. Drag a card between columns, use "Load More", and open the `+` menu on a deal card (New Note, New Task).
5. `node --test crm_platform/tests/js/*.test.mjs crm_platform/tests/crm_patches/*.test.mjs` (set `CRM_FRONTEND` to `apps/crm/frontend`) and `bench --site <site> run-tests --app crm_platform`. The tests of 0003 and 0004 are in `crm_platform/tests/crm_patches/`, so a bench without those patches skips the Python ones.
6. Tasks (0003, 0004), on a deal with a task: change its status from the Tasks tab (Done, then Skip, then Cancel), drag it on `/crm/tasks/view/kanban` (Cancel puts the card back), and change the status in the Task dialog. Write a note with text: with `masquetu_note_title_url` set to `mock` the title becomes the note's first words, unless you edited it first. The note shows in the deal's Notes tab with a "↳ task" line. Delete a task that has notes: they stay on the deal.
7. `bench --site <site> migrate` reports no change to `FCRM Note` or `CRM Task`.
