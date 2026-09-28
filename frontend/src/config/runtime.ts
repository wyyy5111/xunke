/** The default build still talks to the complete FastAPI application. */
export const IS_SHOWCASE = import.meta.env.MODE === 'showcase'

export function sessionKey(name: 'token' | 'user', showcase = IS_SHOWCASE, base = import.meta.env.BASE_URL): string {
  return showcase ? `xunkeflow_showcase:${base}:${name}` : `xunkeflow_${name}`
}

/** Keep authentication redirects inside the current Pages repository path. */
export function loginLocation(
  current: Pick<Location, 'pathname' | 'search' | 'hash'>,
  base = import.meta.env.BASE_URL,
  hashMode = IS_SHOWCASE
): string | null {
  const route = hashMode
    ? (current.hash.replace(/^#/, '') || '/')
    : '/' + (current.pathname.startsWith(base) ? current.pathname.slice(base.length) : current.pathname.replace(/^\//, '')) + current.search
  if (route.split('?')[0] === '/login') return null
  return `${base}${hashMode ? '#/' : ''}login?redirect=${encodeURIComponent(route)}`
}
