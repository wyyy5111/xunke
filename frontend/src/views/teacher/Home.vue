<template>
  <div class="page teacher-home">
    <header class="page-header">
      <div>
        <div class="page-title">教师工作台</div>
        <div class="page-desc">查看课程运行状态，处理资源审核与班级学习风险。</div>
      </div>
      <div class="header-actions">
        <el-select
          v-if="courses.length"
          v-model="selectedCourseId"
          class="course-selector"
          aria-label="选择当前课程"
          @change="selectCourse"
        >
          <el-option v-for="item in courses" :key="item.id" :label="item.name" :value="Number(item.id)" />
        </el-select>
        <el-button @click="router.push('/teacher/courses')">
          <el-icon><FolderOpened /></el-icon>
          课程管理
        </el-button>
        <el-button type="primary" :disabled="!selectedCourseId" @click="goSelected('generate')">
          <el-icon><MagicStick /></el-icon>
          生成教学资源
        </el-button>
      </div>
    </header>

    <div v-if="loading" class="loading-workspace" aria-label="正在加载教师工作台">
      <el-skeleton animated>
        <template #template>
          <div class="skeleton-metrics">
            <el-skeleton-item v-for="item in 4" :key="item" variant="rect" />
          </div>
          <el-skeleton-item class="skeleton-table" variant="rect" />
          <div class="skeleton-bottom">
            <el-skeleton-item v-for="item in 3" :key="item" variant="rect" />
          </div>
        </template>
      </el-skeleton>
    </div>

    <div v-else-if="error" class="page-state error">
      <div>
        <div class="state-icon"><el-icon><WarningFilled /></el-icon></div>
        <h3>教师工作台加载失败</h3>
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
        title="部分课程指标暂未同步"
      >
        本次有 {{ partialFailures }} 项数据请求未完成，未影响已加载课程的操作。可稍后重新加载。
        <el-button text @click="load">重新加载</el-button>
      </el-alert>

      <div v-if="!courses.length" class="page-state">
        <div>
          <div class="state-icon"><el-icon><FolderAdd /></el-icon></div>
          <h3>还没有可运营的课程</h3>
          <p>创建课程后即可上传资料、建设题库并启动资源审核流程。</p>
          <el-button type="primary" @click="router.push('/teacher/courses')">创建第一门课程</el-button>
        </div>
      </div>

      <template v-else>
        <section class="overview-strip" aria-label="教学运营概览">
          <article>
            <span class="metric-mark"><el-icon><FolderOpened /></el-icon></span>
            <div><small>运营课程</small><strong>{{ courses.length }}</strong><p>{{ activeCourseCount }} 门已有教学内容</p></div>
          </article>
          <article>
            <span class="metric-mark"><el-icon><User /></el-icon></span>
            <div><small>课程学习人次</small><strong>{{ studentCount }}</strong><p>来自全部课程学习画像</p></div>
          </article>
          <article>
            <span class="metric-mark warning"><el-icon><Checked /></el-icon></span>
            <div><small>待审核资源</small><strong>{{ pending }}</strong><p>已发布 {{ published }} 项资源</p></div>
          </article>
          <article>
            <span class="metric-mark"><el-icon><EditPen /></el-icon></span>
            <div><small>题库规模</small><strong>{{ qCount }}</strong><p>{{ questionReadyCount }} 门课程已有题目</p></div>
          </article>
        </section>

        <section class="operation-panel">
          <header class="section-head">
            <div>
              <h2>课程运营</h2>
              <p>审核、题库、学习人次与风险均来自当前课程数据。</p>
            </div>
            <el-button text @click="router.push('/teacher/courses')">查看全部课程 <el-icon><ArrowRight /></el-icon></el-button>
          </header>

          <div class="course-table-head" aria-hidden="true">
            <span>课程</span><span>学习人次</span><span>内容状态</span><span>班级风险</span><span>操作</span>
          </div>
          <div class="course-operation-list">
            <article
              v-for="row in courseRows"
              :key="row.course.id"
              class="course-operation-row"
              :class="{ selected: Number(row.course.id) === selectedCourseId }"
              @click="selectCourse(Number(row.course.id))"
            >
              <div class="course-identity">
                <span class="course-mark"><el-icon><Reading /></el-icon></span>
                <div>
                  <small>{{ row.course.code || `COURSE-${row.course.id}` }}</small>
                  <b>{{ row.course.name }}</b>
                  <p>{{ row.course.description || '暂无课程简介' }}</p>
                </div>
              </div>
              <div class="course-students">
                <strong>{{ row.studentCount }}</strong>
                <small>人次</small>
              </div>
              <div class="content-status">
                <div><b>{{ row.published }}/{{ row.resources }}</b><span>已发布 / 总资源</span></div>
                <div class="status-line">
                  <span :class="['status-pill', row.pending ? 'warning' : 'ready']">{{ row.pending ? `${row.pending} 项待审` : '审核已清' }}</span>
                  <span>{{ row.questions }} 道题</span>
                </div>
              </div>
              <div class="risk-status">
                <template v-if="row.weakPoints.length">
                  <span class="risk-dot"></span>
                  <div><b>{{ row.weakPoints[0].name }}</b><small>{{ row.weakPoints[0].count }} 人需关注</small></div>
                </template>
                <template v-else>
                  <span class="risk-dot stable"></span>
                  <div><b>暂无集中风险</b><small>等待更多学习数据</small></div>
                </template>
              </div>
              <div class="row-actions" @click.stop>
                <el-button size="small" @click="router.push(`/teacher/dashboard/${row.course.id}`)">看板</el-button>
                <el-button size="small" type="primary" plain @click="router.push(`/teacher/review/${row.course.id}`)">审核</el-button>
              </div>
            </article>
          </div>
        </section>

        <div class="teacher-detail-grid">
          <section class="detail-panel queue-panel">
            <header class="section-head compact">
              <div><h2>待处理队列</h2><p>按审核、风险和内容准备度排序。</p></div>
              <span class="section-count">{{ priorityItems.length }}</span>
            </header>
            <div v-if="priorityItems.length" class="priority-list">
              <button v-for="item in priorityItems" :key="item.key" type="button" @click="router.push(item.to)">
                <span :class="['queue-signal', item.tone]"><el-icon><component :is="item.icon" /></el-icon></span>
                <span><b>{{ item.title }}</b><small>{{ item.description }}</small></span>
                <el-icon class="queue-arrow"><ArrowRight /></el-icon>
              </button>
            </div>
            <div v-else class="inline-empty">
              <el-icon><CircleCheck /></el-icon><b>当前没有待处理事项</b><span>审核队列与班级风险均处于稳定状态。</span>
            </div>
          </section>

          <section class="detail-panel risk-panel">
            <header class="section-head compact">
              <div><h2>班级风险</h2><p>聚合各课程人数最多的薄弱知识点。</p></div>
              <el-icon class="section-icon"><DataAnalysis /></el-icon>
            </header>
            <div v-if="topRisks.length" class="risk-list">
              <div v-for="risk in topRisks" :key="risk.key" class="risk-row">
                <div class="risk-copy">
                  <span><b>{{ risk.name }}</b><small>{{ risk.courseName }}</small></span>
                  <strong>{{ risk.count }} 人</strong>
                </div>
                <div class="risk-track"><i :style="{ width: `${risk.ratio}%` }"></i></div>
              </div>
            </div>
            <div v-else class="inline-empty">
              <el-icon><DataAnalysis /></el-icon><b>暂无薄弱点数据</b><span>学生完成前测后，这里会呈现班级集中风险。</span>
            </div>
          </section>

          <section class="detail-panel quick-panel">
            <header class="section-head compact">
              <div><h2>快捷动作</h2><p>{{ selectedCourse?.name || '请选择课程' }}</p></div>
            </header>
            <div class="quick-list">
              <button v-for="action in quickActions" :key="action.key" type="button" @click="router.push(action.to)">
                <el-icon><component :is="action.icon" /></el-icon>
                <span><b>{{ action.label }}</b><small>{{ action.description }}</small></span>
                <el-icon class="quick-arrow"><ArrowRight /></el-icon>
              </button>
            </div>
          </section>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { course, question, resource, review, stats } from '@/api'

interface WeakPoint {
  name: string
  count: number
}

interface CourseOperationRow {
  course: any
  pending: number
  published: number
  resources: number
  questions: number
  studentCount: number
  weakPoints: WeakPoint[]
}

const router = useRouter()
const courses = ref<any[]>([])
const courseRows = ref<CourseOperationRow[]>([])
const selectedCourseId = ref(Number(localStorage.getItem('xunkeflow_cid') || 0))
const loading = ref(true)
const error = ref('')
const partialFailures = ref(0)

const pending = computed(() => courseRows.value.reduce((sum, row) => sum + row.pending, 0))
const published = computed(() => courseRows.value.reduce((sum, row) => sum + row.published, 0))
const qCount = computed(() => courseRows.value.reduce((sum, row) => sum + row.questions, 0))
const studentCount = computed(() => courseRows.value.reduce((sum, row) => sum + row.studentCount, 0))
const activeCourseCount = computed(() => courseRows.value.filter((row) => row.resources || row.questions).length)
const questionReadyCount = computed(() => courseRows.value.filter((row) => row.questions > 0).length)
const selectedCourse = computed(() => courses.value.find((item) => Number(item.id) === selectedCourseId.value) || courses.value[0])

const priorityItems = computed(() => {
  const items: Array<{ key: string; title: string; description: string; to: string; tone: string; icon: string; priority: number }> = []
  courseRows.value.forEach((row) => {
    if (row.pending) {
      items.push({
        key: `review-${row.course.id}`,
        title: `${row.course.name}有资源待审核`,
        description: `${row.pending} 项内容等待教师确认后发布`,
        to: `/teacher/review/${row.course.id}`,
        tone: 'warning',
        icon: 'Checked',
        priority: 30 + row.pending
      })
    }
    if (row.weakPoints.length) {
      items.push({
        key: `risk-${row.course.id}`,
        title: `${row.course.name}出现集中薄弱点`,
        description: `${row.weakPoints[0].name} · ${row.weakPoints[0].count} 人需关注`,
        to: `/teacher/dashboard/${row.course.id}`,
        tone: 'risk',
        icon: 'DataAnalysis',
        priority: 20 + row.weakPoints[0].count
      })
    }
    if (!row.questions) {
      items.push({
        key: `question-${row.course.id}`,
        title: `${row.course.name}尚未建设题库`,
        description: '补充题目后可开展前测、练习和后测',
        to: `/teacher/questions/${row.course.id}`,
        tone: 'info',
        icon: 'EditPen',
        priority: 10
      })
    }
  })
  return items.sort((a, b) => b.priority - a.priority).slice(0, 5)
})

const topRisks = computed(() => courseRows.value
  .flatMap((row) => row.weakPoints.slice(0, 2).map((point) => ({
    key: `${row.course.id}-${point.name}`,
    name: point.name,
    courseName: row.course.name,
    count: point.count,
    ratio: row.studentCount ? Math.min(100, Math.round(point.count / row.studentCount * 100)) : 0
  })))
  .sort((a, b) => b.count - a.count)
  .slice(0, 5))

const quickActions = computed(() => {
  const id = Number(selectedCourse.value?.id || selectedCourseId.value)
  return [
    { key: 'upload', label: '上传资料', description: '更新课程依据', icon: 'Upload', to: `/teacher/upload/${id}` },
    { key: 'knowledge', label: '知识点管理', description: '整理课程结构', icon: 'Collection', to: `/teacher/knowledge/${id}` },
    { key: 'graph', label: '知识图谱', description: '检查知识关系', icon: 'Share', to: `/teacher/graph/${id}` },
    { key: 'questions', label: '题库管理', description: '维护测评题目', icon: 'EditPen', to: `/teacher/questions/${id}` },
    { key: 'generate', label: '资源生成', description: '创建教学内容', icon: 'MagicStick', to: `/teacher/generate/${id}` },
    { key: 'dashboard', label: '班级看板', description: '查看学情变化', icon: 'DataAnalysis', to: `/teacher/dashboard/${id}` }
  ]
})

function selectCourse(value: number | string) {
  selectedCourseId.value = Number(value)
  if (selectedCourseId.value) localStorage.setItem('xunkeflow_cid', String(selectedCourseId.value))
  else localStorage.removeItem('xunkeflow_cid')
}

function goSelected(view: string) {
  if (!selectedCourseId.value) return
  router.push(`/teacher/${view}/${selectedCourseId.value}`)
}

function resultValue<T>(result: PromiseSettledResult<T>, fallback: T): T {
  if (result.status === 'fulfilled') return result.value
  partialFailures.value += 1
  return fallback
}

async function load() {
  loading.value = true
  error.value = ''
  partialFailures.value = 0
  try {
    const list = await course.list()
    courses.value = Array.isArray(list) ? list : []
    const validIds = courses.value.map((item) => Number(item.id))
    if (!validIds.includes(selectedCourseId.value)) selectCourse(validIds[0] || 0)

    courseRows.value = await Promise.all(courses.value.map(async (item) => {
      const [pendingResult, questionResult, resourceResult, statsResult] = await Promise.allSettled([
        review.pending(item.id),
        question.list({ course_id: item.id }),
        resource.list({ course_id: item.id }),
        stats.teacher(item.id)
      ])
      const pendingRows: any[] = resultValue(pendingResult as PromiseSettledResult<any[]>, [])
      const questions: any[] = resultValue(questionResult as PromiseSettledResult<any[]>, [])
      const resources: any[] = resultValue(resourceResult as PromiseSettledResult<any[]>, [])
      const dashboard: any = resultValue(statsResult as PromiseSettledResult<any>, {})
      return {
        course: item,
        pending: pendingRows.length,
        published: resources.filter((entry) => entry.published || entry.review_status === 'published').length,
        resources: resources.length,
        questions: questions.length,
        studentCount: Number(dashboard.student_count || 0),
        weakPoints: Array.isArray(dashboard.weak_heatmap) ? dashboard.weak_heatmap : []
      }
    }))
  } catch (err: any) {
    courses.value = []
    courseRows.value = []
    error.value = err?.message || '请检查后端服务后重新加载。'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.teacher-home { --panel-border: #e2e7f0; }
.header-actions { display: flex; align-items: center; justify-content: flex-end; gap: 9px; flex-wrap: wrap; }
.course-selector { width: 250px; }
.partial-alert { margin-bottom: 16px; }
.partial-alert :deep(.el-alert__content) { line-height: 1.6; }

.loading-workspace { padding: 18px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; }
.skeleton-metrics, .skeleton-bottom { display: grid; gap: 12px; }
.skeleton-metrics { grid-template-columns: repeat(4, 1fr); }
.skeleton-metrics .el-skeleton__item { height: 112px; }
.skeleton-table { height: 330px; margin: 16px 0; }
.skeleton-bottom { grid-template-columns: 1fr 1fr .82fr; }
.skeleton-bottom .el-skeleton__item { height: 300px; }

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
.metric-mark.warning { color: var(--warning); background: var(--warning-bg); }
.overview-strip small, .overview-strip strong, .overview-strip p { display: block; }
.overview-strip small { color: var(--text-secondary); font-size: 12px; font-weight: 650; }
.overview-strip strong { margin-top: 2px; font-size: 27px; line-height: 1.15; letter-spacing: -.035em; }
.overview-strip p { overflow: hidden; margin-top: 4px; color: var(--text-muted); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }

.operation-panel, .detail-panel { border: 1px solid var(--panel-border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.operation-panel { overflow: hidden; }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 20px 22px; border-bottom: 1px solid var(--border-light); }
.section-head h2 { font-size: 16px; line-height: 1.35; }
.section-head p { margin-top: 3px; color: var(--text-secondary); font-size: 12px; }
.section-head.compact { padding: 18px 20px; }
.section-count { min-width: 28px; height: 28px; display: grid; place-items: center; border-radius: 999px; color: var(--primary); background: var(--primary-bg); font-size: 12px; font-weight: 750; }
.section-icon { color: var(--primary); font-size: 20px; }

.course-table-head, .course-operation-row { display: grid; grid-template-columns: minmax(260px, 1.5fr) 90px minmax(190px, .9fr) minmax(170px, .8fr) 130px; gap: 16px; align-items: center; }
.course-table-head { padding: 9px 22px; color: var(--text-muted); background: #f8f9fc; font-size: 11px; font-weight: 700; }
.course-operation-row { position: relative; min-height: 94px; padding: 15px 22px; border-top: 1px solid var(--border-light); cursor: pointer; transition: background .18s ease, box-shadow .18s ease; }
.course-operation-row:first-child { border-top: 0; }
.course-operation-row:hover { background: #fafbff; }
.course-operation-row.selected { background: #fbfbff; box-shadow: inset 3px 0 var(--primary); }
.course-identity { min-width: 0; display: grid; grid-template-columns: 42px minmax(0, 1fr); gap: 12px; align-items: center; }
.course-mark { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 11px; color: var(--primary); background: var(--primary-bg); font-size: 18px; }
.course-identity small, .course-identity b, .course-identity p { display: block; }
.course-identity small { color: var(--text-muted); font-size: 10px; font-weight: 750; letter-spacing: .06em; }
.course-identity b { overflow: hidden; margin-top: 1px; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.course-identity p { overflow: hidden; margin-top: 2px; color: var(--text-secondary); font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.course-students strong, .course-students small { display: block; }
.course-students strong { font-size: 20px; line-height: 1.2; }
.course-students small { color: var(--text-muted); font-size: 11px; }
.content-status > div:first-child { display: flex; align-items: baseline; gap: 7px; }
.content-status b { font-size: 15px; }
.content-status span { color: var(--text-secondary); font-size: 11px; }
.status-line { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
.status-pill { padding: 2px 7px; border-radius: 999px; font-size: 10px !important; font-weight: 700; }
.status-pill.warning { color: var(--warning); background: var(--warning-bg); }
.status-pill.ready { color: var(--success); background: var(--success-bg); }
.risk-status { min-width: 0; display: flex; align-items: center; gap: 9px; }
.risk-dot { width: 8px; height: 8px; flex: 0 0 auto; border-radius: 50%; background: var(--warning); box-shadow: 0 0 0 4px var(--warning-bg); }
.risk-dot.stable { background: var(--success); box-shadow: 0 0 0 4px var(--success-bg); }
.risk-status b, .risk-status small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.risk-status b { font-size: 12px; }
.risk-status small { color: var(--text-muted); font-size: 10px; }
.row-actions { display: flex; justify-content: flex-end; gap: 7px; }

.teacher-detail-grid { display: grid; grid-template-columns: 1fr 1fr .82fr; gap: 16px; margin-top: 16px; }
.detail-panel { min-width: 0; overflow: hidden; }
.priority-list, .quick-list { display: grid; }
.priority-list button, .quick-list button { width: 100%; border: 0; border-top: 1px solid var(--border-light); background: #fff; color: var(--text); text-align: left; cursor: pointer; transition: background .18s ease; }
.priority-list button:first-child, .quick-list button:first-child { border-top: 0; }
.priority-list button:hover, .quick-list button:hover { background: #f8f9fd; }
.priority-list button { display: grid; grid-template-columns: 34px minmax(0, 1fr) 16px; gap: 11px; align-items: center; padding: 12px 18px; }
.queue-signal { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 9px; color: var(--primary); background: var(--primary-bg); }
.queue-signal.warning { color: var(--warning); background: var(--warning-bg); }
.queue-signal.risk { color: #a94d60; background: var(--danger-bg); }
.priority-list b, .priority-list small, .quick-list b, .quick-list small { display: block; }
.priority-list b { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.priority-list small { margin-top: 2px; color: var(--text-secondary); font-size: 10px; line-height: 1.5; }
.queue-arrow, .quick-arrow { color: var(--text-muted); }

.risk-list { display: grid; gap: 15px; padding: 18px 20px 22px; }
.risk-copy { display: flex; align-items: end; justify-content: space-between; gap: 12px; }
.risk-copy b, .risk-copy small { display: block; }
.risk-copy b { font-size: 12px; }
.risk-copy small { overflow: hidden; max-width: 250px; margin-top: 2px; color: var(--text-muted); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.risk-copy strong { color: var(--warning); font-size: 12px; }
.risk-track { height: 5px; overflow: hidden; margin-top: 7px; border-radius: 999px; background: #edf0f5; }
.risk-track i { display: block; min-width: 4px; height: 100%; border-radius: inherit; background: #c8832e; transition: width .35s ease; }

.quick-list button { display: grid; grid-template-columns: 30px minmax(0, 1fr) 16px; gap: 9px; align-items: center; padding: 11px 17px; }
.quick-list button > .el-icon:first-child { width: 29px; height: 29px; border-radius: 8px; color: var(--primary); background: var(--primary-bg); }
.quick-list b { font-size: 12px; }
.quick-list small { color: var(--text-muted); font-size: 10px; }
.inline-empty { min-height: 224px; display: flex; align-items: center; justify-content: center; flex-direction: column; padding: 24px; color: var(--text-muted); text-align: center; }
.inline-empty .el-icon { margin-bottom: 9px; color: var(--primary-light); font-size: 28px; }
.inline-empty b { color: var(--text); font-size: 13px; }
.inline-empty span { max-width: 270px; margin-top: 3px; font-size: 11px; }

@media (max-width: 1240px) {
  .teacher-detail-grid { grid-template-columns: 1fr 1fr; }
  .quick-panel { grid-column: 1 / -1; }
  .quick-list { grid-template-columns: repeat(3, 1fr); }
  .quick-list button:nth-child(-n + 3) { border-top: 0; }
  .quick-list button + button { border-left: 1px solid var(--border-light); }
  .course-table-head, .course-operation-row { grid-template-columns: minmax(230px, 1.4fr) 76px minmax(170px, .9fr) minmax(150px, .8fr) 118px; gap: 12px; }
}
@media (max-width: 980px) {
  .overview-strip { grid-template-columns: repeat(2, 1fr); }
  .overview-strip article:nth-child(3) { border-left: 0; border-top: 1px solid var(--border-light); }
  .overview-strip article:nth-child(4) { border-top: 1px solid var(--border-light); }
  .course-table-head { display: none; }
  .course-operation-row { grid-template-columns: minmax(0, 1fr) auto; gap: 12px 18px; }
  .course-students { text-align: right; }
  .content-status, .risk-status { padding-top: 10px; border-top: 1px solid var(--border-light); }
  .row-actions { align-self: stretch; align-items: center; padding-top: 10px; border-top: 1px solid var(--border-light); }
}
@media (max-width: 760px) {
  .page-header { align-items: stretch; }
  .header-actions { justify-content: stretch; }
  .course-selector { width: 100%; }
  .header-actions .el-button { flex: 1; margin-left: 0; }
  .skeleton-metrics, .skeleton-bottom, .overview-strip, .teacher-detail-grid { grid-template-columns: 1fr; }
  .overview-strip article + article { border-left: 0; border-top: 1px solid var(--border-light); }
  .course-operation-row { padding: 15px; }
  .content-status, .risk-status, .row-actions { grid-column: 1 / -1; }
  .row-actions { justify-content: flex-start; }
  .quick-panel { grid-column: auto; }
  .quick-list { grid-template-columns: 1fr; }
  .quick-list button, .quick-list button:nth-child(-n + 3) { border-top: 1px solid var(--border-light); border-left: 0; }
  .quick-list button:first-child { border-top: 0; }
}
</style>
