import { describe, expect, it } from 'vitest'
import { authorizations, DEMO_TODAY, persons, qualifications, shiftDemoDate } from '@/mocks/labData'

describe('synthetic laboratory dataset', () => {
  it('keeps the seed calendar aligned to the current local day', () => {
    expect(shiftDemoDate('2026-10-15')).toBe(DEMO_TODAY)
    expect(shiftDemoDate('2026-10-15 09:30')).toBe(`${DEMO_TODAY} 09:30`)

    const expiredDate = new Date(`${shiftDemoDate('2026-10-05')}T00:00:00Z`)
    const today = new Date(`${DEMO_TODAY}T00:00:00Z`)
    expect((today.getTime() - expiredDate.getTime()) / 86_400_000).toBe(10)
  })

  it('provides full names and linked qualification and authorization data for each person', () => {
    expect(persons).toHaveLength(15)
    expect(persons.every((person) => person.name.length >= 2 && !person.name.includes('某'))).toBe(true)
    expect(persons.every((person) => qualifications.some((q) => q.personId === person.id))).toBe(true)
    expect(persons.every((person) => authorizations.some((a) => a.personId === person.id))).toBe(true)
  })
})
