<template>
  <div class="page settings-page">
    <header class="page-header">
      <div>
        <div class="page-title">个人设置</div>
        <div class="page-desc">维护账号信息与学习策略；保存后会同步到当前课程画像和后续个性化资源生成。</div>
      </div>
      <span class="save-state" :class="{ saved: savedAt }">
        <el-icon><CircleCheck v-if="savedAt" /><Clock v-else /></el-icon>
        {{ savedAt ? `已保存 ${savedAt}` : '设置将安全保存到服务端' }}
      </span>
    </header>

    <div v-if="loading" class="settings-skeleton" aria-label="正在加载个人设置">
      <el-skeleton animated :rows="8" />
    </div>

    <div v-else-if="error" class="page-state error">
      <div>
        <div class="state-icon"><el-icon><WarningFilled /></el-icon></div>
        <h3>个人设置加载失败</h3>
        <p>{{ error }}</p>
        <el-button type="primary" @click="load">重新加载</el-button>
      </div>
    </div>

    <div v-else class="settings-shell">
      <aside class="identity-panel">
        <div class="identity-mark">{{ initials }}</div>
        <span class="identity-role">学生账号</span>
        <h2>{{ form.full_name || settings?.user?.username }}</h2>
        <p>@{{ settings?.user?.username }}</p>

        <dl class="identity-facts">
          <div><dt>已加入课程</dt><dd>{{ courses.length }} 门</dd></div>
          <div><dt>每周学习投入</dt><dd>{{ form.weekly_hours }} 小时</dd></div>
          <div><dt>偏好形式</dt><dd>{{ form.learning_preferences.length }} 项</dd></div>
        </dl>

        <div class="strategy-note">
          <el-icon><MagicStick /></el-icon>
          <div>
            <b>个性化策略已接通</b>
            <p>学习目标、时长和偏好会进入学生画像，辅助规划讲义深度、图解比例与练习结构。</p>
          </div>
        </div>
      </aside>

      <main class="settings-form-panel">
        <section class="form-section">
          <header>
            <span class="section-index">01</span>
            <div><h2>基本资料</h2><p>用于学习报告署名和教师端学生识别。</p></div>
          </header>
          <div class="form-grid">
            <label>
              <span>姓名</span>
              <el-input v-model="form.full_name" maxlength="64" show-word-limit placeholder="请输入真实姓名" />
            </label>
            <label>
              <span>邮箱</span>
              <el-input v-model="form.email" maxlength="128" placeholder="用于账号联系与通知" />
            </label>
          </div>
        </section>

        <section class="form-section learning-section">
          <header>
            <span class="section-index">02</span>
            <div><h2>课程学习计划</h2><p>选择课程后，目标和时长将同步到该课程画像。</p></div>
          </header>

          <div v-if="courses.length" class="course-plan">
            <label class="course-picker">
              <span>当前课程</span>
              <el-select v-model="selectedCourseId" @change="applyCoursePlan">
                <el-option
                  v-for="item in courses"
                  :key="item.course_id"
                  :label="`${item.name}${item.code ? ` · ${item.code}` : ''}`"
                  :value="item.course_id"
                />
              </el-select>
            </label>
            <label class="goal-field">
              <span>学习目标</span>
              <el-input
                v-model="form.learning_goal"
                type="textarea"
                :rows="3"
                maxlength="256"
                show-word-limit
                placeholder="例如：掌握核心概念并能独立完成综合应用任务"
              />
            </label>
            <label class="hours-field">
              <span>每周学习时长</span>
              <div class="hours-control">
                <el-slider v-model="form.weekly_hours" :min="1" :max="40" :step="1" show-stops />
                <strong>{{ form.weekly_hours }}<small>小时</small></strong>
              </div>
            </label>
          </div>
          <div v-else class="inline-empty">
            <el-icon><Reading /></el-icon>
            <div><b>尚未加入课程</b><p>可以先保存默认学习策略，加入课程后再设置课程目标。</p></div>
            <el-button @click="router.push('/courses')">前往课程中心</el-button>
          </div>
        </section>

        <section class="form-section preference-section">
          <header>
            <span class="section-index">03</span>
            <div><h2>内容偏好</h2><p>至少选择一项，系统将据此调整内容组织方式。</p></div>
          </header>
          <el-checkbox-group v-model="form.learning_preferences" class="preference-grid">
            <el-checkbox-button v-for="item in preferenceOptions" :key="item.value" :value="item.value">
              <el-icon><component :is="item.icon" /></el-icon>
              <span><b>{{ item.value }}</b><small>{{ item.description }}</small></span>
            </el-checkbox-button>
          </el-checkbox-group>
        </section>

        <footer class="form-actions">
          <p><el-icon><Lock /></el-icon> 此页面不能修改用户名、角色或账号状态。</p>
          <div>
            <el-button :disabled="saving" @click="reset">恢复已保存内容</el-button>
            <el-button type="primary" :loading="saving" @click="save">
              <el-icon v-if="!saving"><Check /></el-icon>
              保存个人设置
            </el-button>
          </div>
        </footer>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { auth } from '@/api'
import { useUserStore } from '@/stores/user'

interface CoursePlan {
  course_id: number
  name: string
  code: string
  goal: string
  weekly_hours: number
}

interface SettingsPayload {
  user: Record<string, any>
  learning_goal: string
  weekly_hours: number
  learning_preferences: string[]
  courses: CoursePlan[]
}

const router = useRouter()
const userStore = useUserStore()
const settings = ref<SettingsPayload | null>(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const savedAt = ref('')
const selectedCourseId = ref<number | null>(null)
const form = reactive({
  full_name: '',
  email: '',
  learning_goal: '',
  weekly_hours: 6,
  learning_preferences: [] as string[]
})

const preferenceOptions = [
  { value: '文本精读', description: '讲义与概念分层', icon: 'Document' },
  { value: '视觉图解', description: '图谱与结构示意', icon: 'PictureRounded' },
  { value: '实践演练', description: '任务与即时练习', icon: 'Tools' },
  { value: '案例研讨', description: '真实情境与分析', icon: 'ChatLineSquare' },
  { value: '音视频学习', description: '脚本与口播提纲', icon: 'VideoPlay' }
]

const courses = computed(() => settings.value?.courses || [])
const initials = computed(() => (form.full_name || settings.value?.user?.username || '学').trim().charAt(0))

function hydrate(payload: SettingsPayload, preserveCourse = false) {
  settings.value = payload
  userStore.setUser(payload.user as any)
  form.full_name = payload.user.full_name || ''
  form.email = payload.user.email || ''
  form.learning_preferences = [...(payload.learning_preferences || [])]
  const cached = Number(localStorage.getItem('xunkeflow_cid') || 0)
  const candidates = payload.courses.map((item) => item.course_id)
  if (!preserveCourse || !selectedCourseId.value || !candidates.includes(selectedCourseId.value)) {
    selectedCourseId.value = candidates.includes(cached) ? cached : candidates[0] || null
  }
  applyCoursePlan()
}

function applyCoursePlan() {
  const selected = courses.value.find((item) => item.course_id === selectedCourseId.value)
  form.learning_goal = selected?.goal ?? settings.value?.learning_goal ?? ''
  form.weekly_hours = Number(selected?.weekly_hours ?? settings.value?.weekly_hours ?? 6)
  if (selectedCourseId.value) localStorage.setItem('xunkeflow_cid', String(selectedCourseId.value))
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    hydrate(await auth.settings())
  } catch (err: any) {
    error.value = err?.message || '无法读取设置，请稍后重试'
  } finally {
    loading.value = false
  }
}

function validate() {
  if (!form.full_name.trim()) return '请填写姓名'
  if (!/^\S+@\S+\.\S+$/.test(form.email.trim())) return '请输入有效邮箱'
  if (!form.learning_preferences.length) return '请至少选择一种内容偏好'
  if (form.weekly_hours < 1 || form.weekly_hours > 80) return '每周学习时长应在 1 到 80 小时之间'
  return ''
}

async function save() {
  const validation = validate()
  if (validation) return ElMessage.warning(validation)
  saving.value = true
  try {
    const payload = await auth.updateSettings({
      full_name: form.full_name.trim(),
      email: form.email.trim(),
      course_id: selectedCourseId.value,
      learning_goal: form.learning_goal.trim(),
      weekly_hours: form.weekly_hours,
      learning_preferences: form.learning_preferences
    })
    hydrate(payload, true)
    savedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    ElMessage.success('个人资料与学习策略已保存')
  } finally {
    saving.value = false
  }
}

function reset() {
  if (settings.value) hydrate(settings.value, true)
  ElMessage.info('已恢复为最近一次保存的内容')
}

onMounted(load)
</script>

<style scoped>
.settings-page { max-width: 1320px; }
.save-state {
  display: inline-flex; align-items: center; gap: 7px; padding: 7px 11px;
  border: 1px solid var(--border); border-radius: 999px; color: var(--text-secondary); background: #fff; font-size: 12px;
}
.save-state.saved { color: var(--success); border-color: rgba(15,138,114,.25); background: var(--success-bg); }
.settings-skeleton { padding: 28px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; }
.settings-shell {
  display: grid; grid-template-columns: 290px minmax(0, 1fr); overflow: hidden;
  border: 1px solid var(--border); border-radius: var(--radius-xl); background: #fff; box-shadow: var(--shadow-sm);
}
.identity-panel { padding: 34px 28px; border-right: 1px solid var(--border); background: #f8f9ff; }
.identity-mark {
  width: 68px; height: 68px; display: grid; place-items: center; border-radius: 20px;
  background: var(--primary); color: #fff; font-size: 27px; font-weight: 800; box-shadow: 0 14px 30px rgba(79,70,229,.2);
}
.identity-role { display: inline-block; margin-top: 22px; color: var(--primary); font-size: 12px; font-weight: 750; }
.identity-panel h2 { margin-top: 4px; font-size: 22px; }
.identity-panel > p { margin-top: 2px; color: var(--text-secondary); }
.identity-facts { margin-top: 28px; border-top: 1px solid var(--border); }
.identity-facts div { display: flex; justify-content: space-between; gap: 12px; padding: 13px 0; border-bottom: 1px solid var(--border); }
.identity-facts dt { color: var(--text-secondary); font-size: 12px; }
.identity-facts dd { font-weight: 750; }
.strategy-note { display: flex; gap: 10px; margin-top: 24px; padding: 14px; border-radius: 13px; background: #fff; border: 1px solid var(--border); }
.strategy-note > .el-icon { margin-top: 2px; color: var(--primary); font-size: 18px; flex: 0 0 auto; }
.strategy-note b { font-size: 13px; }
.strategy-note p { margin-top: 4px; color: var(--text-secondary); font-size: 12px; line-height: 1.65; }
.settings-form-panel { min-width: 0; padding: 8px 32px 28px; }
.form-section { padding: 26px 0 28px; border-bottom: 1px solid var(--border); }
.form-section > header { display: flex; gap: 13px; align-items: flex-start; margin-bottom: 20px; }
.section-index { color: var(--primary); font-size: 11px; font-weight: 800; letter-spacing: .08em; padding-top: 4px; }
.form-section h2 { font-size: 16px; }
.form-section header p { margin-top: 3px; color: var(--text-secondary); font-size: 12px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.form-grid label, .course-plan label { display: grid; gap: 8px; color: var(--text-secondary); font-size: 12px; font-weight: 650; }
.course-plan { display: grid; grid-template-columns: minmax(210px, .8fr) minmax(0, 1.6fr); gap: 18px; }
.goal-field { grid-row: span 2; }
.hours-field { grid-column: 1 / -1; }
.hours-control { display: grid; grid-template-columns: minmax(0, 1fr) 86px; align-items: center; gap: 22px; padding: 2px 4px 0 10px; }
.hours-control strong { color: var(--text); font-size: 24px; text-align: right; }
.hours-control small { margin-left: 3px; color: var(--text-secondary); font-size: 11px; }
.inline-empty { display: flex; align-items: center; gap: 13px; padding: 16px; border: 1px dashed var(--border); border-radius: var(--radius); background: var(--bg); }
.inline-empty > .el-icon { color: var(--primary); font-size: 22px; }
.inline-empty div { flex: 1; }
.inline-empty b { font-size: 13px; }
.inline-empty p { color: var(--text-secondary); font-size: 12px; }
.preference-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }
.preference-grid :deep(.el-checkbox-button) { width: 100%; }
.preference-grid :deep(.el-checkbox-button__inner) {
  width: 100%; min-height: 94px; display: flex; flex-direction: column; align-items: flex-start; justify-content: space-between;
  padding: 14px; border: 1px solid var(--border) !important; border-radius: 12px !important; box-shadow: none !important; text-align: left;
}
.preference-grid :deep(.el-checkbox-button__inner > .el-icon) { color: var(--primary); font-size: 19px; }
.preference-grid :deep(.el-checkbox-button__inner span) { display: grid; gap: 2px; }
.preference-grid :deep(.el-checkbox-button__inner b) { color: var(--text); font-size: 13px; }
.preference-grid :deep(.el-checkbox-button__inner small) { color: var(--text-secondary); font-size: 10px; }
.preference-grid :deep(.el-checkbox-button.is-checked .el-checkbox-button__inner) { background: var(--primary-bg); border-color: var(--primary) !important; }
.form-actions { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding-top: 24px; }
.form-actions p { display: flex; align-items: center; gap: 7px; color: var(--text-secondary); font-size: 12px; }
.form-actions > div { display: flex; gap: 9px; }
@media (max-width: 1100px) {
  .settings-shell { grid-template-columns: 240px minmax(0, 1fr); }
  .identity-panel { padding: 28px 22px; }
  .preference-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 780px) {
  .settings-shell { grid-template-columns: 1fr; }
  .identity-panel { border-right: 0; border-bottom: 1px solid var(--border); }
  .settings-form-panel { padding: 4px 20px 24px; }
  .form-grid, .course-plan { grid-template-columns: 1fr; }
  .goal-field, .hours-field { grid-row: auto; grid-column: auto; }
  .preference-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .form-actions { align-items: stretch; flex-direction: column; }
  .form-actions > div { justify-content: flex-end; }
}
</style>
