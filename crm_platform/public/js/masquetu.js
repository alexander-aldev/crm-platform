// Másquetú extension for Frappe CRM: theme stylesheet, deal card, column totals
// and board header. Spec: docs/kanban/README.md and, for the deal
// card, docs/deal-card-activity-indicator.md.
//
// Loaded through the CRM's frontend extension interface (crm-patches/0001,
// apps/crm/frontend/src/extensions.js), listed by crm_platform's
// `crm_frontend_extensions` hook. A plain ES module with no build step: the
// components are render functions on the CRM's own Vue and frappe-ui, which the
// interface passes in. Styles live in ../css/masquetu-crm.css.

const STYLESHEET = '../css/masquetu-crm.css'
const BOARD_META = 'crm_platform.api.kanban.board_meta'
const DEALS = { doctype: 'CRM Deal' }

export default function setup(api) {
  if (api.version !== 1) {
    console.warn('[masquetu] unsupported extension API version', api.version)
    return
  }
  addStylesheet()
  const fmt = makeFormatters({
    dayjsLocal: api.ui.dayjsLocal,
    translate: api.services.translate,
  })
  const store = makeBoardStore(api)
  api.register('kanban.board-head', boardHead(api, store, fmt), DEALS)
  api.register('kanban.column-meta', columnTotal(api, store, fmt), DEALS)
  api.register('kanban.card', dealCard(api, store, fmt), DEALS)
}

// The stylesheet sits next to this module; reuse its ?v= so both refresh together.
function addStylesheet() {
  if (document.querySelector('link[data-masquetu]')) return
  const here = new URL(import.meta.url)
  const href = new URL(STYLESHEET, here)
  href.search = here.search
  const link = document.createElement('link')
  link.rel = 'stylesheet'
  link.href = href.toString()
  link.dataset.masquetu = ''
  document.head.appendChild(link)
}

// ---------- Board data: totals and per-card data (crm_platform.api.kanban) ----------

function makeBoardStore({ vue, ui }) {
  const state = vue.reactive({ meta: null })
  let latest = 0
  let lastBoard = null

  async function load(board) {
    if (!board?.columnField) return
    lastBoard = board
    const request = ++latest
    try {
      const meta = await ui.call(BOARD_META, {
        doctype: board.doctype,
        column_field: board.columnField,
        filters: board.filters,
        default_filters: board.defaultFilters,
        names: board.columns.flatMap((column) => column.items),
      })
      if (request === latest) state.meta = meta
    } catch (error) {
      console.error('[masquetu] board data:', error)
    }
  }

  return { state, load, reload: () => load(lastBoard) }
}

// ---------- Components ----------

function boardHead({ vue, services }, store, fmt) {
  const { defineComponent, h, watch } = vue
  return defineComponent({
    name: 'MasquetuBoardHead',
    props: { board: { type: Object, required: true } },
    setup(props) {
      // `board` is a new object whenever the board reloads (filters, drag and drop, load more)
      watch(() => props.board, (board) => store.load(board), { immediate: true })
      return () => {
        const board = store.state.meta?.board
        if (!board) return null
        const __ = services.translate
        const total = fmt.value(board.total, board.currency)
        return h('div', { class: 'mq-board__head' }, [
          h('p', { class: 'mq-board__meta' }, [
            h('span', { class: 'mq-board__meta-full' },
              __('Open value {0} · {1} deals', [total, board.count])),
            h('span', { class: 'mq-board__meta-short' },
              __('{0} · {1} deals', [total, board.count])),
          ]),
        ])
      }
    },
  })
}

function columnTotal({ vue }, store, fmt) {
  const { defineComponent, h } = vue
  return defineComponent({
    name: 'MasquetuColumnTotal',
    props: {
      board: { type: Object, required: true },
      column: { type: Object, required: true },
    },
    setup(props) {
      return () => {
        const meta = store.state.meta
        if (!meta?.board) return null
        const total = meta.columns?.[props.column.name]?.total || 0
        return h('span', { class: 'mq-column__sum' }, fmt.compact(total, meta.board.currency))
      }
    },
  })
}

function dealCard({ vue, ui, services }, store, fmt) {
  const { defineComponent, h, computed } = vue
  const __ = services.translate
  const stop = (event) => {
    // the card is a link to the deal; the menu must not navigate
    event.stopPropagation()
    event.preventDefault()
  }

  function addTo(doctype, title, deal, defaults = {}) {
    services.showModal({
      doctype,
      title,
      defaults: { reference_doctype: 'CRM Deal', reference_docname: deal, ...defaults },
      callbacks: { afterInsert: store.reload, afterUpdate: store.reload },
    })
  }

  const NextActivity = nextActivity({ vue, services }, store, fmt, addTo)

  function chip(c) {
    return h('span', {
      class: ['mq-chip', `mq-chip--${c.kind}`],
      title: c.tooltip || undefined,
    }, c.text)
  }

  function avatar(owner) {
    return h('span', {
      class: 'mq-avatar',
      title: owner.full_name,
      role: 'img',
      'aria-label': owner.full_name,
    }, owner.image
      ? h('img', { src: owner.image, alt: '', loading: 'lazy' })
      : fmt.initials(owner.full_name))
  }

  return defineComponent({
    name: 'MasquetuDealCard',
    props: {
      board: { type: Object, required: true },
      column: { type: String, required: true },
      item: { type: Object, required: true },
    },
    setup(props) {
      const meta = computed(() => store.state.meta?.cards?.[props.item.name])
      const card = computed(() => fmt.card(props.item, meta.value))
      const actions = computed(() => [
        { label: __('New Note'), icon: 'file-text', onClick: () => addTo('FCRM Note', 'Note', props.item.name) },
        { label: __('New Task'), icon: 'check-square', onClick: () => addTo('CRM Task', 'Task', props.item.name) },
      ])
      return () => {
        const c = card.value
        const title = h('p', { class: 'mq-deal__title' }, c.title)
        const chips = c.chips.length
          ? h('div', { class: 'mq-deal__chips' }, c.chips.map(chip))
          : null
        const menu = h(ui.Dropdown, { options: actions.value, onClick: stop }, {
          default: () => h(ui.Button, {
            class: 'mq-deal__menu',
            icon: 'lucide-plus',
            variant: 'ghost',
            size: 'sm',
            'aria-label': __('Add a note or task'),
          }),
        })
        return h('div', { class: ['mq-deal', c.next && `mq-deal--${c.next.state}`] }, [
          // The menu sits in the card's corner, over the first row
          h('div', { class: 'mq-deal__top' }, [chips || title, menu]),
          chips ? title : null,
          c.contact ? h('p', { class: 'mq-deal__contact' }, c.contact) : null,
          h('div', { class: 'mq-deal__foot' }, [
            c.owner ? avatar(c.owner) : null,
            h('span', { class: 'mq-deal__value' }, c.value),
            c.next
              ? h(NextActivity, { deal: props.item.name, next: c.next, step: meta.value?.next_step, owner: c.owner })
              : null,
          ]),
        ])
      }
    },
  })
}

// The footer's next activity and its pop-up (spec §5). The pop-up is teleported
// to <body>, so clicks in it never reach the card link or the drag handler. It
// follows its card while the board scrolls (a click can itself scroll the card
// into view) and closes once the card is out of view.
function nextActivity({ vue, services }, store, fmt, addTo) {
  const { defineComponent, h, ref, nextTick, onBeforeUnmount, Teleport } = vue
  const __ = services.translate
  const GAP = 4
  const MARGIN = 8

  return defineComponent({
    name: 'MasquetuNextActivity',
    props: {
      deal: { type: String, required: true },
      next: { type: Object, required: true },
      step: { type: Object, default: null },
      owner: { type: Object, default: null },
    },
    setup(props) {
      const open = ref(false)
      const trigger = ref(null)
      const panel = ref(null)
      const position = ref({ top: 0, left: 0 })

      function place() {
        const t = trigger.value?.getBoundingClientRect()
        const p = panel.value
        if (!t || !p) return
        if (t.bottom < 0 || t.top > window.innerHeight || t.right < 0 || t.left > window.innerWidth) {
          hide()
          return
        }
        const { offsetWidth: w, offsetHeight: ph } = p
        const below = t.bottom + GAP
        const top = below + ph > window.innerHeight - MARGIN && t.top - GAP - ph > MARGIN
          ? t.top - GAP - ph
          : below
        const left = Math.min(Math.max(MARGIN, t.right - w), window.innerWidth - w - MARGIN)
        position.value = { top, left }
      }

      function show() {
        open.value = true
        document.addEventListener('pointerdown', onOutside, true)
        document.addEventListener('keydown', onKey, true)
        window.addEventListener('scroll', place, true)
        window.addEventListener('resize', place)
        nextTick(() => {
          place()
          panel.value?.focus({ preventScroll: true })
        })
      }

      function hide({ refocus = false } = {}) {
        if (!open.value) return
        open.value = false
        document.removeEventListener('pointerdown', onOutside, true)
        document.removeEventListener('keydown', onKey, true)
        window.removeEventListener('scroll', place, true)
        window.removeEventListener('resize', place)
        if (refocus) trigger.value?.focus()
      }

      function onOutside(event) {
        if (panel.value?.contains(event.target) || trigger.value?.contains(event.target)) return
        hide()
      }

      function onKey(event) {
        if (event.key !== 'Escape') return
        event.stopPropagation()
        hide({ refocus: true })
      }

      function toggle(event) {
        // the card is a link to the deal: don't navigate
        event.preventDefault()
        event.stopPropagation()
        open.value ? hide() : show()
      }

      // A press on the trigger must not start dragging the card
      const keep = (event) => event.stopPropagation()

      function then(action) {
        hide()
        action()
      }

      function openTask() {
        services.showModal({
          doctype: 'CRM Task',
          name: String(props.step.task),
          title: 'Task',
          callbacks: { afterInsert: store.reload, afterUpdate: store.reload },
        })
      }

      function schedule() {
        addTo('CRM Task', 'Task', props.deal, props.owner ? { assigned_to: props.owner.name } : {})
      }

      onBeforeUnmount(() => hide())

      function content() {
        const step = props.step
        if (!step) {
          return [
            h('p', { class: 'mq-pop__title' }, __('Nothing scheduled')),
            h('button', { type: 'button', class: 'mq-pop__action', onClick: () => then(schedule) },
              __('Schedule an activity')),
          ]
        }
        const details = fmt.activityDetails(step)
        return [
          h('p', { class: 'mq-pop__title' }, details.title),
          h('p', { class: 'mq-pop__meta' }, details.due),
          details.assignee
            ? h('p', { class: 'mq-pop__meta' }, __('Assigned to {0}', [details.assignee]))
            : null,
          details.description ? h('p', { class: 'mq-pop__desc' }, details.description) : null,
          h('button', { type: 'button', class: 'mq-pop__action', onClick: () => then(openTask) },
            __('Open task')),
        ]
      }

      return () => {
        const next = props.next
        const parts = [
          next.title ? h('span', { class: 'mq-next__title' }, next.title) : null,
          next.title ? h('span', { class: 'mq-next__sep', 'aria-hidden': 'true' }, ' · ') : null,
          h('span', { class: 'mq-next__when' }, next.when),
        ]
        if (next.state === 'closed') {
          return h('span', { class: 'mq-deal__next mq-deal__next--closed' }, parts)
        }
        return [
          h('button', {
            ref: trigger,
            type: 'button',
            class: ['mq-deal__next', `mq-deal__next--${next.state}`],
            title: next.tooltip || undefined,
            'aria-haspopup': 'dialog',
            'aria-expanded': String(open.value),
            onClick: toggle,
            onPointerdown: keep,
            onMousedown: keep,
            onTouchstart: keep,
          }, parts),
          open.value
            ? h(Teleport, { to: 'body' }, h('div', {
                ref: panel,
                class: 'mq-pop',
                role: 'dialog',
                'aria-label': __('Next activity'),
                tabindex: '-1',
                style: { top: `${position.value.top}px`, left: `${position.value.left}px` },
              }, content()))
            : null,
        ]
      }
    },
  })
}

// ---------- Formatting (exported for tests) ----------

export function makeFormatters({ dayjsLocal, translate: __ }) {
  function currencyFormat(currency, options = {}) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'EUR',
      currencyDisplay: 'narrowSymbol',
      maximumFractionDigits: 0,
      ...options,
    })
  }

  // Card value and board total: "€1,200"
  function value(amount, currency) {
    if (amount == null || amount === '') return ''
    try {
      return currencyFormat(currency).format(amount)
    } catch {
      return `${currency || ''} ${amount}`.trim() // unknown currency code
    }
  }

  // Column totals: "€14.2k", "€1.3M"; below 1,000 the full value
  function compact(amount, currency) {
    amount = amount || 0
    if (Math.abs(amount) < 1000) return value(amount, currency)
    try {
      return currencyFormat(currency, {
        notation: 'compact',
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })
        .format(amount)
        .replace(/K$/, 'k')
    } catch {
      return value(amount, currency)
    }
  }

  // A due datetime with a time part other than midnight
  const hasTime = (dueDate) => !/^\d{4}-\d{2}-\d{2}( 00:00(:00(\.0+)?)?)?$/.test(dueDate)

  // Tasks with a time are converted to the user's timezone. A midnight due date
  // means "this day" and stays on that calendar day: converted, it would fall on
  // the day before for users west of the server's timezone.
  function dueAt(dueDate, now = dayjsLocal()) {
    if (hasTime(dueDate)) return dayjsLocal(dueDate)
    const [y, m, d] = dueDate.slice(0, 10).split('-').map(Number)
    return now.date(1).year(y).month(m - 1).date(d).startOf('day')
  }

  // Activity state of the deal's next activity (its earliest open CRM Task),
  // which sets the card's left border and the colour of the footer text:
  //   ok       due after today          "Call client · 27 Jan"
  //   today    due today                "Demo · today 15:00"
  //   none     no open task, or undated "Nothing scheduled" / "Send deck · no date"
  //   overdue  due before today         "Call client · overdue 2d"
  //   closed   deal is Won or Lost      "Closed"
  // Days are calendar days in the user's timezone.
  function nextStep(step, closed, now = dayjsLocal()) {
    if (closed) return { state: 'closed', title: '', when: __('Closed'), tooltip: '' }
    if (!step) return { state: 'none', title: '', when: __('Nothing scheduled'), tooltip: '' }

    const title = step.title || __('Task')
    if (!step.due_date) return { state: 'none', title, when: __('no date'), tooltip: title }

    const due = dueAt(step.due_date, now)
    const days = due.startOf('day').diff(now.startOf('day'), 'day')
    const tooltip = `${title} · ${dueFull(step.due_date)}`

    if (days < 0) return { state: 'overdue', title, when: __('overdue {0}d', [-days]), tooltip }
    if (days === 0) {
      const when = hasTime(step.due_date) ? __('today {0}', [due.format('HH:mm')]) : __('today')
      return { state: 'today', title, when, tooltip }
    }
    const when = days <= 6
      ? due.format('ddd')
      : due.format(due.year() === now.year() ? 'D MMM' : 'D MMM YYYY')
    return { state: 'ok', title, when, tooltip }
  }

  // "Tue 27 Jan 2027, 10:00"; no time when the task has none
  function dueFull(dueDate) {
    return dueAt(dueDate).format(hasTime(dueDate) ? 'ddd D MMM YYYY, HH:mm' : 'ddd D MMM YYYY')
  }

  // What the next-activity pop-up shows for a task
  function activityDetails(step) {
    return {
      title: step.title || __('Task'),
      due: step.due_date ? dueFull(step.due_date) : __('No due date'),
      assignee: step.assigned_to?.full_name || '',
      description: step.description || '',
    }
  }

  // Up to two initials: "John Smith" -> "JS"
  function initials(name) {
    return (name || '')
      .split(/[\s@._-]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((word) => word[0].toUpperCase())
      .join('')
  }

  // Lead source chip (the specific name if set, else the source) and direction chip
  function chips(meta) {
    const result = []
    const source = meta?.source
    const detail = meta?.source_detail
    if (detail || source) {
      result.push({
        kind: 'source',
        text: detail || source,
        tooltip: detail && source && detail !== source ? `${source} › ${detail}` : '',
      })
    }
    if (result.length && meta?.direction === 'Inbound') {
      result.push({ kind: 'direction', text: `↓ ${__('Inbound')}` })
    } else if (result.length && meta?.direction === 'Outbound') {
      result.push({ kind: 'direction', text: `↑ ${__('Outbound')}` })
    }
    return result
  }

  // View-model for one card. `meta` is the deal's entry from board_meta; `item`
  // is the board's own record, used until board_meta has loaded. Until then the
  // card shows no activity state, so cards don't flash amber.
  function card(item, meta) {
    return {
      title: meta?.title || item.name,
      contact: meta?.contact || '',
      chips: chips(meta),
      owner: meta?.owner || null,
      value: value(
        meta ? meta.value : item.expected_deal_value || item.deal_value,
        meta?.currency || item.currency,
      ),
      next: meta ? nextStep(meta.next_step, meta.closed) : null,
    }
  }

  return { value, compact, nextStep, activityDetails, initials, chips, card }
}
