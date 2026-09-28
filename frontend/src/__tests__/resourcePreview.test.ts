import { describe, expect, it } from 'vitest'
import { formatResourcePreview } from '@/utils/resourcePreview'

describe('formatResourcePreview', () => {
  it('把练习 JSON 转换为可审核的结构化内容', () => {
    const content = JSON.stringify({
      questions: [{
        qtype: 'single',
        knowledge_point: '证据链',
        stem: '哪一项是可追溯学习资源的必要条件？',
        options: [
          { key: 'A', content: '保留来源与片段' },
          { key: 'B', content: '仅保留结论' },
        ],
        answer: 'A',
        analysis: '需要回指到课程资料。',
        wrong_reason: '忽略引用来源。',
        difficulty: 2,
      }],
    })

    const preview = formatResourcePreview({ rtype: 'exercise', content })

    expect(preview).toContain('1. 哪一项是可追溯学习资源的必要条件？')
    expect(preview).toContain('**题型**：单项选择')
    expect(preview).toContain('- A. 保留来源与片段')
    expect(preview).toContain('**参考答案**：A')
    expect(preview).toContain('**常见错因**：忽略引用来源。')
    expect(preview).not.toContain('"questions"')
  })

  it('对异常练习结构给出可操作提示', () => {
    const preview = formatResourcePreview({ rtype: 'exercise', content: '{invalid' })
    expect(preview).toContain('结构异常')
    expect(preview).toContain('修订正文')
  })

  it('保持非练习资源的 Markdown 原文', () => {
    expect(formatResourcePreview({ rtype: 'lecture', content: '# 讲义' })).toBe('# 讲义')
  })
})
