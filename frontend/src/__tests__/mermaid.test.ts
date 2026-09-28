import { describe, expect, it } from 'vitest'
import { normalizeMermaidSource } from '@/utils/mermaid'

describe('normalizeMermaidSource', () => {
  it('keeps stable graph syntax unchanged', () => {
    expect(normalizeMermaidSource('graph LR\n A --> B')).toBe('graph LR\n A --> B')
  })

  it('converts generated mindmaps into a hierarchical flowchart', () => {
    const result = normalizeMermaidSource(`mindmap
  root((可信课程))
    星槎证据链
      引用溯源
    教师审核`)
    expect(result).toContain('flowchart TD')
    expect(result).toContain('MM0["可信课程"]')
    expect(result).toContain('MM0 --> MM1')
    expect(result).toContain('MM1 --> MM2')
    expect(result).toContain('MM0 --> MM3')
    expect(result).not.toContain('mindmap')
  })
})
