import { describe, expect, it, vi } from 'vitest'

const getMock = vi.hoisted(() => vi.fn())
const patchMock = vi.hoisted(() => vi.fn())

vi.mock('@/api/request', () => ({
  default: {
    get: getMock,
    post: vi.fn(),
    put: vi.fn(),
    patch: patchMock,
    delete: vi.fn(),
  },
}))

import { admin } from '@/api'

describe('administrator API client', () => {
  it('uses the protected role endpoint with an allowlisted role value', async () => {
    patchMock.mockResolvedValueOnce({ id: 8, role: 'teacher' })
    await admin.updateRole(8, 'teacher')
    expect(patchMock).toHaveBeenCalledWith('/admin/users/8/role', { role: 'teacher' })
  })

  it('downloads the data snapshot as a Blob instead of parsing it into the UI', async () => {
    const blob = new Blob(['{}'], { type: 'application/json' })
    getMock.mockResolvedValueOnce(blob)
    await expect(admin.exportSnapshot()).resolves.toBe(blob)
    expect(getMock).toHaveBeenCalledWith('/admin/data-snapshot', { responseType: 'blob' })
  })
})
