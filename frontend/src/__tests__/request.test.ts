import { describe, expect, it } from 'vitest'
import { ApiError, formatApiErrorDetail } from '@/api/request'

describe('API error normalization', () => {
  it('turns FastAPI validation details into readable Chinese text', () => {
    const text = formatApiErrorDetail([
      { loc: ['body', 'course_id'], msg: 'Field required' },
      { loc: ['body', 'answers'], msg: 'List should have at least 1 item' }
    ])
    expect(text).toContain('course_id：Field required')
    expect(text).toContain('answers：List should have at least 1 item')
  })

  it('preserves status and safe payload on ApiError', () => {
    const error = new ApiError('权限不足', { status: 403, payload: { detail: '权限不足' } })
    expect(error.name).toBe('ApiError')
    expect(error.status).toBe(403)
    expect(error.message).toBe('权限不足')
  })
})
