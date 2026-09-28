<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="page-title">系统数据看板</div>
        <div class="page-desc">面向高校教学部署的运行驾驶舱：统一观测用户、课程、资源、智能体、模型调用与审核健康度。</div>
      </div>
      <div class="toolbar-actions">
        <el-button :loading="exporting" @click="exportSnapshot">
          <el-icon><Download /></el-icon> 导出数据快照
        </el-button>
        <el-button type="primary" @click="$router.push('/admin/logs')">
          <el-icon><Notebook /></el-icon> 调用日志
        </el-button>
      </div>
    </div>

    <div v-if="loading" class="card"><el-skeleton :rows="8" animated /></div>
    <div v-else-if="error" class="page-state error"><div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>运营数据加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div></div>
    <template v-else>
      <div class="grid grid-4">
        <div class="stat-card">
          <div class="stat-label">总用户数</div>
          <div class="stat-value">{{ d.total_users }}</div>
          <div class="stat-sub">学生 / 教师 / 管理员</div>
          <div class="stat-icon"><el-icon><User /></el-icon></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">课程资产</div>
          <div class="stat-value">{{ d.total_courses }}</div>
          <div class="stat-sub">{{ d.total_courses || 0 }} 门有效课程正在运行</div>
          <div class="stat-icon"><el-icon><Reading /></el-icon></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">生成资源</div>
          <div class="stat-value">{{ d.total_resources }}</div>
          <div class="stat-sub">讲义 / 练习 / 导图 / 课件</div>
          <div class="stat-icon"><el-icon><FolderOpened /></el-icon></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">审核通过率</div>
          <div class="stat-value">{{ d.approved_rate }}<span style="font-size:14px">%</span></div>
          <div class="stat-sub">{{ d.published }} 个资源已发布</div>
          <div class="stat-icon"><el-icon><Checked /></el-icon></div>
        </div>
      </div>

      <div class="ops-strip">
        <div>
          <span>Agent 成功运行</span>
          <b>{{ d.success_runs || 0 }}</b>
        </div>
        <div>
          <span>Agent 失败</span>
          <b>{{ d.failed_runs || 0 }}</b>
        </div>
        <div>
          <span>AI 调用次数</span>
          <b>{{ d.llm_calls || 0 }}</b>
        </div>
        <div>
          <span>AI 调用成功率</span>
          <b>{{ d.llm_calls ? (d.llm_success_rate || 0) : 0 }}%</b>
        </div>
      </div>

      <section v-if="runtime.application" class="runtime-panel">
        <header>
          <div><span class="runtime-kicker">APPLICATION HEALTH</span><h2>应用运行状态</h2></div>
          <small>状态来自当前后端实例，不展示凭据或基础设施地址</small>
        </header>
        <div class="runtime-grid">
          <article>
            <span class="runtime-icon healthy"><el-icon><Coin /></el-icon></span>
            <div><small>数据库</small><b>连接正常</b><p>{{ runtime.database?.backend || 'SQL 数据库' }}</p></div>
            <el-tag type="success" effect="plain" size="small">健康</el-tag>
          </article>
          <article>
            <span :class="['runtime-icon', runtime.ai?.degraded ? 'warning' : runtime.ai?.mode === 'real' ? 'healthy' : 'demo']"><el-icon><MagicStick /></el-icon></span>
            <div><small>智能生成</small><b>{{ aiStatusLabel }}</b><p>{{ runtime.ai?.provider || 'mock' }} · {{ runtime.ai?.model || '课程引擎' }}</p></div>
            <el-tag :type="runtime.ai?.degraded ? 'warning' : runtime.ai?.mode === 'real' ? 'success' : 'info'" effect="plain" size="small">{{ runtime.ai?.degraded ? '已降级' : runtime.ai?.mode === 'real' ? '在线' : '演示' }}</el-tag>
          </article>
          <article>
            <span :class="['runtime-icon', runtime.agents?.running ? 'active' : 'healthy']"><el-icon><Cpu /></el-icon></span>
            <div><small>智能体调度</small><b>{{ runtime.agents?.running ? `${runtime.agents.running} 个任务执行中` : '调度就绪' }}</b><p>累计 {{ runtime.agents?.total || 0 }} 次 · 成功 {{ runtime.agents?.success || 0 }} 次</p></div>
            <el-tag :type="runtime.agents?.running ? 'primary' : 'success'" effect="plain" size="small">{{ runtime.agents?.running ? '运行中' : '就绪' }}</el-tag>
          </article>
          <article>
            <span class="runtime-icon active"><el-icon><Monitor /></el-icon></span>
            <div><small>应用实例</small><b>XunkeFlow v{{ runtime.application.version }}</b><p>启动于 {{ formatDate(runtime.application.started_at) }} · 已运行 {{ formatUptime(runtime.application.uptime_seconds) }}</p></div>
            <el-tag type="primary" effect="plain" size="small">在线</el-tag>
          </article>
        </div>
      </section>

      <div class="grid" style="grid-template-columns: 1fr 1fr 1fr; gap:16px; margin-top:16px">
        <div class="card">
          <div class="card-title"><el-icon><PieChart /></el-icon> 角色分布</div>
          <v-chart :option="roleOption" style="height:260px" autoresize />
        </div>
        <div class="card">
          <div class="card-title"><el-icon><DataAnalysis /></el-icon> 资源类型</div>
          <v-chart :option="resourceOption" style="height:260px" autoresize />
        </div>
        <div class="card">
          <div class="card-title"><el-icon><Checked /></el-icon> 审核状态</div>
          <v-chart :option="reviewOption" style="height:260px" autoresize />
        </div>
      </div>

      <div class="grid" style="grid-template-columns: 1.2fr .8fr; gap:16px">
        <div class="card">
          <div class="card-title"><el-icon><TrendCharts /></el-icon> 课程资源运营</div>
          <v-chart :option="courseOption" style="height:310px" autoresize />
        </div>
        <div class="card">
          <div class="card-title"><el-icon><Connection /></el-icon> 最近智能体运行</div>
          <div class="run-list">
            <div v-for="r in d.recent_runs || []" :key="r.id" class="run-row">
              <span :class="['run-dot', r.status]"></span>
              <div>
                <b>{{ flowText(r.workflow) }}</b>
                <small>{{ r.trace_id }}</small>
              </div>
              <el-tag size="small" :type="statusType(r.status)">{{ statusText(r.status) }}</el-tag>
            </div>
            <el-empty v-if="!(d.recent_runs || []).length" description="暂无运行记录" :image-size="72" />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart as EChartsPieChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { admin } from '@/api'

use([CanvasRenderer, BarChart, EChartsPieChart, TooltipComponent, GridComponent, LegendComponent])

const loading = ref(true)
const exporting = ref(false)
const error = ref('')
const d = ref<any>({})
const palette = ['#2563eb', '#0f766e', '#f59e0b', '#dc2626', '#7c3aed', '#0891b2', '#64748b']
const runtime = computed(() => d.value.runtime_status || {})
const aiStatusLabel = computed(() => runtime.value.ai?.degraded
  ? '真实服务异常，安全降级'
  : runtime.value.ai?.mode === 'real' ? '真实模型模式' : '本地演示模式')

const roleOption = computed(() => pieOption(d.value.role_distribution || []))
const resourceOption = computed(() => pieOption(d.value.resource_distribution || []))
const reviewOption = computed(() => pieOption(d.value.review_distribution || []))
const courseOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: { top: 0 },
  grid: { left: 34, right: 20, bottom: 32, top: 42 },
  xAxis: { type: 'category', data: (d.value.course_cards || []).map((c: any) => c.name), axisLabel: { interval: 0 } },
  yAxis: { type: 'value' },
  series: [
    { name: '资源数', type: 'bar', barWidth: 28, data: (d.value.course_cards || []).map((c: any) => c.resources), itemStyle: { color: '#2563eb', borderRadius: [6, 6, 0, 0] } },
    { name: 'Agent运行', type: 'bar', barWidth: 28, data: (d.value.course_cards || []).map((c: any) => c.agent_runs), itemStyle: { color: '#0f766e', borderRadius: [6, 6, 0, 0] } }
  ]
}))

function pieOption(data: any[]) {
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, type: 'scroll' },
    color: palette,
    series: [{
      type: 'pie',
      radius: ['46%', '72%'],
      center: ['50%', '43%'],
      data,
      label: { formatter: '{b}: {c}' }
    }]
  }
}

const statusText = (s: string) => ({ running: '运行中', success: '成功', failed: '失败' }[s] || s)
const statusType = (s: string) => ({ running: 'warning', success: 'success', failed: 'danger' }[s] as any)
const flowText = (workflow: string) => ({
  full_pipeline: '完整协作流程',
  parse: '资料解析',
  generate: '资源生成',
  diagnose: '学习诊断',
  single_test: '单项校验'
}[workflow] || '课程智能任务')

function formatDate(value: string) {
  if (!value) return '本次启动'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '本次启动'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(date)
}

function formatUptime(value: number) {
  const seconds = Math.max(0, Number(value || 0))
  if (seconds < 60) return `${Math.floor(seconds)} 秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return hours < 24 ? `${hours} 小时 ${minutes} 分钟` : `${Math.floor(hours / 24)} 天 ${hours % 24} 小时`
}

async function exportSnapshot() {
  exporting.value = true
  try {
    const blob = await admin.exportSnapshot()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')
    link.href = url
    link.download = `xunkeflow-data-snapshot-${stamp}.json`
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('安全数据快照已开始下载')
  } catch (err: any) {
    ElMessage.error(err?.message || '数据快照导出失败')
  } finally {
    exporting.value = false
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try { d.value = await admin.dashboard() }
  catch (err: any) { error.value = err?.message || '请稍后重新加载运营数据。' }
  finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.ops-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 16px;
}
.ops-strip div {
  background: var(--gradient-soft);
  border: 1px solid rgba(37,99,235,.12);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ops-strip span { color: var(--text-secondary); font-size: 12px; font-weight: 700; }
.ops-strip b { font-size: 20px; }
.runtime-panel {
  margin-top: 16px;
  padding: 18px 20px 0;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--card-bg);
  box-shadow: var(--shadow-sm);
}
.runtime-panel > header { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; padding-bottom: 15px; border-bottom: 1px solid var(--border-light); }
.runtime-panel > header h2 { margin-top: 2px; font-size: 16px; }
.runtime-panel > header > small { color: var(--text-muted); font-size: 11px; }
.runtime-kicker { color: var(--primary); font-size: 10px; font-weight: 800; letter-spacing: .1em; }
.runtime-grid { display: grid; grid-template-columns: repeat(4, 1fr); }
.runtime-grid article { min-width: 0; display: grid; grid-template-columns: 38px minmax(0, 1fr) auto; align-items: center; gap: 10px; padding: 17px 16px; }
.runtime-grid article + article { border-left: 1px solid var(--border-light); }
.runtime-icon { width: 36px; height: 36px; display: grid; place-items: center; border-radius: 10px; color: var(--primary); background: var(--primary-bg); font-size: 17px; }
.runtime-icon.healthy { color: var(--success); background: var(--success-bg); }
.runtime-icon.warning { color: var(--warning); background: var(--warning-bg); }
.runtime-icon.demo { color: var(--text-secondary); background: var(--bg-secondary); }
.runtime-icon.active { color: var(--primary); background: var(--primary-bg); }
.runtime-grid article small { display: block; color: var(--text-muted); font-size: 10px; font-weight: 700; letter-spacing: .05em; }
.runtime-grid article b { display: block; margin-top: 1px; overflow: hidden; color: var(--text); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.runtime-grid article p { margin-top: 2px; overflow: hidden; color: var(--text-secondary); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.run-list { display: grid; gap: 8px; }
.run-row {
  display: grid;
  grid-template-columns: 12px 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 10px;
  background: #f8fafc;
}
.run-row b { display: block; font-size: 13px; }
.run-row small { display: block; color: var(--text-muted); margin-top: 2px; }
.run-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--text-muted); }
.run-dot.success { background: var(--success); }
.run-dot.failed { background: var(--danger); }
.run-dot.running { background: var(--warning); }
@media (max-width: 1100px) {
  .ops-strip,
  .runtime-grid,
  .page :deep(.grid[style*="1fr 1fr 1fr"]),
  .page :deep(.grid[style*="1.2fr"]) { grid-template-columns: 1fr !important; }
  .runtime-grid article + article { border-top: 1px solid var(--border-light); border-left: 0; }
}
@media (max-width: 720px) { .runtime-panel > header { align-items: flex-start; flex-direction: column; } }
</style>
