# Deal card: activity rotting indicator

**Status:** deal card (§2, §3, §5) implemented 2026-10-22 (roadmap B.6). The lead source field (§4, roadmap B.7) is not built yet: until it is, the card shows the deal's existing lead source and no direction chip
**Applies to:** the deal card on the Kanban board (`crm_platform/public/js/masquetu.js`, `crm_platform/public/css/masquetu-crm.css`) and a new two-level lead source field (§4)
**Style source of truth:** the Másquetú design system (`--mq-*` tokens) and `docs/kanban/` (referred to below as "the kit")
**Note:** references to requirements and roadmap sections point to Másquetú's internal planning documents, which are not published
**Visual reference:** the "event highlight" mockup, option A (chip above the title) only

## 1. Purpose

Show on each deal card, at a glance, whether the deal has a next activity and whether that activity is on time. The signal is an accent border on the card's left edge, plus the next-activity text in the same colour.

This is separate from the **stage-inactivity rotting** in requirements §1.2 and §3.4 (`days_in_stage` / `is_rotting`, roadmap B.1–B.3). The left border is reserved for activity state only. Stage rotting needs its own treatment and must not use this border.

## 2. Activity states

The deal's **next activity** is its earliest open CRM Task: soonest due date first, undated tasks last. This is the same rule `board_meta` uses today. "Today" means the calendar day in the user's timezone, as the current card does. A due date at exactly midnight counts as a date without a time: it stays on its calendar day and is not converted between timezones. Converted, it would land on the previous day for users west of the server's timezone.

| State | Condition | Left border | Activity text colour | Activity text |
|---|---|---|---|---|
| All good | Next activity due after today | none | `--mq-muted` (grey) | `Call client · 27 Jan` |
| Due today | Next activity due today | green | green text token | `Demo · today 15:00` |
| Nothing scheduled | No open activity, **or** the next activity has no due date | amber | amber text token | `Nothing scheduled` / `Send deck · no date` |
| Overdue | Next activity due before today | red | red text token | `Call client · overdue 2d` |
| Closed | Deal status is Won or Lost | none | `--mq-muted` | `Closed` (no pop-up) |

**Agreements with the prospect** (for example "call back after 15 January") are recorded as a follow-up activity (a CRM Task) due on the agreed date. They need no special rule: the follow-up becomes the next activity once the old task is closed or rescheduled.

An undated task appears under Nothing scheduled only when it is the deal's next activity. A deal with a dated task as well shows that task's state instead.

## 3. Card anatomy (top to bottom)

These rules extend the kit's deal card (`.mq-deal`): white card, 1px `--mq-line` border, radius `--mq-radius-sm` (8px), padding 12px, 6px between rows, `--mq-line-hover` border on hover.

| # | Element | Content | Style (kit tokens) |
|---|---|---|---|
| 0 | **Chips row** | Lead source chip, then direction chip (§3.1). The row is hidden when the deal has no lead source | See §3.1 |
| 1 | **Opportunity name** | Deal title: `custom_pipedrive_title` for now, else the deal ID. To be replaced by a custom deal title field (§7) | Manrope 600 14px, `--mq-ink`, wraps. The largest text on the card |
| 2 | **Contact name** | The deal's primary contact, else its first linked contact. The line is hidden when there is none | Manrope 400 13px, `--mq-muted`, one line with ellipsis |
| 3 | **Footer row** | Owner avatar, deal value, next activity | See §3.2 |

The organization is **not** shown on the card. The title no longer falls back to the organization name.

### 3.1 Chips

- **Lead source chip:** the specific name if set (`Acme Expo 2026`), otherwise the lead source (`LinkedIn`). The tooltip shows the full path (`Conference › Acme Expo 2026`).
- **Direction chip:** `↓ Inbound` / `↑ Outbound`, derived automatically (§4). The arrow keeps the two apart without colour.
- Shape: kit badge (`.mq-badge`) geometry: radius `--mq-radius-pill`, padding 2px 8px.
- Type: `--mq-mono` 500, 11px, sentence case (names such as "LinkedIn" read better that way).
- Colour: neutral only. Background `--mq-column-bg` (#F3F3F2), text `--mq-ink-2` (contrast 10.5:1). Chips never use flame, red, green or amber, so they cannot be mistaken for the activity state. The flame `.mq-badge` fill is for marketing badges, not data.
- Layout: chips sit in one row 4px apart and wrap if needed. A single chip shows an ellipsis at full card width.
- The card's note/task menu (`.mq-deal__menu`, top right) overlaps the chips row instead of the title. Move the touch-screen `padding-right: 24px` from `.mq-deal__title` to the chips row, or to the title when the row is hidden.
- **TODO (later):** filter the board by lead source, specific name and direction by clicking a chip or through the board filter. Not in this iteration.

### 3.2 Footer row

Left to right, aligned on the baseline, 8px gap:

1. **Owner avatar** (`deal_owner`): 20px circle. Shows the user's photo if set. Otherwise initials in Manrope 700 10px, `--mq-ink-2` on `--mq-column-bg`. The tooltip and `aria-label` give the full name. Omitted when the deal has no owner.
2. **Value:** kit `.mq-deal__value`: `--mq-mono` 500 12px, `--mq-ink`, never truncated. Formatting stays as today (`€12,000`, `€0`).
3. **Next activity:** pushed to the right edge. Manrope 12px, coloured by state (§2). The text is `<task title> · <when>`; the task title stands in for the activity type for now (§7). The title truncates with an ellipsis, while the `· when` part (`· 27 Jan`, `· overdue 2d`, `· no date`) always stays visible. When the activity doesn't fit beside the value with at least 4.5em of title (2.5em on cards narrower than 180px), it wraps to its own line under the value. On phone-width cards the title takes whatever room is left. Date format: weekday for the next 6 days (`Fri`), else `D MMM`, adding the year when it is not the current year. This element opens the pop-up (§5).

### 3.3 Accent border

- A 4px stripe on the card's left edge, full height, clipped by the card's 8px radius. The 1px `--mq-line` border on the other sides is unchanged.
- To keep text from shifting between states, every deal card gets 16px left padding (the kit's 12px plus the stripe). The stripe is transparent in the All good and Closed states.
- The stripe stays visible on hover, focus and while dragging.

### 3.4 New colour tokens

The kit has no status colours, and its only warning colour (`--mq-due` / `--mq-flame-text`, #B4500F) is a brand orange. That colour is retired on the deal card, because next to amber the two oranges would read as the same state. Add these tokens to `masquetu-crm.css` and to the kit's `masquetu-design-system.css`:

| Token | Light | Contrast on white | Dark | Used for |
|---|---|---|---|---|
| `--mq-status-overdue` | #D92D20 | 4.8:1 | #FF6369 | red stripe |
| `--mq-status-overdue-text` | #B42318 | 6.6:1 | #FF6369 | red activity text |
| `--mq-status-today` | #16A34A | 3.3:1 | #3DD68C | green stripe |
| `--mq-status-today-text` | #15803D | 5.0:1 | #3DD68C | green activity text |
| `--mq-status-none` | #C28B00 | 3.0:1 | #FFB224 | amber stripe |
| `--mq-status-none-text` | #92600A | 5.4:1 | #FFB224 | amber activity text |

- Stripes need at least 3:1 (WCAG 1.4.11) and text at least 4.5:1 (WCAG AA, requirements §2.6). The light values above meet both.
- The amber is a yellow amber, chosen so it is not mistaken for flame #FF8A2B. Flame is also the focus outline colour.
- The dark values meet 4.5:1 against an assumed card background of #1F1F1F. Check them against the real dark `--mq-card-bg` (frappe-ui `--surface-gray-2`) before shipping.

## 4. Lead source field (two levels, with direction)

A custom field that records where the deal came from at two levels:

| Level | What it is | Examples | Stored in |
|---|---|---|---|
| 1. Lead source | The channel | Conference, LinkedIn, Referral, Website, Cold email | The CRM's existing `CRM Lead Source` doctype. The deal's existing `source` field keeps pointing at it |
| 2. Specific name | The particular event, campaign or referrer. Optional | Acme Expo 2026, Brussels Expo 2026 | A new doctype in `crm_platform`, e.g. `Lead Source Detail`: name (unique, case-insensitive) and parent lead source (required) |

**Direction (Inbound/Outbound)** is classified automatically:

- Each lead source has a default direction, held in a new custom Select field on `CRM Lead Source`.
- A specific name may override it. For example, a conference can be inbound when people came to our booth and outbound when we went looking.
- The deal's `direction` is read-only and is recalculated whenever the lead source or specific name changes.

**Input (deal and lead forms):**

- One field with autocomplete. Typing searches specific names and lead sources together, case-insensitively, and lists results as `Conference › Acme Expo 2026`.
- Choosing a specific name sets both levels. Choosing a lead source sets level 1 only and leaves the specific name empty.
- A new name that matches nothing offers **Create "…"**. That option asks the user to pick one of the existing lead sources before the name is saved, so every specific name belongs to a lead source. Users cannot create lead sources from this field; Admins manage those.
- The direction is shown read-only beside the field.
- The fields exist on both CRM Lead and CRM Deal with the same names, so they carry over when a lead is converted to a deal.

**Existing data:** the Pipedrive migration already maps "Leadsource" to `source` (`imports/pipedrive/LOGIC.md`). Those deals get level 1 and a direction, with the specific name left empty.

## 5. Next-activity pop-up

- **Opens** on click or tap on the footer's next-activity text, or Enter/Space when it has keyboard focus. It is a real `<button>`. Pressing it must not start a card drag or open the deal.
- **Closes** on Esc or a click outside, and Esc returns focus to the trigger. While the board scrolls, the pop-up follows its card, and it closes once the card is out of view.
- **Content when there is an activity:** full task title, due date and time (`Tue 27 Jan 2027, 10:00`, or "No due date"), assignee, and the first 3 lines of the description. One action: **Open task**, which opens the CRM's task modal.
- **Content when nothing is scheduled:** the text "Nothing scheduled" and a **Schedule an activity** link. The link opens the CRM's new-task modal already linked to the deal, with the owner preset to the deal owner.
- **Style:** kit panel: `--mq-card-bg`, 1px `--mq-line`, radius `--mq-radius-sm`, padding 12px, max width 280px. Title in Manrope 600 14px `--mq-ink`, meta in Manrope 400 12px `--mq-muted`, link in `--mq-link`.
- Phones use the same pop-up, anchored to the card and kept inside the viewport.

## 6. Accessibility and data

**Accessibility:**

- Colour is never the only signal: every state has its own text (`overdue 2d`, `today`, `no date`, `Nothing scheduled`).
- The card's accessible name includes the state, for example "Euro Trans GmbH, overdue 2 days".
- The pop-up trigger is keyboard reachable and announces `aria-expanded`.

**Data:** `crm_platform/api/kanban.py` `_cards()` must also return, per deal:

- `source`, the specific name (§4) and `direction`
- `deal_owner`: full name and photo URL
- `contact`: the primary contact's full name
- `next_step`: also `assigned_to` and `description`, and a due **time** (CRM Task `due_date` is a datetime)
- `organization` is no longer needed by the card

Everything stays in the single `board_meta` call. There are no extra requests per card, which keeps the board within the 500-deals-in-1.5s budget (requirements §2.4).

## 7. Changes from the current card, and later work

**Changes:**

- The company line becomes the contact line. The organization is removed from the card, including as a title fallback.
- `.mq-deal__next--due` (flame text for due today and overdue) is replaced by the three state colours.
- The overdue text changes from `Overdue 2d` to `<title> · overdue 2d`.
- New: chips row, owner avatar, left stripe, pop-up, and the two-level lead source field.

**Later work:**

- Filtering by chip (§3.1).
- A custom deal title field that replaces `custom_pipedrive_title` as the opportunity name. Until then, deals created in the CRM (with no Pipedrive title) show their deal ID as the title.
- Activity type (`Call`, `Demo`, …) classified automatically from the task with ML. Until then, the task title is shown.
- Stage-inactivity rotting (requirements §3.4) is **not shown on the card** for the time being. If it is added later, it must not use the left border.
