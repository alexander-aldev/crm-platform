// Tests for the note-title formula in crm-patches/<tag>/0004-task-status-note-prompt.patch
// (frontend/src/utils/taskNoteTitle.js, a pure module).
//
// Needs a CRM frontend with that patch applied; nothing to install:
//
//   CRM_FRONTEND=<bench>/apps/crm/frontend node --test crm_platform/tests/crm_patches/*.test.mjs
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { pathToFileURL } from 'node:url'

const frontend = process.env.CRM_FRONTEND
if (!frontend) throw new Error('set CRM_FRONTEND to the frontend folder of a frappe/crm checkout')
const { plainText, taskNoteTitle, taskSubject, withoutNames } = await import(
  pathToFileURL(`${frontend}/src/utils/taskNoteTitle.js`)
)

describe('taskSubject', () => {
  it('capitalises and collapses spaces', () => {
    assert.equal(taskSubject('  follow   up '), 'Follow up')
  })

  it('removes reply prefixes', () => {
    assert.equal(taskSubject('Re: Re: Updated Service Agreement'), 'Updated Service Agreement')
    assert.equal(taskSubject('AW: Fwd: Intro call'), 'Intro call')
  })

  it('keeps a word that only starts like a prefix', () => {
    assert.equal(taskSubject('Regards to Ivan'), 'Regards to Ivan')
  })

  it('cuts a long title at a word boundary', () => {
    assert.equal(
      taskSubject('KN overland BI call on the progress after the workshop'),
      'KN overland BI call on the progress…',
    )
  })

  it('copes with a missing title and with one long word', () => {
    assert.equal(taskSubject(undefined), '')
    assert.equal(taskSubject('x'.repeat(60)), 'X' + 'x'.repeat(39) + '…')
  })
})

describe('taskNoteTitle', () => {
  const names = { deal: 'Kuehne + Nagel', contact: 'Shirish Ekbote' }

  it('is {New status}, {Task} / {Deal}, {Contact}', () => {
    const task = { title: 'follow up' }
    assert.equal(
      taskNoteTitle({ task, from: 'Todo', to: 'Done', ...names }),
      'Done, Follow up / Kuehne + Nagel, Shirish Ekbote',
    )
  })

  it('names the new status as it is, not a verb', () => {
    const task = { title: 'Email' }
    assert.equal(
      taskNoteTitle({ task, from: 'Todo', to: 'In Progress', ...names }),
      'In Progress, Email / Kuehne + Nagel, Shirish Ekbote',
    )
  })

  it('leaves out the deal or the contact when there is none', () => {
    const task = { title: 'Email' }
    assert.equal(taskNoteTitle({ task, to: 'Canceled', deal: 'ACME' }), 'Canceled, Email / ACME')
    assert.equal(taskNoteTitle({ task, to: 'Canceled', contact: 'Ana' }), 'Canceled, Email / Ana')
    assert.equal(taskNoteTitle({ task, to: 'Canceled' }), 'Canceled, Email')
  })

  it('does not repeat the deal or the contact in the task part', () => {
    const task = { title: 'Follow up: Shirish Ekbote, Kuehne + Nagel' }
    assert.equal(
      taskNoteTitle({ task, to: 'Done', ...names }),
      'Done, Follow up / Kuehne + Nagel, Shirish Ekbote',
    )
  })

  it('drops the task part when the names are all it said', () => {
    assert.equal(
      taskNoteTitle({ task: { title: 'Shirish Ekbote' }, to: 'Done', ...names }),
      'Done / Kuehne + Nagel, Shirish Ekbote',
    )
  })

  it('puts a suggestion from an app in place of the task', () => {
    const task = { title: 'Follow up' }
    assert.equal(
      taskNoteTitle({ task, to: 'Done', subject: 'Budget frozen until Q3', ...names }),
      'Done, Budget frozen until Q3 / Kuehne + Nagel, Shirish Ekbote',
    )
  })

  it('takes the names out of a suggestion too, and keeps the task if nothing is left', () => {
    const task = { title: 'Follow up' }
    assert.equal(
      taskNoteTitle({ task, to: 'Done', subject: 'Shirish Ekbote asked for a demo', ...names }),
      'Done, Asked for a demo / Kuehne + Nagel, Shirish Ekbote',
    )
    assert.equal(
      taskNoteTitle({ task, to: 'Done', subject: 'Kuehne + Nagel', ...names }),
      'Done, Follow up / Kuehne + Nagel, Shirish Ekbote',
    )
  })

  it('does not name a contact that is the deal', () => {
    const task = { title: 'Call' }
    assert.equal(
      taskNoteTitle({ task, to: 'Done', deal: 'Ana Lead', contact: 'ana lead' }),
      'Done, Call / Ana Lead',
    )
  })

  it('cuts only the task part to stay within the 140 characters of a note title', () => {
    const task = { title: 'word '.repeat(40) }
    const title = taskNoteTitle({ task, to: 'Done', deal: 'D'.repeat(50), contact: 'C'.repeat(40) })
    assert.ok(title.length <= 140, title.length)
    assert.ok(title.startsWith('Done, Word'))
    assert.ok(title.endsWith('… / ' + 'D'.repeat(50) + ', ' + 'C'.repeat(40)))
  })

  it('copes with a task without a title', () => {
    assert.equal(taskNoteTitle({ task: {}, to: 'Done', deal: 'ACME' }), 'Done / ACME')
  })
})

describe('withoutNames', () => {
  const names = ['Kuehne + Nagel', 'Shirish Ekbote']

  it('removes a name and the separators or connectors it leaves dangling', () => {
    assert.equal(withoutNames('Follow up with Shirish Ekbote', names), 'Follow up')
    assert.equal(withoutNames('call kuehne + nagel (Shirish Ekbote) about the quote', names), 'call about the quote')
    assert.equal(withoutNames('Follow up: Shirish Ekbote, Kuehne + Nagel', names), 'Follow up')
    assert.equal(withoutNames('Send offer to Iván', ['Iván']), 'Send offer')
  })

  it('matches whole names only', () => {
    assert.equal(withoutNames('Reacme call', ['ACME']), 'Reacme call')
    assert.equal(withoutNames('ACME renewal', ['ACME']), 'renewal')
  })

  it('leaves a title without the names as it is', () => {
    assert.equal(withoutNames('Follow up with Ivan, and report', names), 'Follow up with Ivan, and report')
    assert.equal(withoutNames(undefined, names), '')
  })
})

describe('plainText', () => {
  it('drops markup and collapses spaces', () => {
    assert.equal(plainText('<p>Budget&nbsp;<b>approved</b></p><p>by  Ivan</p>'), 'Budget approved by Ivan')
    assert.equal(plainText(null), '')
  })
})
