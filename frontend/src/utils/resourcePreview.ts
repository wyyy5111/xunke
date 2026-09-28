type ResourcePreviewInput = {
  rtype?: string
  content?: unknown
}

type ExerciseOption = {
  key?: unknown
  content?: unknown
}

type ExerciseQuestion = {
  qtype?: unknown
  knowledge_point?: unknown
  stem?: unknown
  options?: unknown
  answer?: unknown
  analysis?: unknown
  wrong_reason?: unknown
  difficulty?: unknown
}

const questionTypeLabels: Record<string, string> = {
  single: '单项选择',
  multiple: '多项选择',
  judge: '判断题',
  fill: '填空题',
  short: '简答题',
  code: '实践题',
  experiment: '实验题',
}

const text = (value: unknown, fallback = '—') => {
  const result = String(value ?? '').trim()
  return result || fallback
}

const questionType = (value: unknown) => {
  const key = String(value ?? '').trim()
  return questionTypeLabels[key] || key || '练习题'
}

const difficulty = (value: unknown) => {
  const score = Number(value)
  if (!Number.isFinite(score)) return '未标注'
  return `${Math.max(1, Math.min(5, Math.round(score)))}/5`
}

const optionLines = (value: unknown) => {
  if (!Array.isArray(value) || !value.length) return ''
  return value.map((option: ExerciseOption | string, index) => {
    if (typeof option === 'string') return `- ${String.fromCharCode(65 + index)}. ${text(option)}`
    return `- ${text(option?.key, String.fromCharCode(65 + index))}. ${text(option?.content)}`
  }).join('\n')
}

function exercisePreview(content: unknown) {
  try {
    const payload = typeof content === 'string' ? JSON.parse(content) : content
    const questions = Array.isArray(payload)
      ? payload
      : (payload && typeof payload === 'object' && Array.isArray((payload as { questions?: unknown }).questions)
          ? (payload as { questions: ExerciseQuestion[] }).questions
          : [])

    if (!questions.length) {
      return '> 该练习资源暂无可预览题目。请切换到“修订正文”检查资源结构。'
    }

    return questions.map((question: ExerciseQuestion, index: number) => {
      const options = optionLines(question?.options)
      const meta = [
        `**题型**：${questionType(question?.qtype)}`,
        `**难度**：${difficulty(question?.difficulty)}`,
        question?.knowledge_point ? `**知识点**：${text(question.knowledge_point)}` : '',
      ].filter(Boolean).join('　')

      return [
        `## ${index + 1}. ${text(question?.stem, '未填写题干')}`,
        meta,
        options,
        `**参考答案**：${text(question?.answer)}`,
        `**解析**：${text(question?.analysis)}`,
        `**常见错因**：${text(question?.wrong_reason)}`,
      ].filter(Boolean).join('\n\n')
    }).join('\n\n---\n\n')
  } catch {
    return '> 练习资源结构异常，无法生成结构化预览。请切换到“修订正文”修正 JSON 后再审核。'
  }
}

export function formatResourcePreview(resource: ResourcePreviewInput | null | undefined, contentOverride?: unknown) {
  if (!resource) return ''
  const content = contentOverride === undefined ? resource.content : contentOverride
  if (resource.rtype === 'exercise') return exercisePreview(content)
  return String(content ?? '')
}
