<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="page-title">课程中心</div>
        <div class="page-desc">选择课程后，系统会把诊断、学习资源和评估结果统一归档到该课程。</div>
      </div>
      <el-input v-model="keyword" class="search" placeholder="按课程名称或代码搜索" clearable @keyup.enter="load">
        <template #prefix><el-icon><Search /></el-icon></template>
        <template #append><el-button aria-label="搜索课程" @click="load"><el-icon><Search /></el-icon></el-button></template>
      </el-input>
    </div>

    <div v-if="loading" class="course-board">
      <div v-for="i in 3" :key="i" class="course-card skeleton"><el-skeleton :rows="5" animated /></div>
    </div>

    <div v-else-if="error" class="page-state error">
      <div>
        <div class="state-icon"><el-icon><WarningFilled /></el-icon></div>
        <h3>课程加载失败</h3>
        <p>{{ error }}</p>
        <el-button type="primary" @click="load">重新加载</el-button>
      </div>
    </div>

    <div v-else-if="!list.length" class="page-state">
      <div>
        <div class="state-icon"><el-icon><Reading /></el-icon></div>
        <h3>没有找到课程</h3>
        <p v-if="keyword">当前关键词没有匹配结果，可以清除筛选查看全部课程。</p>
        <p v-else>{{ store.role === 'student' ? '当前暂无可加入课程，请稍后再查看。' : '当前暂无课程，教师可以在课程管理中创建。' }}</p>
        <el-button v-if="keyword" @click="clearFilter">清除筛选</el-button>
      </div>
    </div>

    <div v-else class="course-board">
      <article v-for="c in list" :key="c.id" class="course-card">
        <header class="course-head">
          <span class="course-mark"><el-icon><Reading /></el-icon></span>
          <div class="course-identity">
            <span>{{ c.code || `COURSE-${c.id}` }}</span>
            <h2>{{ c.name }}</h2>
          </div>
          <el-tag v-if="isEnrolled(c.id)" type="success" effect="plain">已加入</el-tag>
        </header>

        <p class="course-desc">{{ c.description || '该课程暂未填写简介。' }}</p>
        <div class="tag-row">
          <el-tag v-for="t in tags(c.tags)" :key="t" size="small" effect="plain">{{ t }}</el-tag>
        </div>

        <div class="meta-grid">
          <div><b>{{ metricValue(c, 'kps') }}</b><span>知识点</span><small v-if="!meta(c).visible">加入后可见</small></div>
          <div><b>{{ metricValue(c, 'questions') }}</b><span>题目</span><small v-if="!meta(c).visible">加入后可见</small></div>
          <div><b>{{ metricValue(c, 'resources') }}</b><span>学习资源</span><small v-if="!meta(c).visible">加入后可见</small></div>
        </div>

        <footer class="course-footer">
          <el-button
            type="primary"
            :loading="enteringId === c.id"
            @click="enter(c)"
          >
            {{ store.role === 'student' && !isEnrolled(c.id) ? '加入并开始学习' : '进入课程' }}
          </el-button>
          <el-button v-if="store.role !== 'student' || isEnrolled(c.id)" @click="router.push(`/experiment/${c.id}`)">查看学习成效</el-button>
        </footer>
      </article>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { course, kp, question, resource } from '@/api'

const router = useRouter()
const store = useUserStore()
const keyword = ref('')
const loading = ref(true)
const error = ref('')
const enteringId = ref<number | null>(null)
const list = ref<any[]>([])
const enrolledIds = ref<Set<number>>(new Set())
type CourseMeta = { visible: boolean; kps: number | string; questions: number | string; resources: number | string }
const metaMap = ref<Record<number, CourseMeta>>({})

const tags = (value: string) => String(value || '').split(',').map((item) => item.trim()).filter(Boolean).slice(0, 4)
const meta = (c: any): CourseMeta => metaMap.value[c.id] || { visible: false, kps: '—', questions: '—', resources: '—' }
const metricValue = (c: any, key: 'kps' | 'questions' | 'resources') => meta(c).visible ? meta(c)[key] : '—'
const isEnrolled = (id: number) => enrolledIds.value.has(id)

function clearFilter() {
  keyword.value = ''
  load()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [courses, mine] = await Promise.all([
      course.list(keyword.value),
      store.role === 'student' ? course.mine().catch(() => []) : Promise.resolve([])
    ])
    list.value = courses
    enrolledIds.value = new Set((mine as any[]).map((row) => Number(row.id)))
    const entries = await Promise.all(courses.map(async (c) => {
      if (store.role === 'student' && !isEnrolled(c.id)) {
        return [c.id, { visible: false, kps: '—', questions: '—', resources: '—' }] as const
      }
      const [kps, qs, rs] = await Promise.all([
        kp.list(c.id).catch(() => []),
        store.role === 'student' ? Promise.resolve([]) : question.list({ course_id: c.id }, true).catch(() => []),
        resource.list({ course_id: c.id }).catch(() => [])
      ])
      return [c.id, { visible: true, kps: kps.length, questions: store.role === 'student' ? '按需' : qs.length, resources: rs.length }] as const
    }))
    metaMap.value = Object.fromEntries(entries)
  } catch (err: any) {
    error.value = err?.message || '请检查服务连接后重试。'
  } finally {
    loading.value = false
  }
}

async function enter(c: any) {
  enteringId.value = c.id
  try {
    if (store.role === 'student' && !isEnrolled(c.id)) {
      await course.enroll({ course_id: c.id, goal: '', weekly_hours: 6 })
      enrolledIds.value.add(c.id)
      ElMessage.success(`已加入《${c.name}》`)
    }
    localStorage.setItem('xunkeflow_cid', String(c.id))
    await router.push(store.role === 'student' ? `/student/pretest/${c.id}` : `/teacher/generate/${c.id}`)
  } catch (err: any) {
    ElMessage.error(err?.message || '暂时无法进入该课程。')
  } finally {
    enteringId.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.search { width: min(360px, 100%); }
.course-board { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.course-card {
  min-height: 365px;
  display: flex;
  flex-direction: column;
  padding: 22px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition: border-color .18s, box-shadow .18s, transform .18s;
}
.course-card:hover { border-color: #c6c9f8; box-shadow: var(--shadow); transform: translateY(-2px); }
.course-card.skeleton { min-height: 320px; }
.course-head { display: grid; grid-template-columns: 44px minmax(0, 1fr) auto; gap: 12px; align-items: start; }
.course-mark { width: 44px; height: 44px; display: grid; place-items: center; border-radius: 12px; color: var(--primary); background: var(--primary-bg); font-size: 20px; }
.course-identity span { color: var(--text-muted); font-size: 11px; font-weight: 750; letter-spacing: .06em; }
.course-identity h2 { margin-top: 3px; font-size: 18px; line-height: 1.35; }
.course-desc { min-height: 70px; margin: 18px 0 12px; color: var(--text-secondary); line-height: 1.75; }
.meta-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; margin: auto 0 18px; overflow: hidden; border: 1px solid var(--border); border-radius: 10px; background: var(--border); }
.meta-grid div { padding: 11px; text-align: center; background: #fafbfe; }
.meta-grid b, .meta-grid span, .meta-grid small { display: block; }
.meta-grid b { font-size: 18px; }
.meta-grid span { margin-top: 2px; color: var(--text-muted); font-size: 11px; }
.meta-grid small { min-height: 16px; margin-top: 2px; color: var(--primary); font-size: 10px; }
.course-footer { display: flex; gap: 8px; }
.course-footer .el-button { flex: 1; }
@media (max-width: 1120px) { .course-board { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 720px) { .course-board { grid-template-columns: 1fr; } .course-footer { flex-direction: column; } }
</style>
