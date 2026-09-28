import { AxiosError, AxiosHeaders, type AxiosAdapter, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'

export const READ_ONLY_MESSAGE = '当前为前端展示，操作不会保存。运行完整服务后可生成、提交或修改数据。'

interface Entry { status: number; content_type: string; data?: any; asset?: string }
interface Actor { user: Record<string, any>; responses: Record<string, Entry> }
export interface ShowcaseSnapshot {
  schema_version: number
  public: Record<string, Entry>
  actors: Record<string, Actor>
}

const hasOwn = (object: object, key: string) => Object.prototype.hasOwnProperty.call(object, key)

const base = `${import.meta.env.BASE_URL}showcase/`
let snapshotPromise: Promise<ShowcaseSnapshot> | undefined
async function loadSnapshot(): Promise<ShowcaseSnapshot> {
  if (!snapshotPromise) {
    snapshotPromise = fetch(base + 'snapshot.json').then(async (response) => {
      if (!response.ok) throw new Error('展示数据加载失败，请刷新页面重试')
      const data: ShowcaseSnapshot = await response.json()
      if (data.schema_version !== 1) throw new Error('展示数据版本不匹配')
      return data
    }).catch((error) => { snapshotPromise = undefined; throw error })
  }
  return snapshotPromise
}

function entryKey(path: string, params: Record<string, string | number> = {}): string {
  const query = new URLSearchParams(Object.entries(params).sort().map(([key, value]) => [key, String(value)]))
  return path + (query.size ? '?' + query.toString() : '')
}

function jsonEntry(data: unknown, status = 200): Entry {
  return { status, content_type: 'application/json', data }
}

function reject(message: string, status: number): Entry {
  return jsonEntry({ detail: message }, status)
}

// No backend request is made here. Persona tokens only select public seed data;
// they are not real credentials and provide no security boundary.
function resolveEntry(snapshot: ShowcaseSnapshot, config: InternalAxiosRequestConfig): Entry {
  const url = new URL(config.url || '/', 'https://showcase.invalid')
  const path = url.pathname.replace(/^\/api(?=\/)/, '').replace(/\/$/, '')
  const params = url.searchParams
  Object.entries(config.params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null) params.set(key, String(value))
  })
  const method = (config.method || 'get').toLowerCase()
  if (path === '/auth/login' && method === 'post') {
    let body: Record<string, unknown>
    try { body = typeof config.data === 'string' ? JSON.parse(config.data) : config.data || {} }
    catch { return reject('登录信息格式不正确', 400) }
    const username = String(body.username || '')
    const actor = hasOwn(snapshot.actors, username) ? snapshot.actors[username] : undefined
    if (!actor || body.password !== '123456') return reject('请使用展示账号 admin、teacher、teacher2 或 student01，密码 123456', 400)
    return jsonEntry({ code: 0, data: { access_token: `showcase:${username}`, token_type: 'bearer', user: actor.user } })
  }
  if (method !== 'get' && method !== 'head') return reject(READ_ONLY_MESSAGE, 405)
  if (hasOwn(snapshot.public, path)) return snapshot.public[path]
  const token = String(config.headers.get('Authorization') || '').replace(/^Bearer /, '')
  const username = token.startsWith('showcase:') ? token.slice(9) : ''
  const actor = hasOwn(snapshot.actors, username) ? snapshot.actors[username] : undefined
  if (!actor) return reject('请先选择展示账号登录', 401)
  let key = path
  if (['/resources', '/questions', '/review/pending'].includes(path)) {
    key = entryKey(path, { course_id: params.get('course_id') || '0' })
  } else if (['/agents/runs', '/agents/command_center'].includes(path) && Number(params.get('course_id'))) {
    key = entryKey(path, { course_id: params.get('course_id')! })
  } else if (path === '/courses' && params.get('include_archived') === 'true') {
    key = entryKey(path, { include_archived: 'true' })
  } else if (/^\/tests\/pre\/\d+$/.test(path)) {
    key = entryKey(path, { count: 10, test_type: params.get('test_type') || 'practice' })
  }
  const stored = hasOwn(actor.responses, key) ? actor.responses[key] : undefined
  if (!stored) return reject('当前展示账号没有该内容，请从课程列表选择可浏览的课程', 404)
  // Clone every response: Vue views can sort/edit their local copies safely.
  const result: Entry = JSON.parse(JSON.stringify(stored))
  if (result.status >= 400 || !Array.isArray(result.data?.data)) return result
  let rows = result.data.data as Record<string, any>[]
  if (path === '/courses' && params.get('keyword')) rows = rows.filter((row) => row.name.includes(params.get('keyword')))
  if (path === '/resources') {
    for (const [param, field] of [['rtype', 'rtype'], ['status', 'review_status'], ['student_id', 'student_id']]) {
      const value = params.get(param)
      if (value && value !== '0' && !(param === 'student_id' && actor.user.role === 'student')) rows = rows.filter((row) => String(row[field]) === value)
    }
  }
  if (path === '/questions') {
    for (const field of ['kp_id', 'qtype']) {
      const value = params.get(field)
      if (value && value !== '0') rows = rows.filter((row) => String(row[field]) === value)
    }
  }
  const limit = Number(params.get(/^\/tests\/pre\//.test(path) ? 'count' : 'limit'))
  if (limit > 0) rows = rows.slice(0, limit)
  result.data.data = rows
  return result
}

export function createShowcaseAdapter(
  getSnapshot: () => Promise<ShowcaseSnapshot> = loadSnapshot,
  getAsset: typeof fetch = (input, init) => fetch(input, init)
): AxiosAdapter {
  return async (config) => {
    const entry = resolveEntry(await getSnapshot(), config)
    let data = entry.data === undefined ? undefined : JSON.parse(JSON.stringify(entry.data))
    if (entry.asset) {
      const file = await getAsset(base + entry.asset)
      if (!file.ok) throw new AxiosError('报告文件加载失败，请刷新后重试', 'ERR_NETWORK', config)
      data = config.responseType === 'blob' ? await file.blob() : await file.text()
    } else if (config.responseType === 'blob' && entry.status < 400) {
      data = new Blob([JSON.stringify(data, null, 2)], { type: entry.content_type })
    }
    const response: AxiosResponse = {
      data, status: entry.status, statusText: entry.status < 400 ? 'OK' : 'Showcase response',
      headers: new AxiosHeaders({ 'Content-Type': entry.content_type }), config
    }
    if (entry.status >= 400) throw new AxiosError(String(entry.data?.detail || '展示请求失败'), 'ERR_BAD_RESPONSE', config, undefined, response)
    return response
  }
}

export const showcaseAdapter = createShowcaseAdapter()
