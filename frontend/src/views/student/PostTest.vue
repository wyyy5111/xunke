<template>
  <div class="page assessment-page">
    <div class="page-header">
      <div>
        <div class="page-title">后测评估</div>
        <div class="page-desc">完成学习后验证知识掌握变化，结果将进入个人学习报告。</div>
      </div>
      <span class="metric-chip">课程 #{{ cid }}</span>
    </div>

    <div v-if="loading" class="card"><el-skeleton :rows="7" animated /></div>

    <div v-else-if="error" class="page-state error">
      <div>
        <div class="state-icon"><el-icon><WarningFilled /></el-icon></div>
        <h3>后测暂时不可用</h3>
        <p>{{ error }}</p>
        <el-button type="primary" @click="prepare">重新加载</el-button>
      </div>
    </div>

    <section v-else-if="!started && !result" class="assessment-start">
      <span class="start-mark"><el-icon><TrendCharts /></el-icon></span>
      <p class="eyebrow">LEARNING OUTCOME</p>
      <h1>用一次后测确认学习是否真正发生</h1>
      <p>共 {{ questions.length }} 道题，提交后自动生成总分和知识点维度对比。</p>
      <el-button type="primary" size="large" :disabled="!questions.length" @click="started = true">开始后测</el-button>
    </section>

    <section v-else-if="started && !result" class="assessment-shell">
      <aside class="question-nav">
        <b>答题进度</b>
        <el-progress :percentage="progress" :stroke-width="8" />
        <div class="nav-grid">
          <button
            v-for="(q, index) in questions"
            :key="q.id"
            type="button"
            :class="{ active: index === idx, answered: hasAnswer(q) }"
            @click="idx = index"
          >{{ index + 1 }}</button>
        </div>
      </aside>

      <article v-if="current" class="question-stage">
        <div class="question-meta">
          <span>第 {{ idx + 1 }} / {{ questions.length }} 题</span>
          <el-tag effect="plain">{{ typeText(current.qtype) }}</el-tag>
          <span>难度 {{ current.difficulty || 3 }}/5</span>
        </div>
        <h2>{{ current.stem }}</h2>

        <div class="answer-area">
          <el-radio-group v-if="current.qtype === 'single'" v-model="answers[current.id]">
            <el-radio v-for="option in current.options" :key="option.key" :value="option.key" border>{{ option.key }}. {{ option.content }}</el-radio>
          </el-radio-group>
          <el-checkbox-group v-else-if="current.qtype === 'multiple'" v-model="answers[current.id]">
            <el-checkbox v-for="option in current.options" :key="option.key" :value="option.key" border>{{ option.key }}. {{ option.content }}</el-checkbox>
          </el-checkbox-group>
          <el-radio-group v-else-if="current.qtype === 'judge'" v-model="answers[current.id]">
            <el-radio value="正确" border>正确</el-radio>
            <el-radio value="错误" border>错误</el-radio>
          </el-radio-group>
          <el-input v-else v-model="answers[current.id]" type="textarea" :rows="4" placeholder="请输入你的答案" />
        </div>

        <footer class="question-actions">
          <el-button :disabled="idx === 0" @click="idx--">上一题</el-button>
          <el-button v-if="idx < questions.length - 1" type="primary" @click="idx++">下一题</el-button>
          <el-button v-else type="success" :loading="submitting" @click="submit">提交后测</el-button>
        </footer>
      </article>
    </section>

    <section v-else class="result-surface">
      <span class="result-label">本次后测成绩</span>
      <strong>{{ result.score }}<small>分</small></strong>
      <p :class="Number(result.improvement) >= 0 ? 'text-success' : 'text-danger'">
        较前测 {{ signed(result.improvement) }} 分
      </p>
      <div class="toolbar-actions">
        <el-button type="primary" @click="$router.push(`/student/compare/${cid}`)">查看前后测对比</el-button>
        <el-button @click="$router.push(`/student/wrong/${cid}`)">查看错题补救</el-button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { test } from '@/api'

const route = useRoute()
const cid = computed(() => Number(route.params.cid))
const loading = ref(true)
const submitting = ref(false)
const started = ref(false)
const error = ref('')
const questions = ref<any[]>([])
const answers = ref<Record<number, any>>({})
const idx = ref(0)
const result = ref<any>(null)

const current = computed(() => questions.value[idx.value])
const progress = computed(() => questions.value.length ? Math.round(questions.value.filter(hasAnswer).length / questions.value.length * 100) : 0)
const typeText = (type: string) => ({ single: '单选', multiple: '多选', judge: '判断', fill: '填空', short: '简答' }[type] || type)
const signed = (value: number) => `${Number(value) >= 0 ? '+' : ''}${Number(value || 0).toFixed(1)}`

function hasAnswer(question: any) {
  const value = answers.value[question.id]
  return Array.isArray(value) ? value.length > 0 : String(value || '').trim().length > 0
}

async function prepare() {
  loading.value = true
  error.value = ''
  try {
    const comparison = await test.compare(cid.value, true).catch(() => null)
    if (Number(comparison?.post_score) > 0) {
      result.value = {
        score: Number(comparison.post_score),
        improvement: Number(comparison.improvement || 0),
        restored: true
      }
      started.value = false
      questions.value = []
      return
    }
    questions.value = await test.pre(cid.value, 8, 'post')
    if (!questions.value.length) {
      error.value = '课程题库为空，请联系教师补充题目。'
      return
    }
    answers.value = Object.fromEntries(questions.value.map((q) => [q.id, q.qtype === 'multiple' ? [] : '']))
  } catch (err: any) {
    error.value = err?.message || '请稍后重新加载。'
  } finally {
    loading.value = false
  }
}

async function submit() {
  const unanswered = questions.value.filter((q) => !hasAnswer(q)).length
  if (unanswered) {
    try {
      await ElMessageBox.confirm(`还有 ${unanswered} 道题未作答，仍要提交吗？`, '确认提交', { confirmButtonText: '继续提交', cancelButtonText: '返回答题' })
    } catch { return }
  }
  submitting.value = true
  try {
    result.value = await test.submit({
      course_id: cid.value,
      test_type: 'post',
      answers: questions.value.map((q) => ({
        question_id: q.id,
        answer: Array.isArray(answers.value[q.id]) ? answers.value[q.id].join('') : String(answers.value[q.id] || '')
      }))
    })
    ElMessage.success('后测已提交，学习成效已更新')
  } catch (err: any) {
    error.value = err?.message || '后测提交失败，请重试。'
  } finally {
    submitting.value = false
  }
}

onMounted(prepare)
</script>

<style scoped>
.assessment-start, .result-surface { min-height: 440px; display: flex; align-items: center; justify-content: center; flex-direction: column; padding: 42px; text-align: center; border: 1px solid var(--border); border-radius: var(--radius-xl); background: #fff; box-shadow: var(--shadow-sm); }
.start-mark { width: 58px; height: 58px; display: grid; place-items: center; margin-bottom: 18px; border-radius: 16px; color: var(--primary); background: var(--primary-bg); font-size: 26px; }
.eyebrow { color: var(--primary) !important; font-size: 11px !important; font-weight: 800; letter-spacing: .12em; }
.assessment-start h1 { max-width: 620px; margin: 8px 0 12px; font-size: clamp(28px, 4vw, 42px); line-height: 1.18; letter-spacing: -.04em; }
.assessment-start p { max-width: 620px; margin-bottom: 22px; color: var(--text-secondary); }
.assessment-shell { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 16px; }
.question-nav, .question-stage { padding: 22px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.question-nav { align-self: start; }
.question-nav > b { display: block; margin-bottom: 12px; }
.nav-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 7px; margin-top: 18px; }
.nav-grid button { aspect-ratio: 1; border: 1px solid var(--border); border-radius: 8px; background: #fff; color: var(--text-secondary); cursor: pointer; }
.nav-grid button.answered { border-color: #9dd8ca; color: var(--success); background: var(--success-bg); }
.nav-grid button.active { border-color: var(--primary); color: #fff; background: var(--primary); }
.question-meta { display: flex; align-items: center; gap: 10px; color: var(--text-muted); font-size: 12px; }
.question-stage h2 { margin: 18px 0 24px; font-size: 19px; line-height: 1.75; }
.answer-area :deep(.el-radio-group), .answer-area :deep(.el-checkbox-group) { width: 100%; display: grid; gap: 10px; }
.answer-area :deep(.el-radio), .answer-area :deep(.el-checkbox) { width: 100%; min-height: 44px; margin: 0; }
.question-actions { display: flex; justify-content: space-between; margin-top: 28px; }
.result-surface strong { margin: 8px 0; color: var(--primary); font-size: 76px; line-height: 1; letter-spacing: -.06em; }
.result-surface strong small { margin-left: 6px; font-size: 20px; }
.result-surface p { margin-bottom: 22px; font-size: 16px; font-weight: 700; }
@media (max-width: 820px) { .assessment-shell { grid-template-columns: 1fr; } .question-nav { order: 2; } }
</style>
