import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    run: vi.fn(async () => undefined)
  }
}))

import MarkdownView from '@/components/MarkdownView.vue'

describe('MarkdownView', () => {
  it('sanitizes script and event-handler HTML while keeping learning content', async () => {
    const wrapper = mount(MarkdownView, {
      props: {
        content: '# 课程讲义\n安全内容<img src="x" onerror="alert(1)"><script>alert(2)</script><svg onload="alert(3)"><a xlink:href="javascript:alert(4)">x</a></svg><span style="position:fixed">遮挡</span>'
      }
    })
    await flushPromises()
    const surface = wrapper.get('.md-surface')
    expect(surface.text()).toContain('课程讲义')
    expect(surface.html()).not.toContain('<script')
    expect(surface.html()).not.toContain('onerror')
    expect(surface.html()).not.toContain('<svg')
    expect(surface.html()).not.toContain('javascript:')
    expect(surface.html()).not.toContain('style=')
  })
})
