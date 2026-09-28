import axios from 'axios'
import { describe, expect, it, vi } from 'vitest'
import snapshot from '../../public/showcase/snapshot.json'
import { createShowcaseAdapter, READ_ONLY_MESSAGE } from '@/showcase/adapter'
import { loginLocation, sessionKey } from '@/config/runtime'

function client(username = 'admin', assetFetch = vi.fn()) {
  return axios.create({
    adapter: createShowcaseAdapter(async () => snapshot, assetFetch),
    headers: { Authorization: `Bearer showcase:${username}` }
  })
}

describe('GitHub Pages showcase', () => {
  it('logs in with public demo personas and never returns a real JWT', async () => {
    const api = client('')
    for (const username of Object.keys(snapshot.actors)) {
      const { data } = await api.post('/auth/login', { username, password: '123456' })
      expect(data.data.access_token).toBe(`showcase:${username}`)
      expect(data.data.user.username).toBe(username)
    }
    await expect(api.post('/auth/login', { username: 'admin', password: 'wrong' })).rejects.toMatchObject({ response: { status: 400 } })
    await expect(api.get('/auth/me')).rejects.toMatchObject({ response: { status: 401 } })
  })

  it('serves every recorded read with its original role and HTTP status', async () => {
    for (const [username, actor] of Object.entries(snapshot.actors)) {
      const api = client(username)
      for (const [url, entry] of Object.entries(actor.responses)) {
        if ('asset' in entry) continue
        if (entry.status >= 400) {
          await expect(api.get(url)).rejects.toMatchObject({ response: { status: entry.status, data: entry.data } })
        } else {
          const response = await api.get(url)
          expect(response.data).toEqual(entry.data)
        }
      }
    }
  })

  it('filters the original resource data and does not mutate stored responses', async () => {
    const api = client()
    const original = await api.get('/resources', { params: { course_id: 1 } })
    const lectures = await api.get('/resources', { params: { course_id: 1, rtype: 'lecture' } })
    expect(lectures.data.data).toEqual(original.data.data.filter((row) => row.rtype === 'lecture'))
    original.data.data.splice(0)
    expect((await api.get('/resources?course_id=1')).data.data.length).toBeGreaterThan(0)
    expect((await api.get('/courses', { params: { keyword: '不存在的课程' } })).data.data).toEqual([])
  })

  it('blocks every write operation and preserves the snapshot', async () => {
    const before = JSON.stringify(snapshot)
    for (const method of ['post', 'put', 'patch', 'delete']) {
      for (const url of ['/agents/run', '/resources/generate', '/auth/register', '/auth/me', '/admin/users/1', '/tests/submit']) {
        await expect(client().request({ method, url, data: {} })).rejects.toMatchObject({
          response: { status: 405, data: { detail: READ_ONLY_MESSAGE } }
        })
      }
    }
    expect(JSON.stringify(snapshot)).toBe(before)
  })

  it('does not fall back to another persona or accept inherited object properties', async () => {
    await expect(client('student01').get('/admin/users')).rejects.toMatchObject({ response: { status: 403 } })
    await expect(client('constructor').get('/auth/me')).rejects.toMatchObject({ response: { status: 401 } })
    await expect(client('teacher2').get('/resources?course_id=1')).rejects.toMatchObject({ response: { status: 404 } })
  })

  it('downloads exported reports from a static asset and handles missing assets', async () => {
    const mockFetch = vi.fn().mockResolvedValue(new Response('sample-report', { headers: { 'Content-Type': 'application/pdf' } }))
    const response = await client('student01', mockFetch).get('/reports/student/1.pdf', { responseType: 'blob' })
    expect(mockFetch.mock.calls[0][0]).toMatch(/^\/showcase\/files\/.+\.pdf$/)
    expect(response.data.size).toBe(13)
    const failedFetch = vi.fn().mockResolvedValue(new Response('', { status: 404 }))
    await expect(client('student01', failedFetch).get('/reports/student/1.pdf')).rejects.toMatchObject({ code: 'ERR_NETWORK' })
  })
})

describe('repository subpath routing', () => {
  it('keeps expired sessions inside the repository, with an encoded route', () => {
    expect(loginLocation({ pathname: '/project/', search: '', hash: '#/student/report/1?tab=pdf' }, '/project/', true))
      .toBe('/project/#/login?redirect=%2Fstudent%2Freport%2F1%3Ftab%3Dpdf')
    expect(loginLocation({ pathname: '/', search: '', hash: '#/login?redirect=x' }, '/', true)).toBeNull()
    expect(loginLocation({ pathname: '/student', search: '?a=1', hash: '' }, '/', false)).toBe('/login?redirect=%2Fstudent%3Fa%3D1')
    expect(loginLocation({ pathname: '/app/student', search: '', hash: '' }, '/app/', false)).toBe('/app/login?redirect=%2Fstudent')
  })
  it('separates showcase sessions by repository and preserves full-service keys', () => {
    expect(sessionKey('token', true, '/one/')).not.toBe(sessionKey('token', true, '/two/'))
    expect(sessionKey('token', false, '/')).toBe('xunkeflow_token')
    expect(sessionKey('user', false, '/')).toBe('xunkeflow_user')
  })
})
