<template>
  <div class="page command-page">
    <div class="page-header">
      <div>
        <div class="page-title">智能协作流程</div>
        <div class="page-desc">查看课程解析、学习诊断、内容生成、质量校验和教师预审的实际执行状态。</div>
      </div>
      <div class="toolbar-actions">
        <el-button :loading="loading" @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
        <el-button type="primary" :loading="running" @click="startPipeline"><el-icon><VideoPlay /></el-icon>启动完整任务</el-button>
      </div>
    </div>

    <div v-if="error" class="page-state error compact-state">
      <div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>流程数据加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div>
    </div>

    <template v-else>
      <el-alert
        v-if="IS_SHOWCASE || String(latestRun?.trace_id || '').startsWith('trace_seed_demo')"
        class="demo-evidence-alert"
        type="warning"
        :closable="false"
        show-icon
        :title="IS_SHOWCASE ? '当前为前端展示，展示原程序的预置任务记录；运行完整服务后可启动新的协作任务。' : '当前展示的是预置离线演示任务记录；点击“启动完整任务”后会生成新的真实运行日志与任务编号。'"
      />
      <section class="run-overview">
        <div class="overview-main">
          <span class="overview-kicker">当前任务</span>
          <h1>{{ data.course?.name || '请选择课程后启动任务' }}</h1>
          <div class="trace-line">
            <span>任务编号</span><code>{{ data.hero?.active_trace || '尚未运行' }}</code>
            <span>状态</span><el-tag :type="statusType(latestRun?.status)" effect="plain">{{ statusText(latestRun?.status || 'waiting') }}</el-tag>
          </div>
        </div>
        <div class="progress-block">
          <div><span>总体进度</span><strong>{{ totalProgress }}%</strong></div>
          <el-progress :percentage="totalProgress" :stroke-width="10" :show-text="false" />
          <small>{{ completedCount }} / {{ agentNodes.length || 10 }} 个环节已完成</small>
        </div>
        <div class="overview-metrics">
          <div><span>平均质量</span><b>{{ formatScore(data.kpis?.avg_quality) }}</b></div>
          <div><span>课程引用</span><b>{{ data.kpis?.rag_evidence || 0 }}</b></div>
          <div><span>学习提升</span><b :class="Number(data.kpis?.improvement || 0) >= 0 ? 'text-success' : 'text-danger'">{{ signed(data.kpis?.improvement || 0) }}</b></div>
        </div>
      </section>

      <div v-if="loading && !agentNodes.length" class="card"><el-skeleton :rows="8" animated /></div>

      <section v-else class="workspace-grid">
        <div class="pipeline-surface">
          <header class="section-head">
            <div><h2>10 个协作环节</h2><p>点击任一节点查看输入、输出、引用、执行记录与异常信息。</p></div>
            <span class="status-legend"><i class="pending"></i>待执行 <i class="running"></i>执行中 <i class="success"></i>成功 <i class="warning"></i>需关注 <i class="failed"></i>失败</span>
          </header>

          <div class="agent-flow">
            <button
              v-for="node in agentNodes"
              :key="node.agent"
              type="button"
              class="agent-node"
              :class="normalizeStatus(node.status)"
              @click="openNode(node)"
            >
              <span class="node-index">{{ node.step }}</span>
              <span class="node-state"><i></i>{{ statusText(node.status) }}</span>
              <b>{{ node.label }}</b>
              <small>{{ node.desc }}</small>
              <p>{{ node.summary || '等待上游任务' }}</p>
              <footer><span>{{ node.duration_ms ? formatDuration(node.duration_ms) : node.output?.demo_data ? '预置记录' : '未执行' }}</span><strong v-if="node.score != null">{{ Math.round(node.score) }} 分</strong></footer>
            </button>
          </div>
        </div>

        <aside class="resource-surface">
          <header class="section-head compact"><div><h2>本次任务产物</h2><p>已生成并进入审核或发布流程的资源。</p></div><span>{{ resources.length }} 项</span></header>
          <div v-if="resources.length" class="resource-list">
            <article v-for="item in resources" :key="item.id" class="resource-item">
              <span class="resource-mark"><el-icon><component :is="resourceIcon(item.rtype)" /></el-icon></span>
              <div><b>{{ item.title }}</b><small>{{ resourceType(item.rtype) }} · {{ citationCount(item.citations) }} 条引用</small></div>
              <div class="resource-status"><strong>{{ Math.round(item.quality_score || 0) }}</strong><el-tag size="small" :type="reviewType(item.review_status)" effect="plain">{{ reviewText(item.review_status) }}</el-tag></div>
            </article>
          </div>
          <div v-else class="resource-empty"><el-icon><FolderOpened /></el-icon><b>暂无任务产物</b><span>启动完整任务后，生成结果会集中显示在这里。</span></div>
        </aside>
      </section>

      <section class="quality-section">
        <header class="section-head compact"><div><h2>质量与闭环指标</h2><p>指标来自当前课程资源、引用和前后测结果。</p></div></header>
        <div class="quality-grid">
          <article v-for="metric in qualityMetrics" :key="metric.name" :class="metric.status">
            <span>{{ metric.name }}</span>
            <strong>{{ metric.value }}<small>{{ metric.unit }}</small></strong>
            <p>{{ metric.desc }}</p>
          </article>
        </div>
      </section>

      <section class="run-history">
        <header class="section-head compact"><div><h2>最近任务</h2><p>每次执行均保留任务编号、状态、进度和耗时。</p></div></header>
        <el-table :data="data.recent_runs || []" size="small" @row-click="openRun" highlight-current-row>
          <el-table-column prop="trace_id" label="任务编号" min-width="180"><template #default="{ row }"><code>{{ row.trace_id }}</code></template></el-table-column>
          <el-table-column label="任务类型" width="130"><template #default="{ row }">{{ flowLabel(row.workflow) }}</template></el-table-column>
          <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag size="small" :type="statusType(row.status)" effect="plain">{{ statusText(row.status) }}</el-tag></template></el-table-column>
          <el-table-column label="进度" width="180"><template #default="{ row }"><el-progress :percentage="Math.round((row.progress || 0) * 100)" :stroke-width="7" /></template></el-table-column>
          <el-table-column label="耗时" width="110"><template #default="{ row }">{{ row.duration_ms ? formatDuration(row.duration_ms) : '—' }}</template></el-table-column>
          <el-table-column label="操作" width="100"><template #default="{ row }"><el-button v-if="row.status === 'failed' && row.workflow === 'full_pipeline'" size="small" type="primary" plain :loading="retryingId === row.id" @click.stop="retryRun(row)">重试</el-button><span v-else class="muted">—</span></template></el-table-column>
          <template #empty><el-empty description="暂无任务记录" /></template>
        </el-table>
      </section>
    </template>

    <el-drawer v-model="drawerOpen" size="min(680px, 92vw)" :title="drawerTitle">
      <div v-if="selectedNode" class="node-inspector">
        <div class="inspector-summary">
          <span :class="['inspector-mark', normalizeStatus(selectedNode.status)]">{{ selectedNode.step }}</span>
          <div><h2>{{ selectedNode.label }}</h2><p>{{ selectedNode.desc }}</p></div>
          <el-tag :type="statusType(selectedNode.status)">{{ statusText(selectedNode.status) }}</el-tag>
        </div>

        <div class="inspector-grid">
          <div><span>执行耗时</span><b>{{ selectedNode.duration_ms ? formatDuration(selectedNode.duration_ms) : selectedNode.output?.demo_data ? '预置记录' : '未执行' }}</b></div>
          <div><span>使用服务</span><b>{{ selectedNode.model || '未记录' }}</b></div>
          <div><span>引用资料</span><b>{{ selectedNode.citationCount || 0 }} 条</b></div>
          <div><span>质量评分</span><b>{{ selectedNode.quality == null ? '—' : `${Math.round(selectedNode.quality)} 分` }}</b></div>
          <div><span>重试次数</span><b>{{ selectedNode.retries || 0 }}</b></div>
          <div><span>任务编号</span><b class="mono">{{ data.hero?.active_trace || '—' }}</b></div>
        </div>

        <section><h3>输入摘要</h3><pre>{{ pretty(selectedNode.input, selectedNode.agent) }}</pre></section>
        <section><h3>输出摘要</h3><pre>{{ pretty(selectedNode.output, selectedNode.agent) }}</pre></section>
        <section v-if="selectedNode.citations?.length"><h3>引用来源</h3><div class="drawer-citations"><article v-for="(item, index) in selectedNode.citations" :key="index"><b>[{{ index + 1 }}] {{ item.source }}</b><span>第 {{ item.page || 1 }} 页 · {{ item.score || 0 }}%</span><p>{{ cleanSnippet(item.snippet) }}</p></article></div></section>
        <section><h3>执行日志</h3><div class="execution-log"><span>{{ selectedNode.created_at ? formatTime(selectedNode.created_at) : '本次任务' }}</span><b>{{ selectedNode.label }} · {{ statusText(selectedNode.status) }}</b><p>{{ selectedNode.summary || '暂无执行摘要' }}</p></div></section>
        <el-alert v-if="selectedNode.error" type="error" :closable="false" show-icon><template #title>执行异常</template>{{ selectedNode.error }}</el-alert>
      </div>

      <div v-else-if="selectedRun" class="run-inspector">
        <div class="inspector-grid run-kpis">
          <div><span>任务状态</span><b>{{ statusText(selectedRun.status) }}</b></div>
          <div><span>任务类型</span><b>{{ flowLabel(selectedRun.workflow) }}</b></div>
          <div><span>总体进度</span><b>{{ Math.round((selectedRun.progress || 0) * 100) }}%</b></div>
          <div><span>总耗时</span><b>{{ selectedRun.duration_ms ? formatDuration(selectedRun.duration_ms) : '—' }}</b></div>
        </div>
        <div class="run-log-list"><article v-for="log in selectedRun.logs || []" :key="log.id"><span>{{ log.step }}</span><div><b>{{ agentLabel(log.agent) }}</b><p>{{ humanSummary(log.agent, log.output_summary, compact(log.output_summary)) }}</p><small v-if="log.error" class="text-danger">{{ log.error }}</small></div><em>{{ formatDuration(log.duration_ms || 0) }}</em></article></div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { agent, resource, system } from '@/api'
import { useUserStore } from '@/stores/user'
import { IS_SHOWCASE } from '@/config/runtime'

const route = useRoute()
const store = useUserStore()
const loading = ref(false)
const running = ref(false)
const retryingId = ref(0)
const error = ref('')
const drawerOpen = ref(false)
const selectedNode = ref<any>(null)
const selectedRun = ref<any>(null)
const data = ref<any>({})
const engineInfo = ref<any>({})
const latestDetail = ref<any>(null)
const resourceRows = ref<any[]>([])
let pollTimer: number | null = null
let activeTraceId = ''

const activeCourse = computed(() => Number(route.params.cid || localStorage.getItem('xunkeflow_cid') || data.value.course?.id || 0))
// The recent-runs table is chronological and may start with a one-step upload
// parse. The ten-node command surface instead follows the backend-selected
// complete pipeline so progress, logs and the active trace always agree.
const latestRun = computed(() => data.value.active_run || data.value.recent_runs?.[0] || null)
const resources = computed(() => {
  if (store.role !== 'student') return data.value.resources || []
  return resourceRows.value
    .filter((item) => (!item.is_personalized || Number(item.student_id) === Number(store.user?.id)) && (item.published || ['approved', 'published'].includes(item.review_status)))
    .slice(0, 10)
})
const agentNodes = computed(() => {
  const logs = latestDetail.value?.logs || []
  const calls = (data.value.model_calls || []).filter((call: any) => !latestRun.value?.trace_id || call.trace_id === latestRun.value.trace_id)
  return (data.value.agent_nodes || []).map((node: any) => {
    const log = logs.find((item: any) => item.agent === node.agent) || {}
    const call = findModelCall(node.agent, calls)
    const output = log.output_summary || {}
    const declaredCitationCount = Number(node.citation_count ?? log.citation_count ?? 0)
    const evidence = evidenceForAgent(
      node.agent,
      data.value.evidence || [],
      output,
      log.input_summary || {},
      declaredCitationCount
    )
    return {
      ...node,
      desc: agentDescription(node.agent, node.desc),
      summary: log.id ? humanSummary(node.agent, output, node.summary) : (node.summary || '等待上游任务'),
      input: log.input_summary || {},
      output,
      error: log.error || '',
      retries: output.retry_count ?? output.retries ?? log.retry_count ?? 0,
      model: store.role === 'admin'
        ? (log.model_name || call?.model || engineInfo.value.engine_name || '')
        : '课程智能服务',
      created_at: log.created_at || '',
      citations: evidence,
      citationCount: declaredCitationCount || evidence.length,
      quality: node.score ?? output.quality ?? output.avg_score ?? null
    }
  })
})
const completedCount = computed(() => agentNodes.value.filter((node: any) => ['success', 'warning', 'failed', 'risk', 'pending_review'].includes(normalizeStatus(node.status))).length)
const totalProgress = computed(() => {
  const backendProgress = Number(latestRun.value?.progress || 0)
  if (backendProgress > 0) return Math.min(100, Math.round(backendProgress * 100))
  return agentNodes.value.length ? Math.round(completedCount.value / agentNodes.value.length * 100) : 0
})
const qualityMetrics = computed(() => {
  const gates = (data.value.quality_gates || []).map((gate: any) => ({ ...gate, value: gate.value ?? 0 }))
  if (gates.length) return gates
  return [
    { name: '内容质量', value: formatScore(data.value.kpis?.avg_quality), unit: '分', status: 'pending', desc: '等待资源生成后计算' },
    { name: '课程引用', value: data.value.kpis?.rag_evidence || 0, unit: '条', status: 'pending', desc: '等待检索课程资料' },
    { name: '教师审核', value: 0, unit: '项', status: 'pending', desc: '等待内容进入审核队列' }
  ]
})
const drawerTitle = computed(() => selectedNode.value ? `环节详情 · ${selectedNode.value.label}` : selectedRun.value ? `任务详情 · ${selectedRun.value.trace_id}` : '详情')

const normalizeStatus = (status: string) => ({ waiting: 'pending', pending: 'pending', running: 'running', success: 'success', pending_review: 'warning', risk: 'warning', warning: 'warning', failed: 'failed' }[status] || 'pending')
const statusText = (status: string) => ({ waiting: '待执行', pending: '待执行', running: '执行中', success: '成功', pending_review: '待审核', risk: '需关注', warning: '需关注', failed: '失败' }[status] || status || '待执行')
const statusType = (status: string) => ({ running: 'primary', success: 'success', pending_review: 'warning', risk: 'warning', warning: 'warning', failed: 'danger', waiting: 'info', pending: 'info' }[status] as any)
const flowLabel = (workflow: string) => ({ full_pipeline: '完整协作流程', parse: '资料解析', generate: '资源生成', diagnose: '学习诊断' }[workflow] || workflow || '任务')
const signed = (value: number) => `${Number(value) >= 0 ? '+' : ''}${Number(value || 0).toFixed(1)}`
const formatScore = (value: any) => Number.isFinite(Number(value)) ? Math.round(Number(value)) : 0
const formatDuration = (ms: number) => ms >= 1000 ? `${(ms / 1000).toFixed(1)} 秒` : `${Math.round(ms)} 毫秒`
const formatTime = (value: string) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
const reviewText = (status: string) => ({ pending: '待审核', approved: '已通过', published: '已发布', risk: '需关注', rejected: '已退回' }[status] || status)
const reviewType = (status: string) => ({ pending: 'info', approved: 'success', published: 'success', risk: 'warning', rejected: 'danger' }[status] as any)
const resourceType = (type: string) => ({ lecture: '个性化讲义', mindmap: '思维导图', exercise: '分层练习', experiment: '实验任务', reading: '拓展阅读', ppt: '课件大纲', video: '视频脚本', wrong_review: '错题复盘', remedial: '补救资源' }[type] || type)
const resourceIcon = (type: string) => ({ lecture: 'Document', mindmap: 'Share', exercise: 'EditPen', experiment: 'Operation', reading: 'Reading', ppt: 'Present', video: 'VideoCamera', wrong_review: 'Warning', remedial: 'FirstAidKit' }[type] || 'Document')
const citationCount = (value: any) => Array.isArray(value) ? value.length : Number(value || 0)
const cleanSnippet = (value: string) => String(value || '')
  .replace(/#{1,6}\s*/g, '')
  .replace(/```[\s\S]*?```/g, ' ')
  .replace(/[>*_`|]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim()
  .slice(0, 220)

function agentLabel(agentName: string) {
  return ({ CourseParserAgent: '课程解析', KnowledgeGraphAgent: '知识图谱', DiagnosisAgent: '学习诊断', PlannerAgent: '路径规划', LectureAgent: '讲义生成', MindMapAgent: '思维导图', ExerciseAgent: '练习生成', MultimodalResourceAgent: '多类型资源', QualityCheckAgent: '质量校验', TeacherReviewAgent: '教师预审' } as Record<string, string>)[agentName] || agentName
}

function agentDescription(agentName: string, fallback: string) {
  return ({
    CourseParserAgent: '课程资料结构化与检索准备',
    KnowledgeGraphAgent: '建立先修、关联与易混关系',
    DiagnosisAgent: '识别学习基础与待强化内容',
    PlannerAgent: '生成分阶段学习顺序',
    LectureAgent: '基于课程证据分层讲解',
    MindMapAgent: '整理课程知识结构',
    ExerciseAgent: '生成分层题目、答案与解析',
    MultimodalResourceAgent: '生成课件、微课与实践任务',
    QualityCheckAgent: '检查内容、引用、难度与答案',
    TeacherReviewAgent: '形成教师审核建议与风险提示'
  } as Record<string, string>)[agentName] || fallback
}

function findModelCall(agentName: string, calls: any[]) {
  const keyword = ({ CourseParserAgent: 'parse', KnowledgeGraphAgent: 'graph', DiagnosisAgent: 'diagnos', PlannerAgent: 'plan', LectureAgent: 'lecture', MindMapAgent: 'mind', ExerciseAgent: 'exercise', MultimodalResourceAgent: 'multi', QualityCheckAgent: 'quality', TeacherReviewAgent: 'review' } as Record<string, string>)[agentName]
  return calls.find((call) => String(call.purpose || '').toLowerCase().includes(keyword || '')) || calls[0]
}

function evidenceForAgent(agentName: string, rows: any[], output: any, input: any, expectedCount: number) {
  const types: Record<string, string[]> = {
    LectureAgent: ['lecture'],
    MindMapAgent: ['mindmap'],
    ExerciseAgent: ['exercise'],
    MultimodalResourceAgent: ['ppt', 'video', 'experiment'],
    QualityCheckAgent: ['lecture', 'mindmap', 'exercise', 'ppt', 'video', 'experiment'],
    TeacherReviewAgent: ['lecture', 'mindmap', 'exercise', 'ppt', 'video', 'experiment']
  }
  const allowed = types[agentName]
  if (!allowed || expectedCount <= 0) return []

  const resourceIds = new Set(
    [output?.resource_id, ...(Array.isArray(output?.resource_ids) ? output.resource_ids : []), ...(Array.isArray(input?.resource_ids) ? input.resource_ids : [])]
      .map(Number)
      .filter((value) => Number.isInteger(value) && value > 0)
  )
  const typedRows = rows.filter((item) => allowed.includes(String(item.rtype || '')))
  const scopedRows = resourceIds.size
    ? typedRows.filter((item) => resourceIds.has(Number(item.resource_id)))
    : typedRows
  return scopedRows.slice(0, expectedCount)
}

function compact(value: any) {
  if (!value) return '暂无输出摘要'
  if (typeof value === 'string') return value.slice(0, 180)
  return Object.entries(value).slice(0, 5).map(([key, item]) => `${fieldLabel(key)}：${humanValue(item)}`).join('，')
}

function humanSummary(agentName: string, value: any, fallback = '') {
  const output = value && typeof value === 'object' ? value : {}
  const count = (item: any) => Array.isArray(item) ? item.length : Number(item || 0)
  const summaries: Record<string, string> = {
    CourseParserAgent: `已解析 ${output.pages || 0} 页课程资料，形成 ${output.chunks || 0} 个检索片段和 ${output.points || 0} 个知识点。`,
    KnowledgeGraphAgent: `已连接 ${output.nodes || 0} 个知识点，建立 ${output.relations || output.edges || 0} 条学习关系。`,
    DiagnosisAgent: `前测 ${output.pre_score ?? '—'} 分，识别 ${output.weak_count || 0} 个待强化知识点。`,
    PlannerAgent: `已安排 ${output.nodes || 0} 个学习节点，预计学习 ${formatStudyTime(output.total_minutes)}。`,
    LectureAgent: `个性化讲义已生成，质量 ${Math.round(Number(output.quality || 0))} 分，采用 ${output.citations || 0} 条课程依据。`,
    MindMapAgent: `知识导图包含 ${output.nodes || 0} 个节点和 ${output.relations || output.edges || 0} 条关系。`,
    ExerciseAgent: `已生成 ${output.questions || 0} 道分层练习，质量 ${Math.round(Number(output.quality || 0))} 分。`,
    MultimodalResourceAgent: `已形成 ${count(output.resource_ids) || count(output.rtypes)} 项课件、微课或实践资源。`,
    QualityCheckAgent: `已完成 ${output.checked || output.count || 0} 项质量校验，平均 ${Math.round(Number(output.avg_score || output.quality || 0))} 分。`,
    TeacherReviewAgent: `已为 ${output.reviewed || count(output.suggestions) || 0} 项资源形成教师预审建议。`
  }
  const summary = summaries[agentName]
  return summary && !summary.includes('undefined') ? summary : (fallback || '该环节已完成。')
}

function formatStudyTime(value: any) {
  const minutes = Number(value || 0)
  if (!minutes) return '待评估'
  if (minutes < 60) return `${minutes} 分钟`
  return `${(minutes / 60).toFixed(1)} 小时`
}

const fieldLabels: Record<string, string> = {
  parsed: '资料解析', pages: '资料页数', chunks: '检索片段', chapters: '课程章节', points: '知识点',
  nodes: '知识节点', relations: '关系数量', summary: '执行结论', pre_score: '前测成绩', base_level: '学习基础',
  weak_count: '待强化知识点', total_minutes: '预计学习时长', first_node: '首个学习主题', quality: '质量评分',
  citations: '课程引用', questions: '练习题', checked: '校验资源', avg_score: '平均质量', reviewed: '预审资源',
  retry_count: '重试次数', retries: '重试次数', warning: '提示', fallback_used: '降级保护', publishable: '是否建议发布',
  personalized: '个性化生成'
}
const hiddenFields = new Set(['course_id', 'file_id', 'student_id', 'kp_id', 'profile_id', 'path_id', 'resource_id', 'resource_ids', 'qids', 'agent_run_id', 'generation_mode', 'rtype', 'rtypes', 'details'])
function fieldLabel(key: string) { return fieldLabels[key] || key.replace(/_/g, ' ') }
function humanValue(value: any): string {
  if (value === true) return '已完成'
  if (value === false) return '否'
  if (Array.isArray(value)) return `${value.length} 项`
  if (value && typeof value === 'object') return `${Object.keys(value).length} 项`
  const labels: Record<string, string> = { basic: '基础阶段', intermediate: '进阶阶段', advanced: '高阶阶段', demo: '演示内容', real: '在线生成' }
  return labels[String(value)] || String(value ?? '—')
}
function pretty(value: any, agentName = '') {
  if (!value || (typeof value === 'object' && !Object.keys(value).length)) return '使用当前课程资料与学习数据。'
  if (typeof value === 'string') return value
  const lines = Object.entries(value)
    .filter(([key]) => !hiddenFields.has(key))
    .slice(0, 10)
    .map(([key, item]) => `${fieldLabel(key)}：${key === 'total_minutes' ? formatStudyTime(item) : humanValue(item)}`)
  return lines.length ? lines.join('\n') : `${agentLabel(agentName)}使用当前课程、资料引用与学习画像完成处理。`
}

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    ;[data.value, engineInfo.value, resourceRows.value] = await Promise.all([
      agent.commandCenter(activeCourse.value, silent),
      system.info(),
      store.role === 'student' ? resource.list({ course_id: activeCourse.value }) : Promise.resolve([])
    ])
    const latest = data.value.active_run || data.value.recent_runs?.[0]
    latestDetail.value = latest ? await agent.detail(latest.id) : null
    const active = latest && ['pending', 'running'].includes(latest.status)
    if (active) {
      running.value = true
      startPolling()
    } else {
      if (activeTraceId && latest?.trace_id === activeTraceId) {
        if (latest.status === 'success') ElMessage.success('完整课程任务已完成，生成结果已进入审核流程')
        if (latest.status === 'failed') ElMessage.error('完整课程任务执行失败，请查看失败节点')
        activeTraceId = ''
      }
      running.value = false
      stopPolling()
    }
  } catch (err: any) {
    if (!silent) error.value = err?.message || '请稍后重新加载协作流程。'
  } finally {
    if (!silent) loading.value = false
  }
}

async function startPipeline() {
  if (!activeCourse.value) return ElMessage.info('请先在课程中心选择课程')
  running.value = true
  error.value = ''
  try {
    const response = await agent.run({ course_id: activeCourse.value, workflow: 'full_pipeline' })
    if (response?.status === 'failed') throw new Error('完整任务执行失败，请打开失败节点查看原因。')
    activeTraceId = response?.trace_id || ''
    ElMessage.success('完整课程任务已提交，页面将实时更新执行进度')
    await load(true)
    startPolling()
  } catch (err: any) {
    if (!(IS_SHOWCASE && err?.status === 405)) error.value = err?.message || '任务执行失败，请重试。'
    stopPolling()
    running.value = false
  }
}

async function retryRun(row: any) {
  retryingId.value = row.id
  try {
    const response = await agent.retry(row.id)
    activeTraceId = response?.trace_id || ''
    ElMessage.success(response?.deduplicated ? '该任务已在执行，已切换到现有进度' : '失败任务已按新任务编号重新提交')
    await load(true)
    startPolling()
  } catch (err: any) {
    ElMessage.error(err?.message || '任务重试失败')
  } finally {
    retryingId.value = 0
  }
}

function startPolling() {
  if (pollTimer !== null) return
  pollTimer = window.setInterval(() => load(true), 1800)
}
function stopPolling() { if (pollTimer !== null) window.clearInterval(pollTimer); pollTimer = null }

function openNode(node: any) { selectedRun.value = null; selectedNode.value = node; drawerOpen.value = true }
async function openRun(row: any) {
  selectedNode.value = null
  try { selectedRun.value = await agent.detail(row.id) } catch { selectedRun.value = row }
  drawerOpen.value = true
}

onMounted(load)
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.command-page { max-width: 1560px; }
.run-overview { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(260px, .7fr) minmax(330px, .8fr); gap: 22px; align-items: center; margin-bottom: 16px; padding: 24px 26px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.overview-kicker { color: var(--primary); font-size: 11px; font-weight: 800; letter-spacing: .1em; }
.overview-main h1 { margin: 5px 0 10px; font-size: 24px; }
.trace-line { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; color: var(--text-muted); font-size: 12px; }
code, .mono { font-family: "SFMono-Regular", Consolas, monospace; color: var(--primary-dark); }
.progress-block > div { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 8px; }
.progress-block strong { font-size: 26px; }
.progress-block small { display: block; margin-top: 7px; color: var(--text-muted); }
.overview-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; overflow: hidden; border: 1px solid var(--border); border-radius: 11px; background: var(--border); }
.overview-metrics div { padding: 13px; background: #fafbfe; }
.overview-metrics span, .overview-metrics b { display: block; }
.overview-metrics span { color: var(--text-muted); font-size: 11px; }
.overview-metrics b { margin-top: 3px; font-size: 18px; }
.workspace-grid { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 16px; align-items: start; }
.pipeline-surface, .resource-surface, .quality-section, .run-history { padding: 20px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.resource-surface { position: sticky; top: 14px; }
.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.section-head.compact { align-items: center; }
.section-head h2 { font-size: 16px; }
.section-head p { margin-top: 3px; color: var(--text-secondary); font-size: 12px; }
.section-head > span { color: var(--text-muted); font-size: 12px; }
.status-legend { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.status-legend i { width: 7px; height: 7px; border-radius: 50%; margin-left: 4px; background: #a8b1c0; }
.status-legend i.running { background: var(--primary); }.status-legend i.success { background: var(--success); }.status-legend i.warning { background: var(--warning); }.status-legend i.failed { background: var(--danger); }
.agent-flow { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }
.agent-node { position: relative; min-height: 178px; display: flex; flex-direction: column; padding: 14px; border: 1px solid var(--border); border-top: 3px solid #a8b1c0; border-radius: 12px; background: #fff; color: var(--text); text-align: left; cursor: pointer; transition: transform .18s, box-shadow .18s, border-color .18s; }
.agent-node:hover { transform: translateY(-2px); box-shadow: var(--shadow); }
.agent-node.running { border-top-color: var(--primary); background: #fbfbff; }.agent-node.success { border-top-color: var(--success); }.agent-node.warning { border-top-color: var(--warning); background: #fffdf8; }.agent-node.failed { border-top-color: var(--danger); background: #fffafb; }
.node-index { width: 28px; height: 28px; display: grid; place-items: center; margin-bottom: 10px; border-radius: 8px; color: var(--primary); background: var(--primary-bg); font-weight: 800; }
.node-state { position: absolute; top: 16px; right: 12px; display: flex; align-items: center; gap: 5px; color: var(--text-muted); font-size: 10px; }
.node-state i { width: 7px; height: 7px; border-radius: 50%; background: #a8b1c0; }.running .node-state i { background: var(--primary); animation: pulse 1.3s infinite; }.success .node-state i { background: var(--success); }.warning .node-state i { background: var(--warning); }.failed .node-state i { background: var(--danger); }
@keyframes pulse { 50% { box-shadow: 0 0 0 5px rgba(79,70,229,.12); } }
.agent-node > b { font-size: 14px; }.agent-node > small { margin-top: 2px; color: var(--text-secondary); }.agent-node > p { display: -webkit-box; overflow: hidden; margin-top: 9px; color: var(--text-muted); font-size: 11px; line-height: 1.55; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.agent-node footer { display: flex; justify-content: space-between; gap: 8px; margin-top: auto; padding-top: 10px; color: var(--text-muted); font-size: 10px; }.agent-node footer strong { color: var(--success); }
.resource-list { display: grid; gap: 8px; }
.resource-item { display: grid; grid-template-columns: 36px minmax(0, 1fr) auto; gap: 10px; align-items: center; padding: 11px; border: 1px solid var(--border); border-radius: 10px; }
.resource-mark { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 9px; color: var(--primary); background: var(--primary-bg); }
.resource-item b, .resource-item small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.resource-item small { color: var(--text-muted); }
.resource-status { text-align: right; }.resource-status strong { display: block; margin-bottom: 3px; }
.resource-empty { min-height: 310px; display: flex; align-items: center; justify-content: center; flex-direction: column; color: var(--text-muted); text-align: center; }.resource-empty .el-icon { margin-bottom: 10px; color: var(--primary-light); font-size: 34px; }.resource-empty b { color: var(--text); }.resource-empty span { max-width: 220px; margin-top: 4px; font-size: 12px; }
.quality-section, .run-history { margin-top: 16px; }
.quality-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(185px, 1fr)); gap: 10px; }
.quality-grid article { padding: 15px; border: 1px solid var(--border); border-radius: 11px; border-left: 3px solid #a8b1c0; }.quality-grid article.pass, .quality-grid article.success { border-left-color: var(--success); }.quality-grid article.warn, .quality-grid article.warning { border-left-color: var(--warning); }.quality-grid article.failed { border-left-color: var(--danger); }
.quality-grid span { color: var(--text-secondary); font-size: 12px; }.quality-grid strong { display: block; margin: 5px 0; font-size: 25px; }.quality-grid strong small { margin-left: 3px; color: var(--text-muted); font-size: 11px; }.quality-grid p { color: var(--text-muted); font-size: 11px; }
.compact-state { min-height: 220px; margin-bottom: 16px; }
.demo-evidence-alert { margin-bottom: 16px; }
.node-inspector, .run-inspector { padding: 0 8px 24px; }
.inspector-summary { display: grid; grid-template-columns: 44px 1fr auto; gap: 12px; align-items: center; padding-bottom: 18px; border-bottom: 1px solid var(--border); }
.inspector-mark { width: 42px; height: 42px; display: grid; place-items: center; border-radius: 11px; color: #fff; background: #a8b1c0; font-weight: 800; }.inspector-mark.running { background: var(--primary); }.inspector-mark.success { background: var(--success); }.inspector-mark.warning { background: var(--warning); }.inspector-mark.failed { background: var(--danger); }
.inspector-summary h2 { font-size: 18px; }.inspector-summary p { color: var(--text-secondary); font-size: 12px; }
.inspector-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; margin: 16px 0; }.inspector-grid div { padding: 12px; border-radius: 9px; background: var(--bg-secondary); }.inspector-grid span, .inspector-grid b { display: block; }.inspector-grid span { color: var(--text-muted); font-size: 11px; }.inspector-grid b { margin-top: 3px; font-size: 13px; word-break: break-word; }
.node-inspector section { margin-top: 18px; }.node-inspector h3 { margin-bottom: 8px; font-size: 14px; }.node-inspector pre { overflow: auto; max-height: 260px; padding: 13px 14px; border: 1px solid #dce3f0; border-radius: 9px; background: #f6f8fc; color: #334155; white-space: pre-wrap; font: 12px/1.7 "PingFang SC", "Microsoft YaHei", sans-serif; }
.drawer-citations { display: grid; gap: 8px; }.drawer-citations article { padding: 11px; border: 1px solid var(--border); border-radius: 9px; }.drawer-citations b, .drawer-citations span { display: block; }.drawer-citations span { color: var(--text-muted); font-size: 11px; }.drawer-citations p { margin-top: 5px; color: var(--text-secondary); font-size: 12px; }
.execution-log { padding: 12px; border-left: 3px solid var(--primary); background: var(--primary-bg); }.execution-log span { color: var(--text-muted); font-size: 11px; }.execution-log b { display: block; margin: 3px 0; }.execution-log p { color: var(--text-secondary); }
.run-log-list { display: grid; gap: 9px; }.run-log-list article { display: grid; grid-template-columns: 30px 1fr auto; gap: 10px; padding: 12px; border: 1px solid var(--border); border-radius: 10px; }.run-log-list article > span { width: 28px; height: 28px; display: grid; place-items: center; border-radius: 8px; color: var(--primary); background: var(--primary-bg); font-weight: 800; }.run-log-list p { color: var(--text-secondary); font-size: 12px; }.run-log-list em { color: var(--text-muted); font-style: normal; font-size: 11px; }
@media (max-width: 1240px) { .run-overview { grid-template-columns: 1fr 1fr; }.overview-metrics { grid-column: 1 / -1; }.agent-flow { grid-template-columns: repeat(3, minmax(0, 1fr)); }.workspace-grid { grid-template-columns: 1fr; }.resource-surface { position: static; } }
@media (max-width: 760px) { .run-overview { grid-template-columns: 1fr; }.overview-metrics { grid-column: auto; }.agent-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); }.status-legend { display: none; }.inspector-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 480px) { .agent-flow, .overview-metrics, .inspector-grid { grid-template-columns: 1fr; } }
</style>
