<template>
  <div class="page">
    <div class="page-title">前测诊断</div>
    <div class="page-desc">通过课程核心题目识别当前基础，并生成学习画像与个性化路径。</div>

    <div v-if="initializing" class="card"><el-skeleton :rows="7" animated /></div>

    <div v-else-if="error" class="page-state error">
      <div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>前测暂时不可用</h3><p>{{ error }}</p><el-button type="primary" @click="error = ''; start()">重新加载</el-button></div>
    </div>

    <div v-else-if="!started && !result" class="card start-card">
      <div class="start-icon"><el-icon><Aim /></el-icon></div>
      <h2>开始前测</h2>
      <p>系统将抽取 8 道课程核心题目。提交后自动生成诊断报告。</p>
      <el-button type="primary" size="large" :loading="loading" @click="start">开始答题</el-button>
    </div>

    <div v-else-if="started && !result" class="card">
      <div class="q-progress">
        <span>第 {{ idx + 1 }} / {{ questions.length }} 题</span>
        <el-progress :percentage="Math.round(((idx) / questions.length) * 100)" />
      </div>
      <div class="q-card" v-if="current">
        <div class="q-stem">{{ idx + 1 }}. [{{ typeText(current.qtype) }}] {{ current.stem }}</div>
        <div v-if="current.qtype === 'single' || current.qtype === 'multiple'" class="q-options">
          <el-radio-group v-if="current.qtype === 'single'" v-model="answers[current.id]">
            <el-radio v-for="o in current.options" :key="o.key" :value="o.key" class="q-opt">{{ o.key }}. {{ o.content }}</el-radio>
          </el-radio-group>
          <el-checkbox-group v-else v-model="answers[current.id]">
            <el-checkbox v-for="o in current.options" :key="o.key" :value="o.key" class="q-opt">{{ o.key }}. {{ o.content }}</el-checkbox>
          </el-checkbox-group>
        </div>
        <div v-else-if="current.qtype === 'judge'" class="q-options">
          <el-radio-group v-model="answers[current.id]">
            <el-radio value="正确">✅ 正确</el-radio>
            <el-radio value="错误">❌ 错误</el-radio>
          </el-radio-group>
        </div>
        <div v-else>
          <el-input v-model="answers[current.id]" type="textarea" :rows="3" placeholder="请输入你的答案" />
        </div>
      </div>
      <div class="q-actions">
        <el-button :disabled="idx === 0" @click="idx--">上一题</el-button>
        <el-button v-if="idx < questions.length - 1" type="primary" @click="idx++">下一题</el-button>
        <el-button v-else type="success" :loading="submitting" @click="submit">提交并诊断</el-button>
      </div>
    </div>

    <div v-else class="card result-card">
      <div class="result-head">
        <div class="big-score" :class="scoreColor(result.score)">{{ result.score }}<span>分</span></div>
        <div class="r-meta">
          <div>{{ result.correct != null ? `正确 ${result.correct} / ${result.total}` : '本课程前测已完成' }}</div>
          <el-tag :type="result.score >= 60 ? 'success' : 'danger'">{{ result.score >= 80 ? '基础扎实' : result.score >= 60 ? '中等水平' : '基础薄弱' }}</el-tag>
        </div>
      </div>
      <el-alert type="success" :closable="false" style="margin: 16px 0">
        {{ result.restored ? '前测结果已恢复，可继续查看学生画像和学习路径。' : '诊断完成！系统已生成你的学生画像与个性化学习路径。' }}
      </el-alert>
      <div class="result-actions">
        <el-button type="primary" @click="$router.push(`/student/profile/${cid}`)">查看学生画像</el-button>
        <el-button @click="$router.push(`/student/path/${cid}`)">查看学习路径</el-button>
        <el-button @click="$router.push(`/student/agents/${cid}`)">查看 Agent 日志</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { test as testApi } from '@/api'

const route = useRoute()
const cid: any = computed(() => route.params.cid)
const started = ref(false)
const initializing = ref(true)
const loading = ref(false)
const submitting = ref(false)
const questions = ref<any[]>([])
const idx = ref(0)
const answers = ref<Record<number, any>>({})
const result = ref<any>(null)
const error = ref('')

const current = computed(() => questions.value[idx.value])
const typeText = (t: string) => ({ single: '单选', multiple: '多选', judge: '判断', fill: '填空', short: '简答' }[t] || t)
const scoreColor = (s: number) => s >= 80 ? 'text-success' : s >= 60 ? 'text-warning' : 'text-danger'

async function start() {
  loading.value = true
  error.value = ''
  try {
    questions.value = (await testApi.pre(cid.value, 8, 'pre')) as any[]
    if (!questions.value.length) {
      ElMessage.warning('题库为空，请教师先在题库管理或资源生成中添加题目')
      return
    }
    questions.value.forEach(q => { answers.value[q.id] = q.qtype === 'multiple' ? [] : '' })
    started.value = true
  } catch (err: any) { error.value = err?.message || '请稍后重新加载前测题目。' } finally { loading.value = false }
}

async function submit() {
  const unanswered = questions.value.filter(q => {
    const a = answers.value[q.id]
    return Array.isArray(a) ? a.length === 0 : !a
  })
  if (unanswered.length) {
    try {
      await ElMessageBox.confirm(`还有 ${unanswered.length} 道题未作答，仍要提交吗？`, '确认提交', {
        confirmButtonText: '继续提交',
        cancelButtonText: '返回答题',
        type: 'warning'
      })
    } catch { return }
  }
  submitting.value = true
  try {
    const payload = {
      course_id: cid.value,
      test_type: 'pre',
      answers: questions.value.map(q => ({ question_id: q.id, answer: Array.isArray(answers.value[q.id]) ? answers.value[q.id].join('') : answers.value[q.id] }))
    }
    result.value = await testApi.submit(payload)
    ElMessage.success('提交成功，诊断报告已生成')
  } catch (err: any) { error.value = err?.message || '前测提交失败，请重试。' } finally { submitting.value = false }
}

async function restoreExistingResult() {
  try {
    const comparison = await testApi.compare(Number(cid.value), true)
    if (Number(comparison?.pre_score) > 0) {
      result.value = {
        score: Number(comparison.pre_score),
        correct: null,
        total: null,
        restored: true
      }
    }
  } catch { /* 尚未前测时继续显示开始页 */ }
  finally { initializing.value = false }
}

onMounted(restoreExistingResult)

</script>

<style scoped>
.start-card { text-align: center; padding: 50px 20px; }
.start-icon { width: 62px; height: 62px; display: grid; place-items: center; margin: 0 auto 12px; border-radius: 18px; color: var(--primary); background: var(--primary-bg); font-size: 29px; }
.start-card h2 { margin-bottom: 8px; }
.start-card p { color: var(--text-secondary); margin-bottom: 22px; }
.q-progress { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.q-stem { font-size: 16px; font-weight: 600; line-height: 1.7; margin-bottom: 16px; }
.q-options { display: flex; flex-direction: column; gap: 8px; }
.q-opt { display: flex; padding: 8px 12px; border: 1px solid var(--border); border-radius: 8px; margin: 0 !important; }
.q-opt:hover { background: #f3f4f6; }
.q-actions { display: flex; justify-content: space-between; margin-top: 20px; }
.result-head { display: flex; align-items: center; gap: 30px; }
.big-score { font-size: 56px; font-weight: 800; }
.big-score span { font-size: 18px; }
.r-meta div { margin-bottom: 8px; }
.result-actions { display: flex; gap: 10px; }
</style>
