<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="page-title">分层练习</div>
        <div class="page-desc">练习记录独立于前测，用于形成错题、错因和补救建议。</div>
      </div>
      <el-button type="primary" :loading="generating" @click="generateExercise">
        <el-icon><MagicStick /></el-icon>生成一组新练习
      </el-button>
    </div>

    <div v-if="loading" class="card"><el-skeleton :rows="8" animated /></div>

    <div v-else-if="error" class="page-state error">
      <div>
        <div class="state-icon"><el-icon><WarningFilled /></el-icon></div>
        <h3>练习加载失败</h3>
        <p>{{ error }}</p>
        <el-button type="primary" @click="load">重新加载</el-button>
      </div>
    </div>

    <div v-else-if="!questions.length" class="page-state">
      <div>
        <div class="state-icon"><el-icon><EditPen /></el-icon></div>
        <h3>当前课程还没有练习题</h3>
        <p>可以让教师补充题库，或直接生成一组与当前课程匹配的题目。</p>
        <el-button type="primary" :loading="generating" @click="generateExercise">生成练习</el-button>
      </div>
    </div>

    <template v-else>
      <section class="exercise-summary">
        <div><span>题目数量</span><b>{{ questions.length }}</b></div>
        <div><span>已完成</span><b>{{ answeredCount }}</b></div>
        <div><span>本次正确率</span><b>{{ submitted ? `${accuracy}%` : '待提交' }}</b></div>
      </section>

      <section class="question-list">
        <article v-for="(q, index) in questions" :key="q.id" class="question-block">
          <header class="question-head">
            <span class="question-index">{{ index + 1 }}</span>
            <div>
              <div class="question-meta">
                <el-tag size="small" effect="plain">{{ typeText(q.qtype) }}</el-tag>
                <span>难度 {{ q.difficulty || 3 }}/5</span>
                <span v-if="q.tags">{{ q.tags }}</span>
              </div>
              <h2>{{ q.stem }}</h2>
            </div>
          </header>

          <div class="answer-area">
            <el-radio-group v-if="q.qtype === 'single'" v-model="answers[q.id]" :disabled="submitted">
              <el-radio v-for="option in q.options" :key="option.key" :value="option.key" border>
                {{ option.key }}. {{ option.content }}
              </el-radio>
            </el-radio-group>
            <el-checkbox-group v-else-if="q.qtype === 'multiple'" v-model="answers[q.id]" :disabled="submitted">
              <el-checkbox v-for="option in q.options" :key="option.key" :value="option.key" border>
                {{ option.key }}. {{ option.content }}
              </el-checkbox>
            </el-checkbox-group>
            <el-radio-group v-else-if="q.qtype === 'judge'" v-model="answers[q.id]" :disabled="submitted">
              <el-radio value="正确" border>正确</el-radio>
              <el-radio value="错误" border>错误</el-radio>
            </el-radio-group>
            <el-input v-else v-model="answers[q.id]" type="textarea" :rows="3" :disabled="submitted" placeholder="请输入你的答案" />
          </div>

          <div v-if="submitted" class="result-panel" :class="results[q.id]?.is_correct ? 'correct' : 'incorrect'">
            <div class="result-line">
              <el-tag :type="results[q.id]?.is_correct ? 'success' : 'danger'">
                {{ results[q.id]?.is_correct ? '回答正确' : '需要巩固' }}
              </el-tag>
              <span>你的答案：<b>{{ answerText(answers[q.id]) || '未作答' }}</b></span>
              <span>参考答案：<b>{{ results[q.id]?.correct || '-' }}</b></span>
            </div>
            <p><strong>解析：</strong>{{ results[q.id]?.analysis || '暂无解析' }}</p>
            <p v-if="!results[q.id]?.is_correct"><strong>错因建议：</strong>{{ results[q.id]?.reason || '回到对应知识点梳理概念，再完成一道同类题。' }}</p>
          </div>
        </article>
      </section>

      <footer class="submit-bar">
        <div>
          <b>{{ submitted ? `本次答对 ${correctCount} / ${questions.length} 题` : `已完成 ${answeredCount} / ${questions.length} 题` }}</b>
          <span>{{ submitted ? '错题已进入后续补救流程' : '提交不会覆盖你的前测成绩' }}</span>
        </div>
        <div class="toolbar-actions">
          <el-button v-if="submitted" @click="reset">再做一次</el-button>
          <el-button v-else type="primary" :loading="submitting" @click="submit">提交练习</el-button>
        </div>
      </footer>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { resource, test } from '@/api'

const route = useRoute()
const cid = computed(() => Number(route.params.cid))
const loading = ref(true)
const generating = ref(false)
const submitting = ref(false)
const submitted = ref(false)
const error = ref('')
const questions = ref<any[]>([])
const answers = ref<Record<number, any>>({})
const results = ref<Record<number, any>>({})

const answeredCount = computed(() => questions.value.filter((q) => {
  const answer = answers.value[q.id]
  return Array.isArray(answer) ? answer.length > 0 : String(answer || '').trim().length > 0
}).length)
const correctCount = computed(() => Object.values(results.value).filter((row: any) => row?.is_correct).length)
const accuracy = computed(() => questions.value.length ? Math.round(correctCount.value / questions.value.length * 100) : 0)

const typeText = (type: string) => ({ single: '单选', multiple: '多选', judge: '判断', fill: '填空', short: '简答', code: '实践题', experiment: '实验题' }[type] || type)
const answerText = (answer: any) => Array.isArray(answer) ? answer.join('、') : String(answer || '')

function initializeAnswers(rows: any[]) {
  answers.value = Object.fromEntries(rows.map((q) => [q.id, q.qtype === 'multiple' ? [] : '']))
  results.value = {}
  submitted.value = false
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    questions.value = await test.pre(cid.value, 8)
    initializeAnswers(questions.value)
  } catch (err: any) {
    error.value = err?.message || '请稍后重新加载练习。'
  } finally {
    loading.value = false
  }
}

async function generateExercise() {
  generating.value = true
  error.value = ''
  try {
    const response = await resource.generate({ course_id: cid.value, rtype: 'exercise' })
    if (response?.status === 'failed') throw new Error('题目生成失败，请稍后重试。')
    ElMessage.success('练习已生成并进入教师审核，审核通过后会出现在题目列表')
    await load()
  } catch (err: any) {
    error.value = err?.message || '暂时无法生成新练习。'
  } finally {
    generating.value = false
  }
}

async function submit() {
  if (!answeredCount.value) return ElMessage.warning('请至少完成一道题后再提交')
  submitting.value = true
  try {
    const response = await test.exerciseSubmit({
      course_id: cid.value,
      answers: questions.value.map((q) => ({
        question_id: q.id,
        answer: Array.isArray(answers.value[q.id]) ? answers.value[q.id].join('') : String(answers.value[q.id] || '')
      }))
    })
    results.value = Object.fromEntries((response.details || []).map((row: any) => [row.question_id, row]))
    submitted.value = true
    ElMessage.success(`练习已提交，正确率 ${Math.round((response.correct || 0) / Math.max(1, response.total || 0) * 100)}%`)
  } catch (err: any) {
    ElMessage.error(err?.message || '练习提交失败，请重试')
  } finally {
    submitting.value = false
  }
}

function reset() {
  initializeAnswers(questions.value)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(load)
</script>

<style scoped>
.exercise-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; overflow: hidden; margin-bottom: 16px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--border); }
.exercise-summary div { padding: 15px 18px; background: #fff; }
.exercise-summary span, .exercise-summary b { display: block; }
.exercise-summary span { color: var(--text-secondary); font-size: 12px; }
.exercise-summary b { margin-top: 3px; font-size: 20px; }
.question-list { display: grid; gap: 14px; }
.question-block { padding: 22px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.question-head { display: grid; grid-template-columns: 34px 1fr; gap: 13px; }
.question-index { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 10px; color: #fff; background: var(--primary); font-weight: 750; }
.question-meta { display: flex; align-items: center; gap: 9px; color: var(--text-muted); font-size: 12px; }
.question-head h2 { margin-top: 9px; font-size: 16px; line-height: 1.7; }
.answer-area { margin: 18px 0 0 47px; }
.answer-area :deep(.el-radio-group), .answer-area :deep(.el-checkbox-group) { width: 100%; display: grid; gap: 9px; }
.answer-area :deep(.el-radio), .answer-area :deep(.el-checkbox) { width: 100%; min-height: 42px; margin: 0; }
.result-panel { margin: 18px 0 0 47px; padding: 14px 16px; border-radius: 10px; background: var(--success-bg); border-left: 3px solid var(--success); }
.result-panel.incorrect { background: var(--danger-bg); border-left-color: var(--danger); }
.result-line { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.result-panel p { margin-top: 9px; color: var(--text-secondary); }
.submit-bar { position: sticky; bottom: 12px; z-index: 8; display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 18px; padding: 15px 18px; border: 1px solid var(--border); border-radius: 14px; background: rgba(255,255,255,.94); box-shadow: var(--shadow); backdrop-filter: blur(14px); }
.submit-bar b, .submit-bar span { display: block; }
.submit-bar span { margin-top: 2px; color: var(--text-secondary); font-size: 12px; }
@media (max-width: 720px) { .exercise-summary { grid-template-columns: 1fr; } .answer-area, .result-panel { margin-left: 0; } .submit-bar { align-items: stretch; flex-direction: column; } }
</style>
