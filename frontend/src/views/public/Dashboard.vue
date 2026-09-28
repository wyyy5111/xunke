<template>
  <div class="page dashboard-page">
    <header class="dashboard-head">
      <div>
        <span class="dashboard-kicker">XunkeFlow</span>
        <h1>{{ greeting }}，{{ store.user?.full_name || store.user?.username }}</h1>
        <p>{{ roleSummary }}</p>
      </div>
      <div class="toolbar-actions">
        <el-button @click="$router.push('/courses')"><el-icon><Reading /></el-icon>课程中心</el-button>
        <el-button type="primary" @click="goPrimary"><el-icon><Position /></el-icon>{{ primaryAction }}</el-button>
      </div>
    </header>

    <el-alert v-if="partialError" type="warning" :closable="false" show-icon class="dashboard-alert">
      部分数据暂未更新：{{ partialError }} <el-button text @click="load">重新加载</el-button>
    </el-alert>

    <div v-if="loading" class="card"><el-skeleton :rows="9" animated /></div>
    <template v-else>
      <section class="overview-strip">
        <article><span class="overview-icon"><el-icon><Reading /></el-icon></span><div><span>可用课程</span><b>{{ courses.length }}</b><small>课程资料与学习任务</small></div></article>
        <article><span class="overview-icon"><el-icon><Connection /></el-icon></span><div><span>最近任务</span><b>{{ runs.length }}</b><small>{{ successfulRuns }} 次已完成</small></div></article>
        <article><span class="overview-icon"><el-icon><Checked /></el-icon></span><div><span>平均内容质量</span><b>{{ Math.round(commandCenter.kpis?.avg_quality || 0) }}</b><small>当前课程综合评分</small></div></article>
        <article><span class="overview-icon"><el-icon><TrendCharts /></el-icon></span><div><span>学习提升</span><b :class="Number(commandCenter.kpis?.improvement || 0) >= 0 ? 'text-success' : 'text-danger'">{{ signed(commandCenter.kpis?.improvement || 0) }}</b><small>前后测平均变化</small></div></article>
      </section>

      <section class="dashboard-grid">
        <div class="course-section">
          <div class="section-head"><div><h2>课程工作区</h2><p>进入课程继续诊断、学习、生成或审核。</p></div><el-button text @click="$router.push('/courses')">查看全部</el-button></div>
          <div v-if="courses.length" class="course-list">
            <article v-for="courseItem in courses.slice(0, 4)" :key="courseItem.id">
              <span class="course-symbol"><el-icon><Reading /></el-icon></span>
              <div><small>{{ courseItem.code || `COURSE-${courseItem.id}` }}</small><b>{{ courseItem.name }}</b><p>{{ courseItem.description || '暂无课程简介' }}</p></div>
              <el-button type="primary" plain @click="enterCourse(courseItem.id)">进入</el-button>
            </article>
          </div>
          <div v-else class="inline-empty"><el-icon><Reading /></el-icon><b>暂无可用课程</b><span>前往课程中心查看或创建课程。</span><el-button type="primary" @click="$router.push('/courses')">打开课程中心</el-button></div>
        </div>

        <aside class="activity-section">
          <div class="section-head"><div><h2>最近任务</h2><p>课程处理与内容生成状态。</p></div><el-button text @click="$router.push(agentCenterPath)">查看流程</el-button></div>
          <div v-if="runs.length" class="activity-list">
            <button v-for="run in runs.slice(0, 6)" :key="run.id" type="button" @click="$router.push(agentCenterPath)">
              <i :class="normalizeStatus(run.status)"></i>
              <span><b>{{ flowLabel(run.workflow) }}</b><small>{{ formatTime(run.finished_at || run.started_at) }}</small></span>
              <strong>{{ Math.round((run.progress || 0) * 100) }}%</strong>
            </button>
          </div>
          <div v-else class="inline-empty small"><el-icon><Connection /></el-icon><b>暂无任务记录</b><span>进入课程并启动一次学习或生成任务。</span></div>
        </aside>
      </section>

      <section class="journey-section">
        <div class="section-head"><div><h2>课程闭环</h2><p>每个环节都有明确输入、输出和下一步动作。</p></div><span :class="['status-badge', store.demoMode ? 'demo' : 'live']">{{ store.demoMode ? '演示模式' : '在线模式' }}</span></div>
        <div class="journey-list">
          <article v-for="(item, index) in journey" :key="item.title"><span>{{ index + 1 }}</span><div><b>{{ item.title }}</b><p>{{ item.desc }}</p></div></article>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { agent, course, system } from '@/api'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const store = useUserStore()
const loading = ref(true)
const partialError = ref('')
const courses = ref<any[]>([])
const runs = ref<any[]>([])
const commandCenter = ref<any>({})

const role = computed(() => store.role)
const activeCourseId = ref(localStorage.getItem('xunkeflow_cid') || '')
const activeCourse = computed(() => activeCourseId.value)
const successfulRuns = computed(() => runs.value.filter((run) => run.status === 'success').length)
const agentCenterPath = computed(() => role.value === 'student' ? `/student/agents/${activeCourse.value}` : role.value === 'admin' ? '/admin/agents' : '/teacher/agents')
const primaryAction = computed(() => role.value === 'student' ? '继续学习' : role.value === 'teacher' ? '进入教学工作台' : '查看运营数据')
const roleSummary = computed(() => role.value === 'student' ? '从课程诊断开始，继续你的个性化学习任务。' : role.value === 'teacher' ? '处理课程资料、生成学习资源并完成教师审核。' : '查看课程、用户、任务和内容质量的整体运行情况。')
const greeting = computed(() => new Date().getHours() < 12 ? '上午好' : new Date().getHours() < 18 ? '下午好' : '晚上好')

const journey = [
  { title: '课程准备', desc: '上传资料，形成知识点与课程检索索引。' },
  { title: '学习诊断', desc: '通过前测识别基础水平和薄弱知识点。' },
  { title: '内容学习', desc: '按学习路径使用讲义、导图和分层练习。' },
  { title: '质量审核', desc: '核对课程引用、答案一致性和发布建议。' },
  { title: '成效评估', desc: '完成后测、错题补救并导出学习报告。' }
]

const signed = (value: number) => `${Number(value) >= 0 ? '+' : ''}${Number(value || 0).toFixed(1)}`
const flowLabel = (value: string) => ({ full_pipeline: '完整课程任务', parse: '课程资料处理', generate: '学习资源生成', diagnose: '学习诊断' }[value] || value || '课程任务')
const normalizeStatus = (value: string) => ['success', 'failed', 'running'].includes(value) ? value : 'pending'
const formatTime = (value: string) => value ? new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : '刚刚'

function goPrimary() {
  router.push(role.value === 'student' ? '/student' : role.value === 'teacher' ? '/teacher' : '/admin')
}
function enterCourse(id: number) {
  activeCourseId.value = String(id)
  localStorage.setItem('xunkeflow_cid', String(id))
  router.push(role.value === 'student' ? `/student/profile/${id}` : `/teacher/generate/${id}`)
}

async function load() {
  loading.value = true
  partialError.value = ''
  let failed = 0
  try {
    courses.value = await course.list()
    const validIds = courses.value.map((item) => String(item.id))
    if (!validIds.includes(activeCourse.value) && validIds[0]) {
      activeCourseId.value = validIds[0]
      localStorage.setItem('xunkeflow_cid', validIds[0])
    }
  } catch { failed += 1 }
  const currentId = activeCourseId.value
  const results = await Promise.allSettled([
    agent.runs(currentId),
    currentId ? agent.commandCenter(currentId, true) : Promise.resolve({}),
    system.info()
  ])
  if (results[0].status === 'fulfilled') runs.value = results[0].value
  if (results[1].status === 'fulfilled') commandCenter.value = results[1].value
  if (results[2].status === 'fulfilled') {
    store.demoMode = !!(results[2].value.demo_mode ?? results[2].value.is_mock_llm)
    store.engineInfo = results[2].value
  }
  failed += results.filter((item) => item.status === 'rejected').length
  if (failed) partialError.value = `${failed} 项数据请求失败`
  loading.value = false
}

onMounted(load)
</script>

<style scoped>
.dashboard-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin-bottom: 22px; }
.dashboard-kicker { color: var(--primary); font-size: 12px; font-weight: 800; letter-spacing: .08em; }
.dashboard-head h1 { margin: 4px 0 6px; font-size: 30px; letter-spacing: -.035em; }
.dashboard-head p { color: var(--text-secondary); }
.dashboard-alert { margin-bottom: 16px; }
.overview-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; overflow: hidden; margin-bottom: 16px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--border); box-shadow: var(--shadow-sm); }
.overview-strip article { display: grid; grid-template-columns: 42px 1fr; gap: 12px; padding: 18px; background: #fff; }
.overview-icon { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 11px; color: var(--primary); background: var(--primary-bg); font-size: 18px; }
.overview-strip span, .overview-strip b, .overview-strip small { display: block; }
.overview-strip article > div > span { color: var(--text-secondary); font-size: 12px; }.overview-strip b { margin-top: 2px; font-size: 23px; line-height: 1.15; }.overview-strip small { margin-top: 3px; color: var(--text-muted); font-size: 11px; }
.dashboard-grid { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(320px, .7fr); gap: 16px; }
.course-section, .activity-section, .journey-section { padding: 20px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; margin-bottom: 14px; }.section-head h2 { font-size: 16px; }.section-head p { margin-top: 2px; color: var(--text-secondary); font-size: 12px; }
.course-list { display: grid; gap: 8px; }.course-list article { display: grid; grid-template-columns: 42px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 13px; border: 1px solid var(--border); border-radius: 11px; }.course-symbol { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 10px; color: var(--primary); background: var(--primary-bg); }.course-list small, .course-list b, .course-list p { display: block; }.course-list small { color: var(--text-muted); font-size: 10px; font-weight: 750; letter-spacing: .06em; }.course-list b { font-size: 14px; }.course-list p { overflow: hidden; color: var(--text-secondary); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.activity-list { display: grid; gap: 7px; }.activity-list button { width: 100%; display: grid; grid-template-columns: 9px 1fr auto; gap: 10px; align-items: center; padding: 11px; border: 0; border-radius: 9px; background: #f8f9fc; color: var(--text); text-align: left; cursor: pointer; }.activity-list button:hover { background: var(--primary-bg); }.activity-list i { width: 8px; height: 8px; border-radius: 50%; background: #a8b1c0; }.activity-list i.success { background: var(--success); }.activity-list i.failed { background: var(--danger); }.activity-list i.running { background: var(--primary); }.activity-list b, .activity-list small { display: block; }.activity-list small { color: var(--text-muted); }.activity-list strong { font-size: 12px; }
.inline-empty { min-height: 240px; display: flex; align-items: center; justify-content: center; flex-direction: column; color: var(--text-muted); text-align: center; }.inline-empty.small { min-height: 220px; }.inline-empty .el-icon { margin-bottom: 8px; color: var(--primary-light); font-size: 30px; }.inline-empty b { color: var(--text); }.inline-empty span { margin: 4px 0 12px; font-size: 12px; }
.journey-section { margin-top: 16px; }.journey-list { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; }.journey-list article { display: grid; grid-template-columns: 28px 1fr; gap: 9px; padding: 13px; border-top: 2px solid var(--primary); background: #fafbfe; }.journey-list article > span { width: 26px; height: 26px; display: grid; place-items: center; border-radius: 8px; color: var(--primary); background: var(--primary-bg); font-weight: 800; }.journey-list b { font-size: 13px; }.journey-list p { margin-top: 3px; color: var(--text-secondary); font-size: 11px; line-height: 1.55; }
@media (max-width: 1100px) { .overview-strip { grid-template-columns: repeat(2, 1fr); }.dashboard-grid { grid-template-columns: 1fr; }.journey-list { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 720px) { .dashboard-head { align-items: stretch; flex-direction: column; }.overview-strip, .journey-list { grid-template-columns: 1fr; }.course-list article { grid-template-columns: 38px minmax(0, 1fr); }.course-list article .el-button { grid-column: 1 / -1; } }
</style>
