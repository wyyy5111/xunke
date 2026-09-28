export const ROLE_HOME: Record<string, string> = {
  student: '/student',
  teacher: '/teacher',
  admin: '/admin'
}

export function homeForRole(role: string): string {
  return ROLE_HOME[role] || '/login'
}

export function safeInternalRedirect(value: unknown, fallback: string): string {
  if (typeof value !== 'string') return fallback
  const candidate = value.trim()
  if (!/^\/(?!\/)/.test(candidate)) return fallback
  const hasControlCharacter = Array.from(candidate).some((char) => {
    const code = char.charCodeAt(0)
    return code < 32 || code === 127
  })
  if (candidate.includes('\\') || hasControlCharacter) return fallback
  return candidate
}
