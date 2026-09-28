function cleanLabel(raw: string) {
  let value = raw.trim()
  value = value.replace(/^root\s*/i, '')
  value = value.replace(/^\(\((.*)\)\)$/, '$1')
  value = value.replace(/^\[(.*)\]$/, '$1')
  value = value.replace(/^\((.*)\)$/, '$1')
  value = value.replace(/^['"]|['"]$/g, '')
  return value.replace(/"/g, "'").trim() || '课程要点'
}

/**
 * Mermaid's experimental `mindmap` renderer emits invalid SVG transforms in
 * some Chromium/headless layouts (`translate(undefined, NaN)`). Convert the
 * simple indented format used by generated course resources into a stable
 * top-down flowchart while preserving hierarchy and labels.
 */
export function normalizeMermaidSource(source: string) {
  const trimmed = (source || '').trim()
  if (!/^mindmap(?:\s|$)/i.test(trimmed)) return trimmed

  const rows = trimmed.split(/\r?\n/).slice(1)
  const declarations: string[] = ['flowchart TD']
  const edges: string[] = []
  const stack: Array<{ indent: number; id: string }> = []
  let nodeIndex = 0

  for (const raw of rows) {
    if (!raw.trim()) continue
    const indent = raw.match(/^\s*/)?.[0].length || 0
    const id = `MM${nodeIndex++}`
    declarations.push(`  ${id}["${cleanLabel(raw)}"]`)
    while (stack.length && stack[stack.length - 1].indent >= indent) stack.pop()
    if (stack.length) edges.push(`  ${stack[stack.length - 1].id} --> ${id}`)
    stack.push({ indent, id })
  }

  return [...declarations, ...edges].join('\n')
}
