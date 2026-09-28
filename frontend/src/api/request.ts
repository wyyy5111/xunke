import axios, {
  type AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type Method
} from 'axios'
import { ElMessage } from 'element-plus'
import { IS_SHOWCASE, loginLocation, sessionKey } from '@/config/runtime'

interface ApiEnvelope<T> {
  code: number
  msg?: string
  data: T
}

export interface RequestConfig extends AxiosRequestConfig {
  silent?: boolean
}

export class ApiError extends Error {
  status?: number
  code?: number
  payload?: unknown

  constructor(message: string, options: { status?: number; code?: number; payload?: unknown } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status
    this.code = options.code
    this.payload = options.payload
  }
}

const client: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 120000
})

if (IS_SHOWCASE) {
  client.defaults.adapter = async (config) => {
    const { showcaseAdapter } = await import('@/showcase/adapter')
    return showcaseAdapter(config)
  }
}

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(sessionKey('token'))
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

function isEnvelope<T>(value: unknown): value is ApiEnvelope<T> {
  return !!value && typeof value === 'object' && 'code' in value
}

export function formatApiErrorDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (!item || typeof item !== 'object') return String(item)
        const row = item as Record<string, unknown>
        const loc = Array.isArray(row.loc) ? row.loc.slice(1).join('.') : ''
        return `${loc ? `${loc}：` : ''}${String(row.msg || '参数不正确')}`
      })
      .join('；')
  }
  if (detail && typeof detail === 'object') {
    const row = detail as Record<string, unknown>
    return String(row.message || row.msg || '请求失败')
  }
  return '网络请求失败'
}

function handleFailure(error: unknown, silent = false): never {
  const axiosError = error as AxiosError<any>
  const status = axiosError.response?.status
  const responseData = axiosError.response?.data

  if (status === 401) {
    localStorage.removeItem(sessionKey('token'))
    localStorage.removeItem(sessionKey('user'))
    if (!silent) ElMessage.error('登录状态已失效，请重新登录')
    const target = loginLocation(location)
    if (target) window.setTimeout(() => {
      location.assign(target)
      // A hash-only navigation does not reset Pinia's stale in-memory session.
      if (IS_SHOWCASE) location.reload()
    }, 350)
  }

  const message = status === 401
    ? '登录状态已失效'
    : formatApiErrorDetail(responseData?.detail ?? responseData?.msg ?? axiosError.message)

  if (!silent && status !== 401) ElMessage.error(message)
  throw new ApiError(message, { status, payload: responseData })
}

async function send<T>(method: Method, url: string, data?: unknown, config: RequestConfig = {}): Promise<T> {
  const { silent = false, ...axiosConfig } = config
  try {
    const response = await client.request<ApiEnvelope<T> | T>({
      ...axiosConfig,
      method,
      url,
      data
    })
    const payload = response.data
    if (isEnvelope<T>(payload)) {
      if (payload.code !== 0) {
        const message = payload.msg || '请求失败'
        if (!silent) ElMessage.error(message)
        throw new ApiError(message, { code: payload.code, payload })
      }
      return payload.data
    }
    return payload as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    return handleFailure(error, silent)
  }
}

const request = {
  get<T = any>(url: string, config?: RequestConfig) {
    return send<T>('GET', url, undefined, config)
  },
  post<T = any>(url: string, data?: unknown, config?: RequestConfig) {
    return send<T>('POST', url, data, config)
  },
  put<T = any>(url: string, data?: unknown, config?: RequestConfig) {
    return send<T>('PUT', url, data, config)
  },
  patch<T = any>(url: string, data?: unknown, config?: RequestConfig) {
    return send<T>('PATCH', url, data, config)
  },
  delete<T = any>(url: string, config?: RequestConfig) {
    return send<T>('DELETE', url, undefined, config)
  }
}

export default request
