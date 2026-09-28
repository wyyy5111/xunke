import { describe, expect, it } from 'vitest'
import { homeForRole, safeInternalRedirect } from '@/router/guards'

describe('route guards', () => {
  it('maps roles to isolated workspaces', () => {
    expect(homeForRole('student')).toBe('/student')
    expect(homeForRole('teacher')).toBe('/teacher')
    expect(homeForRole('admin')).toBe('/admin')
    expect(homeForRole('unknown')).toBe('/login')
  })

  it('accepts only same-site relative redirect paths', () => {
    expect(safeInternalRedirect('/student/report/3', '/student')).toBe('/student/report/3')
    expect(safeInternalRedirect('https://evil.example', '/student')).toBe('/student')
    expect(safeInternalRedirect('//evil.example', '/student')).toBe('/student')
    expect(safeInternalRedirect('/\\evil', '/student')).toBe('/student')
  })
})
