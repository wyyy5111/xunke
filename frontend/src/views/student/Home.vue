<template>
  <div class="page student-home">
    <header class="page-header">
      <div>
        <div class="page-title">学习工作台</div>
        <div class="page-desc">{{ user?.full_name || user?.username || '同学' }}，查看课程阶段、测评进展和下一项学习任务。</div>
      </div>
      <div class="header-actions">
        <el-select
          v-if="courseRows.length"
          v-model="selectedCourseId"
          class="course-selector"
          aria-label="选择当前课程"
          @change="selectCourse"
        >
          <el-option v-for="row in courseRows" :key="row.course.id" :label="row.course.name" :value="Number(row.course.id)" />
        </el-select>
        <el-button type="primary" @click="router.push('/courses')">
          <el-icon><Reading /></el-icon>
          课程中心
        </el-button>
      </div>
    </header>

    <div v-if="loading" class="loading-workspace" aria-label="正在加载学习工作台">
      <el-skeleton animated>
        <template #template>
          <div class="skeleton-metrics">
            <el-skeleton-item v-for="item in 4" :key="item" variant="rect" />
          </div>
          <div class="skeleton-main">
            <el-skeleton-item variant="rect" />
            <el-skeleton-item variant="rect" />
          </div>
        </template>
      </el-skeleton>
    </div>

    <div v-else-if="error" class="page-state error">
      <div>
        <div class="state-icon"><el-icon><WarningFilled /></el-icon></div>
        <h3>学习工作台加载失败</h3>
        <p>{{ error }}</p>
        <el-button type="primary" @click="load">重新加载</el-button>
      </div>
    </div>

    <template v-else>
      <el-alert
        v-if="partialFailures"
        class="partial-alert"
        type="warning"
        :closable="false"
        show-icon
        title="部分学习进度暂未同步"
      >
        已显示可用数据，本次有 {{ partialFailures }} 项课程状态未完成同步。
        <el-button text @click="load">重新加载</el-button>
      </el-alert>

      <div v-if="!courseRows.length" class="page-state">
        <div>
          <div class="state-icon"><el-icon><Reading /></el-icon></div>
          <h3>还没有加入课程</h3>
          <p>前往课程中心选择课程，完成前测后即可生成学习画像与个性化路径。</p>
          <el-button type="primary" @click="router.push('/courses')">浏览可选课程</el-button>
        </div>
      </div>

      <template v-else>
        <section class="overview-strip" aria-label="学习概览">
          <article>
            <span class="metric-mark"><el-icon><Reading /></el-icon></span>
            <div><small>已选课程</small><strong>{{ courseRows.length }}</strong><p>{{ profileCompletedCount }} 门已完成前测画像</p></div>
          </article>
          <article>
            <span class="metric-mark"><el-icon><EditPen /></el-icon></span>
            <div><small>平均前测</small><strong>{{ avgPre }}<em>分</em></strong><p>{{ profileCompletedCount }} 门课程已完成</p></div>
          </article>
          <article>
            <span class="metric-mark success"><el-icon><TrendCharts /></el-icon></span>
            <div><small>平均后测</small><strong>{{ avgPost }}<em>分</em></strong><p>{{ postCompletedCount }} 门课程已完成后测</p></div>
          </article>
          <article>
            <span class="metric-mark warning"><el-icon><WarningFilled /></el-icon></span>
            <div><small>未解决错题</small><strong>{{ wrongCount }}</strong><p>{{ wrongCourseCount }} 门课程需要巩固</p></div>
          </article>
        </section>

        <div class="learning-workspace">
          <section class="course-panel">
            <header class="section-head">
              <div><h2>课程学习状态</h2><p>选择课程后，右侧会显示对应阶段与下一步行动。</p></div>
              <span class="course-count">{{ completedLoopCount }}/{{ courseRows.length }} 已完成闭环</span>
            </header>

            <div class="course-list-head" aria-hidden="true">
              <span>课程</span><span>当前阶段</span><span>测评成绩</span><span>错题</span><span>下一步</span>
            </div>
            <div class="learning-course-list">
              <article
                v-for="row in courseRows"
                :key="row.course.id"
                class="learning-course-row"
                :class="{ selected: Number(row.course.id) === selectedCourseId }"
                @click="selectCourse(Number(row.course.id))"
              >
                <div class="course-identity">
                  <span class="course-mark"><el-icon><Reading /></el-icon></span>
                  <div>
                    <small>{{ row.course.code || `COURSE-${row.course.id}` }}</small>
                    <b>{{ row.course.name }}</b>
                    <div class="course-progress"><i :style="{ width: `${progressFor(row)}%` }"></i></div>
                  </div>
                </div>
                <div class="stage-cell">
                  <span :class="['stage-badge', stageTone(row)]">{{ stageText(row) }}</span>
                  <small>{{ progressFor(row) }}% 学习闭环</small>
                </div>
                <div class="score-cell">
                  <span><small>前测</small><b>{{ scoreText(row.profile?.pre_score) }}</b></span>
                  <el-icon><Right /></el-icon>
                  <span><small>后测</small><b :class="{ success: hasPostTest(row) }">{{ hasPostTest(row) ? scoreText(row.profile?.post_score) : '--' }}</b></span>
                </div>
                <div class="wrong-cell" :class="{ active: row.wrongCount }">
                  <strong>{{ row.wrongCount }}</strong><small>道</small>
                </div>
                <div class="row-action" @click.stop>
                  <el-button size="small" :type="Number(row.course.id) === selectedCourseId ? 'primary' : ''" plain @click="router.push(nextAction(row).to)">
                    {{ nextAction(row).label }}
                  </el-button>
                </div>
              </article>
            </div>
          </section>

          <aside v-if="selectedRow" class="stage-panel">
            <header class="stage-header">
              <span>{{ selectedRow.course.code || `COURSE-${selectedRow.course.id}` }}</span>
              <h2>{{ selectedRow.course.name }}</h2>
              <div class="stage-summary">
                <b>{{ stageText(selectedRow) }}</b>
                <strong>{{ progressFor(selectedRow) }}%</strong>
              </div>
              <div class="stage-progress"><i :style="{ width: `${progressFor(selectedRow)}%` }"></i></div>
            </header>

            <ol class="phase-track" aria-label="学习阶段">
              <li v-for="(step, index) in stageSteps" :key="step.title" :class="stepClass(selectedRow, index)">
                <span class="phase-index"><el-icon v-if="stepClass(selectedRow, index) === 'done'"><Check /></el-icon><template v-else>{{ index + 1 }}</template></span>
                <div><b>{{ step.title }}</b><small>{{ step.description }}</small></div>
              </li>
            </ol>

            <div class="next-action">
              <small>下一步行动</small>
              <h3>{{ nextAction(selectedRow).label }}</h3>
              <p>{{ nextAction(selectedRow).description }}</p>
              <el-button type="primary" @click="router.push(nextAction(selectedRow).to)">
                {{ nextAction(selectedRow).buttonText }}
                <el-icon><ArrowRight /></el-icon>
              </el-button>
            </div>

            <div class="secondary-actions">
              <button type="button" @click="router.push(`/student/profile/${selectedRow.course.id}`)"><el-icon><User /></el-icon><span>学习画像</span></button>
              <button type="button" @click="router.push(`/student/lecture/${selectedRow.course.id}`)"><el-icon><Document /></el-icon><span>课程讲义</span></button>
              <button type="button" @click="router.push(`/student/exercise/${selectedRow.course.id}`)"><el-icon><Tickets /></el-icon><span>分层练习</span></button>
              <button type="button" @click="router.push(`/student/report/${selectedRow.course.id}`)"><el-icon><Download /></el-icon><span>学习报告</span></button>
            </div>
          </aside>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { course } from '@/api'
import request from '@/api/request'
import { useUserStore } from '@/stores/user'

interface CourseLearningRow {
  course: any
  profile: any | null
  path: any | null
  wrongCount: number
}

const router = useRouter()
const store = useUserStore()
const user = computed(() => store.user)
const courseRows = ref<CourseLearningRow[]>([])
const selectedCourseId = ref(Number(localStorage.getItem('xunkeflow_cid') || 0))
const loading = ref(true)
const error = ref('')
const partialFailures = ref(0)

const stageSteps = [
  { title: '前测诊断', description: '识别知识基础与薄弱点' },
  { title: '学习画像', description: '形成学习目标与建议' },
  { title: '路径学习', description: '按知识依赖推进任务' },
  { title: '练习巩固', description: '处理练习与未解决错题' },
  { title: '后测评估', description: '验证提升并生成报告' }
]

const profileRows = computed(() => courseRows.value.filter((row) => row.profile))
const postRows = computed(() => courseRows.value.filter((row) => hasPostTest(row)))
const profileCompletedCount = computed(() => profileRows.value.length)
const postCompletedCount = computed(() => postRows.value.length)
const completedLoopCount = computed(() => postRows.value.length)
const wrongCount = computed(() => courseRows.value.reduce((sum, row) => sum + row.wrongCount, 0))
const wrongCourseCount = computed(() => courseRows.value.filter((row) => row.wrongCount > 0).length)
const avgPre = computed(() => profileRows.value.length
  ? Math.round(profileRows.value.reduce((sum, row) => sum + Number(row.profile.pre_score || 0), 0) / profileRows.value.length)
  : 0)
// 后测均分只统计 post_score > 0 的已完成课程，避免未完成课程以 0 分拉低结果。
const avgPost = computed(() => postRows.value.length
  ? Math.round(postRows.value.reduce((sum, row) => sum + Number(row.profile.post_score), 0) / postRows.value.length)
  : 0)
const selectedRow = computed(() => courseRows.value.find((row) => Number(row.course.id) === selectedCourseId.value) || courseRows.value[0] || null)

function hasPostTest(row: CourseLearningRow) {
  return Number(row.profile?.post_score || 0) > 0
}

function pathRatio(row: CourseLearningRow) {
  const nodes = Array.isArray(row.path?.nodes) ? row.path.nodes.length : 0
  if (!nodes) return 0
  return Math.min(1, Number(row.path?.completed_nodes || 0) / nodes)
}

function progressFor(row: CourseLearningRow) {
  if (!row.profile) return 0
  if (hasPostTest(row)) return 100
  const ratio = pathRatio(row)
  if (ratio >= 1) return 80
  if (ratio > 0) return Math.round(40 + ratio * 40)
  if (row.wrongCount) return 60
  return 40
}

function completedStageCount(row: CourseLearningRow) {
  const progress = progressFor(row)
  if (progress >= 100) return 5
  if (progress >= 80) return 4
  if (progress > 40) return 3
  if (progress >= 40) return 2
  return 0
}

function stepClass(row: CourseLearningRow, index: number) {
  const completed = completedStageCount(row)
  if (index < completed) return 'done'
  if (index === completed && completed < stageSteps.length) return 'current'
  return 'pending'
}

function stageText(row: CourseLearningRow) {
  if (!row.profile) return '待完成前测'
  if (hasPostTest(row)) return '已完成学习闭环'
  if (row.wrongCount) return '错题补救中'
  if (progressFor(row) >= 80) return '待完成后测'
  if (progressFor(row) > 40) return '路径学习中'
  return '画像已生成'
}

function stageTone(row: CourseLearningRow) {
  if (hasPostTest(row)) return 'success'
  if (row.wrongCount) return 'warning'
  if (!row.profile) return 'pending'
  return 'active'
}

function scoreText(value: unknown) {
  return `${Math.round(Number(value || 0))} 分`
}

function nextAction(row: CourseLearningRow) {
  const id = Number(row.course.id)
  if (!row.profile) {
    return { label: '完成前测', buttonText: '开始前测', description: '完成课程前测，系统将据此生成学习画像与薄弱点分析。', to: `/student/pretest/${id}` }
  }
  if (row.wrongCount) {
    return { label: `处理 ${row.wrongCount} 道错题`, buttonText: '进入错题补救', description: '先对未解决错题进行复盘，再继续课程学习或后测。', to: `/student/wrong/${id}` }
  }
  if (hasPostTest(row)) {
    return { label: '查看前后测结果', buttonText: '查看学习成效', description: '学习闭环已完成，可查看知识点提升与个人学习报告。', to: `/student/compare/${id}` }
  }
  if (progressFor(row) < 80) {
    return { label: '继续学习路径', buttonText: '打开学习路径', description: '按照知识点依赖与当前进度继续完成课程学习任务。', to: `/student/path/${id}` }
  }
  return { label: '完成后测评估', buttonText: '开始后测', description: '路径任务已完成，通过后测验证掌握度提升并形成对比。', to: `/student/posttest/${id}` }
}

function selectCourse(value: number | string) {
  selectedCourseId.value = Number(value)
  if (selectedCourseId.value) localStorage.setItem('xunkeflow_cid', String(selectedCourseId.value))
  else localStorage.removeItem('xunkeflow_cid')
}

async function loadCourseState(item: any): Promise<CourseLearningRow> {
  let profileData: any = null
  let pathData: any = null
  let wrongRows: any[] = []
  if (item.has_profile !== false) {
    try {
      profileData = await request.get<any>(`/profiles/${item.id}`, { silent: true })
    } catch (err: any) {
      if (err?.status !== 404) partialFailures.value += 1
    }
  }
  if (profileData) {
    try {
      pathData = await request.get<any>(`/profiles/${item.id}/path`, { silent: true })
    } catch {
      partialFailures.value += 1
    }
  }
  try {
    const rows = await request.get<any[]>(`/wrong/${item.id}`, { silent: true })
    wrongRows = Array.isArray(rows) ? rows : []
  } catch {
    partialFailures.value += 1
  }
  return { course: item, profile: profileData, path: pathData, wrongCount: wrongRows.length }
}

async function load() {
  loading.value = true
  error.value = ''
  partialFailures.value = 0
  try {
    const [enrolled, activeCourses] = await Promise.all([course.mine(), course.list()])
    const activeIds = new Set((Array.isArray(activeCourses) ? activeCourses : []).map((item) => Number(item.id)))
    const available = (Array.isArray(enrolled) ? enrolled : []).filter((item) => activeIds.has(Number(item.id)))
    courseRows.value = await Promise.all(available.map(loadCourseState))
    const validIds = courseRows.value.map((row) => Number(row.course.id))
    if (!validIds.includes(selectedCourseId.value)) selectCourse(validIds[0] || 0)
  } catch (err: any) {
    courseRows.value = []
    error.value = err?.message || '请检查后端服务后重新加载。'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.student-home { --panel-border: #e2e7f0; }
.header-actions { display: flex; align-items: center; justify-content: flex-end; gap: 9px; flex-wrap: wrap; }
.course-selector { width: 250px; }
.partial-alert { margin-bottom: 16px; }
.partial-alert :deep(.el-alert__content) { line-height: 1.6; }

.loading-workspace { padding: 18px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; }
.skeleton-metrics, .skeleton-main { display: grid; gap: 12px; }
.skeleton-metrics { grid-template-columns: repeat(4, 1fr); }
.skeleton-metrics .el-skeleton__item { height: 112px; }
.skeleton-main { grid-template-columns: minmax(0, 1.55fr) minmax(300px, .7fr); margin-top: 16px; }
.skeleton-main .el-skeleton__item { height: 520px; }

.overview-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 16px;
  border: 1px solid var(--panel-border);
  border-radius: var(--radius-lg);
  background: #fff;
  box-shadow: var(--shadow-sm);
}
.overview-strip article { min-width: 0; display: grid; grid-template-columns: 42px 1fr; gap: 13px; align-items: center; padding: 20px 22px; }
.overview-strip article + article { border-left: 1px solid var(--border-light); }
.metric-mark { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 11px; color: var(--primary); background: var(--primary-bg); font-size: 19px; }
.metric-mark.success { color: var(--success); background: var(--success-bg); }
.metric-mark.warning { color: var(--warning); background: var(--warning-bg); }
.overview-strip small, .overview-strip strong, .overview-strip p { display: block; }
.overview-strip small { color: var(--text-secondary); font-size: 12px; font-weight: 650; }
.overview-strip strong { margin-top: 2px; font-size: 27px; line-height: 1.15; letter-spacing: -.035em; }
.overview-strip strong em { margin-left: 3px; color: var(--text-secondary); font-size: 11px; font-style: normal; font-weight: 650; letter-spacing: 0; }
.overview-strip p { overflow: hidden; margin-top: 4px; color: var(--text-muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }

.learning-workspace { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(310px, .7fr); gap: 16px; align-items: start; }
.course-panel, .stage-panel { overflow: hidden; border: 1px solid var(--panel-border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 20px 22px; border-bottom: 1px solid var(--border-light); }
.section-head h2 { font-size: 16px; }
.section-head p { margin-top: 3px; color: var(--text-secondary); font-size: 12px; }
.course-count { min-height: 27px; display: inline-flex; align-items: center; padding: 3px 9px; border-radius: 999px; color: var(--success); background: var(--success-bg); font-size: 11px; font-weight: 700; white-space: nowrap; }

.course-list-head, .learning-course-row { display: grid; grid-template-columns: minmax(220px, 1.35fr) minmax(130px, .8fr) 150px 55px 112px; gap: 14px; align-items: center; }
.course-list-head { padding: 9px 20px; color: var(--text-muted); background: #f8f9fc; font-size: 11px; font-weight: 700; }
.learning-course-row { position: relative; min-height: 98px; padding: 15px 20px; border-top: 1px solid var(--border-light); cursor: pointer; transition: background .18s ease, box-shadow .18s ease; }
.learning-course-row:first-child { border-top: 0; }
.learning-course-row:hover { background: #fafbff; }
.learning-course-row.selected { background: #fbfbff; box-shadow: inset 3px 0 var(--primary); }
.course-identity { min-width: 0; display: grid; grid-template-columns: 42px minmax(0, 1fr); gap: 12px; align-items: center; }
.course-mark { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 11px; color: var(--primary); background: var(--primary-bg); font-size: 18px; }
.course-identity small, .course-identity b { display: block; }
.course-identity small { color: var(--text-muted); font-size: 10px; font-weight: 750; letter-spacing: .06em; }
.course-identity b { overflow: hidden; margin-top: 1px; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.course-progress { height: 4px; overflow: hidden; margin-top: 7px; border-radius: 999px; background: #e9edf4; }
.course-progress i { display: block; min-width: 0; height: 100%; border-radius: inherit; background: var(--primary); transition: width .35s ease; }
.stage-cell { min-width: 0; }
.stage-cell small { display: block; margin-top: 5px; color: var(--text-muted); font-size: 10px; }
.stage-badge { display: inline-flex; align-items: center; min-height: 24px; padding: 2px 8px; border-radius: 999px; font-size: 10px; font-weight: 700; }
.stage-badge.pending { color: var(--text-secondary); background: var(--bg-secondary); }
.stage-badge.active { color: var(--primary); background: var(--primary-bg); }
.stage-badge.warning { color: var(--warning); background: var(--warning-bg); }
.stage-badge.success { color: var(--success); background: var(--success-bg); }
.score-cell { display: flex; align-items: center; gap: 8px; }
.score-cell > span { min-width: 48px; }
.score-cell small, .score-cell b { display: block; }
.score-cell small { color: var(--text-muted); font-size: 9px; }
.score-cell b { font-size: 12px; }
.score-cell b.success { color: var(--success); }
.score-cell > .el-icon { color: var(--text-muted); font-size: 12px; }
.wrong-cell { color: var(--text-muted); }
.wrong-cell strong { font-size: 18px; }
.wrong-cell small { margin-left: 2px; font-size: 10px; }
.wrong-cell.active { color: var(--warning); }
.row-action { display: flex; justify-content: flex-end; }

.stage-panel { position: sticky; top: 14px; }
.stage-header { padding: 22px 22px 18px; border-bottom: 1px solid var(--border-light); }
.stage-header > span { color: var(--primary); font-size: 10px; font-weight: 800; letter-spacing: .08em; }
.stage-header h2 { overflow: hidden; margin-top: 4px; font-size: 18px; text-overflow: ellipsis; white-space: nowrap; }
.stage-summary { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-top: 17px; }
.stage-summary b { font-size: 12px; }
.stage-summary strong { color: var(--primary); font-size: 22px; line-height: 1; }
.stage-progress { height: 6px; overflow: hidden; margin-top: 9px; border-radius: 999px; background: #e9edf4; }
.stage-progress i { display: block; height: 100%; border-radius: inherit; background: var(--primary); transition: width .35s ease; }

.phase-track { list-style: none; padding: 18px 22px 8px; }
.phase-track li { position: relative; display: grid; grid-template-columns: 28px 1fr; gap: 11px; min-height: 58px; }
.phase-track li:not(:last-child)::after { content: ''; position: absolute; top: 28px; bottom: 0; left: 13px; width: 1px; background: #dfe4ec; }
.phase-index { position: relative; z-index: 1; width: 27px; height: 27px; display: grid; place-items: center; border: 1px solid var(--border); border-radius: 9px; background: #fff; color: var(--text-muted); font-size: 10px; font-weight: 750; }
.phase-track b, .phase-track small { display: block; }
.phase-track b { padding-top: 2px; color: var(--text-secondary); font-size: 12px; }
.phase-track small { margin-top: 2px; color: var(--text-muted); font-size: 10px; }
.phase-track li.done .phase-index { border-color: transparent; color: var(--success); background: var(--success-bg); }
.phase-track li.done:not(:last-child)::after { background: #b9dfd5; }
.phase-track li.done b { color: var(--text); }
.phase-track li.current .phase-index { border-color: transparent; color: #fff; background: var(--primary); box-shadow: 0 0 0 4px var(--primary-bg); }
.phase-track li.current b { color: var(--primary-dark); }

.next-action { margin: 0 18px 18px; padding: 17px; border-left: 3px solid var(--primary); border-radius: 0 10px 10px 0; background: #f7f7ff; }
.next-action > small { color: var(--primary); font-size: 10px; font-weight: 800; letter-spacing: .08em; }
.next-action h3 { margin-top: 4px; font-size: 15px; }
.next-action p { margin: 5px 0 12px; color: var(--text-secondary); font-size: 11px; line-height: 1.65; }
.secondary-actions { display: grid; grid-template-columns: repeat(2, 1fr); border-top: 1px solid var(--border-light); }
.secondary-actions button { min-height: 48px; display: flex; align-items: center; gap: 7px; padding: 0 14px; border: 0; border-right: 1px solid var(--border-light); border-bottom: 1px solid var(--border-light); background: #fff; color: var(--text-secondary); cursor: pointer; font-size: 11px; }
.secondary-actions button:nth-child(even) { border-right: 0; }
.secondary-actions button:nth-last-child(-n + 2) { border-bottom: 0; }
.secondary-actions button:hover { color: var(--primary); background: var(--primary-bg); }

@media (max-width: 1240px) {
  .learning-workspace { grid-template-columns: 1fr; }
  .stage-panel { position: static; display: grid; grid-template-columns: minmax(240px, .7fr) minmax(330px, 1fr); }
  .stage-header { border-right: 1px solid var(--border-light); }
  .phase-track { grid-row: span 2; }
  .next-action { align-self: start; }
  .secondary-actions { grid-column: 1 / -1; }
}
@media (max-width: 980px) {
  .overview-strip { grid-template-columns: repeat(2, 1fr); }
  .overview-strip article:nth-child(3) { border-left: 0; border-top: 1px solid var(--border-light); }
  .overview-strip article:nth-child(4) { border-top: 1px solid var(--border-light); }
  .course-list-head { display: none; }
  .learning-course-row { grid-template-columns: minmax(0, 1fr) auto; gap: 12px 18px; }
  .stage-cell { text-align: right; }
  .score-cell, .wrong-cell, .row-action { padding-top: 10px; border-top: 1px solid var(--border-light); }
  .row-action { align-self: stretch; align-items: center; }
}
@media (max-width: 760px) {
  .page-header { align-items: stretch; }
  .header-actions { justify-content: stretch; }
  .course-selector { width: 100%; }
  .header-actions .el-button { width: 100%; margin-left: 0; }
  .skeleton-metrics, .skeleton-main, .overview-strip { grid-template-columns: 1fr; }
  .overview-strip article + article { border-left: 0; border-top: 1px solid var(--border-light); }
  .section-head { align-items: flex-start; flex-direction: column; }
  .learning-course-row { padding: 15px; }
  .score-cell { grid-column: 1 / -1; }
  .wrong-cell { display: flex; align-items: baseline; justify-content: flex-start; }
  .row-action { justify-content: flex-end; }
  .stage-panel { display: block; }
  .stage-header { border-right: 0; }
}
</style>
