// Tests for the deal-card formatting in public/js/masquetu.js.
//
// Uses Node's test runner and the dayjs that ships with the CRM frontend, so
// there is nothing to install. Point CRM_FRONTEND at the frontend folder of a
// frappe/crm checkout (with node_modules installed):
//
//   CRM_FRONTEND=<bench>/apps/crm/frontend node --test crm_platform/tests/js/*.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'

import { makeFormatters } from '../../public/js/masquetu.js'

const frontend = process.env.CRM_FRONTEND
if (!frontend) throw new Error('set CRM_FRONTEND to the frontend folder of a frappe/crm checkout')
const require = createRequire(`${frontend}/package.json`)
const dayjs = require('dayjs')
dayjs.extend(require('dayjs/plugin/utc'))
dayjs.extend(require('dayjs/plugin/timezone'))

// frappe-ui's dayjsLocal: server datetimes are in the system timezone, shown in the user's
const SYSTEM_TZ = 'Europe/Sofia'
const LOCAL_TZ = 'Europe/Berlin'
const dayjsLocal = (s) => (s ? dayjs.tz(s, SYSTEM_TZ).tz(LOCAL_TZ) : dayjs().tz(LOCAL_TZ))
const translate = (message, args = []) => message.replace(/\{(\d)\}/g, (_, i) => args[i])

const fmt = makeFormatters({ dayjsLocal, translate })
const now = dayjsLocal('2026-10-12 10:00:00') // a Monday
const task = (title, due_date) => ({ title, due_date })

test('values: full for cards, compact for column totals', () => {
  assert.equal(fmt.value(1200, 'EUR'), '€1,200')
  assert.equal(fmt.value(9800, 'USD'), '$9,800')
  assert.equal(fmt.value(null, 'EUR'), '')
  assert.equal(fmt.compact(14200, 'EUR'), '€14.2k')
  assert.equal(fmt.compact(11000, 'EUR'), '€11.0k')
  assert.equal(fmt.compact(1250000, 'EUR'), '€1.3M')
  assert.equal(fmt.compact(800, 'EUR'), '€800')
  assert.equal(fmt.compact(0, 'EUR'), '€0')
})

const state = (step) => [step.state, step.title, step.when]

test('next step: overdue keeps the title and counts days', () => {
  const step = fmt.nextStep(task('Call', '2026-10-10 09:00:00'), false, now)
  assert.deepEqual(state(step), ['overdue', 'Call', 'overdue 2d'])
  assert.equal(step.tooltip, 'Call · Sat 10 Oct 2026, 08:00')
})

test('next step: due today shows the time, if the task has one', () => {
  assert.deepEqual(state(fmt.nextStep(task('Demo', '2026-10-12 16:00:00'), false, now)),
    ['today', 'Demo', 'today 15:00'])
  assert.equal(fmt.nextStep(task('Demo', '2026-10-12'), false, now).when, 'today')
})

test('next step: later activities show a weekday, then a date, then the year', () => {
  assert.deepEqual(state(fmt.nextStep(task('Email', '2026-10-16 09:00:00'), false, now)),
    ['ok', 'Email', 'Fri'])
  assert.equal(fmt.nextStep(task('Email', '2026-10-18 12:00:00'), false, now).when, 'Sun')
  assert.equal(fmt.nextStep(task('Email', '2026-10-19 12:00:00'), false, now).when, '19 Oct')
  assert.equal(fmt.nextStep(task('Email', '2027-01-27 12:00:00'), false, now).when, '27 Jan 2027')
})

test('next step: nothing scheduled and undated tasks are amber', () => {
  assert.deepEqual(state(fmt.nextStep(null, false, now)), ['none', '', 'Nothing scheduled'])
  assert.deepEqual(state(fmt.nextStep(task('Send deck', null), false, now)), ['none', 'Send deck', 'no date'])
})

test('next step: compares calendar days in the user\'s timezone', () => {
  // 00:30 in Sofia on the 13th is still the 12th in Berlin: due today, not tomorrow
  assert.equal(fmt.nextStep(task('Call', '2026-10-13 00:30:00'), false, now).state, 'today')
  // A date without a time stays on its day: midnight in Sofia is 23:00 the day before in Berlin
  assert.equal(fmt.nextStep(task('Call', '2026-10-12 00:00:00'), false, now).state, 'today')
  assert.equal(fmt.nextStep(task('Call', '2026-10-13 00:00:00'), false, now).when, 'Tue')
})

test('next step: closed deals', () => {
  assert.deepEqual(state(fmt.nextStep(task('Call', '2026-10-10 09:00:00'), true, now)), ['closed', '', 'Closed'])
})

test('pop-up details', () => {
  const step = { task: 7, title: 'Call', due_date: '2027-01-26 11:00:00', assigned_to: { full_name: 'John Smith' }, description: 'Ask about Q1' }
  assert.deepEqual(fmt.activityDetails(step), {
    title: 'Call', due: 'Tue 26 Jan 2027, 10:00', assignee: 'John Smith', description: 'Ask about Q1',
  })
  assert.equal(fmt.activityDetails({ title: 'Call', due_date: null }).due, 'No due date')
  assert.equal(fmt.activityDetails({ title: 'Call', due_date: '2027-01-26' }).due, 'Tue 26 Jan 2027')
})

test('initials', () => {
  assert.equal(fmt.initials('John Smith'), 'JS')
  assert.equal(fmt.initials('Anna Maria van Dijk'), 'AM')
  assert.equal(fmt.initials('admin@example.com'), 'AE')
  assert.equal(fmt.initials(''), '')
})

test('chips: specific name over source, direction only with a source', () => {
  assert.deepEqual(fmt.chips({ source: 'Conference', source_detail: 'Acme Expo 2026', direction: 'Outbound' }), [
    { kind: 'source', text: 'Acme Expo 2026', tooltip: 'Conference › Acme Expo 2026' },
    { kind: 'direction', text: '↑ Outbound' },
  ])
  assert.deepEqual(fmt.chips({ source: 'LinkedIn', direction: 'Inbound' }).map((c) => c.text), ['LinkedIn', '↓ Inbound'])
  assert.deepEqual(fmt.chips({ source: null, direction: 'Inbound' }), [])
  assert.deepEqual(fmt.chips(undefined), [])
})

test('card: title, contact and value; no activity state until board data loads', () => {
  const item = { name: 'CRM-DEAL-2026-00001', organization: 'Ferreira Bakery', expected_deal_value: 3900, currency: 'EUR' }
  const loading = fmt.card(item)
  assert.equal(loading.title, 'CRM-DEAL-2026-00001')
  assert.equal(loading.value, '€3,900')
  assert.equal(loading.next, null)

  const meta = { title: 'Website retainer', contact: 'Ana Ferreira', value: 1200, currency: 'EUR', next_step: null }
  const card = fmt.card(item, meta)
  assert.deepEqual([card.title, card.contact, card.value, card.next.state], ['Website retainer', 'Ana Ferreira', '€1,200', 'none'])
  assert.equal(fmt.card({ name: 'D3', deal_value: 700, currency: 'EUR' }).value, '€700')
  assert.equal(fmt.card(item, { ...meta, value: 0 }).value, '€0')
})
