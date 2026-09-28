<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="page-title">智能服务配置</div>
        <div class="page-desc">查看内容生成、课程检索和调用健康状态；敏感凭据不会在页面展示。</div>
      </div>
      <div class="toolbar-actions"><span :class="['status-badge', (demoMode || degraded) ? 'demo' : 'live']">{{ degraded ? '服务降级' : demoMode ? '演示模式' : '在线模式' }}</span><el-button :loading="loading" @click="load"><el-icon><Refresh /></el-icon>刷新</el-button></div>
    </div>

    <div v-if="loading" class="card"><el-skeleton :rows="8" animated /></div>
    <div v-else-if="error" class="page-state error"><div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>运行状态加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div></div>
    <template v-else>
      <section class="service-overview">
        <article><span><el-icon><Cpu /></el-icon></span><div><small>当前 Provider</small><b>{{ providerLabel }}</b><p>{{ modelLabel }}</p></div></article>
        <article><span><el-icon><Key /></el-icon></span><div><small>访问凭据</small><b>{{ keyConfigured ? '已配置' : '未配置' }}</b><p>{{ keyConfigured ? '凭据由后端环境安全读取' : '请在服务端环境文件中配置后重启' }}</p></div></article>
        <article><span><el-icon><Share /></el-icon></span><div><small>课程检索</small><b>{{ friendlyValue(info.vector_store, '本地课程索引') }}</b><p>用于定位课程原文并展示引用来源</p></div></article>
        <article><span><el-icon><CircleCheck /></el-icon></span><div><small>最近调用</small><b :class="lastCall?.success === false ? 'text-danger' : 'text-success'">{{ lastCall ? (lastCall.success ? '成功' : '失败') : '暂无记录' }}</b><p>{{ lastCall ? `${lastCall.duration_ms || 0} 毫秒` : '完成一次生成任务后显示' }}</p></div></article>
      </section>

      <section class="settings-grid">
        <div class="settings-panel">
          <header><h2>运行策略</h2><p>这些状态由后端环境配置决定，页面不会保存明文凭据。</p></header>
          <dl>
            <div><dt>当前模式</dt><dd>{{ degraded ? '在线调用失败后的演示降级' : demoMode ? '演示内容模式' : '真实模型模式' }}</dd></div>
            <div><dt>当前 Provider</dt><dd>{{ providerLabel }}</dd></div>
            <div><dt>当前模型</dt><dd>{{ modelLabel }}</dd></div>
            <div><dt>禁止 Pro 模型</dt><dd>是 · 后端策略强制执行</dd></div>
            <div><dt>课程检索方式</dt><dd>{{ friendlyValue(info.embedding_provider, '本地检索') }}</dd></div>
            <div><dt>失败保护</dt><dd>请求失败会记录原因，并保留页面重试入口</dd></div>
            <div><dt>凭据安全</dt><dd>仅显示配置状态，不返回或保存真实密钥</dd></div>
          </dl>
          <el-alert :type="(demoMode || degraded) ? 'warning' : 'success'" :closable="false" show-icon>
            {{ IS_SHOWCASE ? '当前为前端展示，以下是样例服务配置。运行完整服务后可启用生成、上传与测评功能。' : degraded ? '真实模型调用失败，当前使用演示模式结果；请查看最近调用错误后重试。' : demoMode ? '当前可完整运行演示流程；请在 .env 中配置 DEEPSEEK_API_KEY 后重启后端以启用在线服务。' : '在线智能服务运行中，生成结果仍需经过质量校验与教师审核。' }}
          </el-alert>
        </div>

        <div class="health-panel">
          <header><h2>调用健康度</h2><p>统计最近 {{ logs.length }} 次内容生成调用。</p></header>
          <div class="health-summary"><div><b>{{ successRate }}%</b><span>成功率</span></div><div><b>{{ avgDuration }}</b><span>平均耗时（毫秒）</span></div><div><b>{{ failedCount }}</b><span>失败次数</span></div></div>
          <div v-if="logs.length" class="health-list">
            <article v-for="item in logs.slice(0, 8)" :key="item.id"><i :class="item.success ? 'success' : 'failed'"></i><div><b>{{ purposeText(item.purpose) }}</b><small>{{ formatTime(item.created_at) }}</small></div><span>{{ item.duration_ms || 0 }} ms</span></article>
          </div>
          <div v-else class="health-empty">暂无调用记录，完成一次资源生成后即可查看。</div>
        </div>
      </section>

      <section class="card config-table">
        <div class="card-title"><el-icon><Setting /></el-icon>后端配置状态</div>
        <el-table :data="safeConfigs" size="small" stripe>
          <el-table-column prop="label" label="配置项" min-width="220" />
          <el-table-column prop="display" label="当前状态" min-width="220" />
          <el-table-column prop="category" label="分类" width="130" />
          <el-table-column prop="remark" label="说明" min-width="280" />
          <template #empty><el-empty description="暂无可展示配置" /></template>
        </el-table>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { admin, system } from '@/api'
import { IS_SHOWCASE } from '@/config/runtime'

const loading = ref(true)
const error = ref('')
const info = ref<any>({})
const configs = ref<any[]>([])
const logs = ref<any[]>([])

const demoMode = computed(() => !!(info.value.demo_mode ?? info.value.is_mock_llm))
const degraded = computed(() => !!info.value.degraded)
const providerLabel = computed(() => String(info.value.llm_provider || '').toLowerCase() === 'deepseek' ? 'DeepSeek' : 'MockLLM')
const modelLabel = computed(() => info.value.llm_model || 'deepseek-v4-flash')
const keyConfigured = computed(() => info.value.api_key_configured ?? info.value.key_configured ?? !demoMode.value)
const lastCall = computed(() => {
  const current = info.value.last_call
  if (current?.trace_id) return { ...current, success: !!current.ok }
  return logs.value[0] || null
})
const failedCount = computed(() => logs.value.filter((item) => !item.success).length)
const successRate = computed(() => logs.value.length ? Math.round(logs.value.filter((item) => item.success).length / logs.value.length * 100) : 0)
const avgDuration = computed(() => logs.value.length ? Math.round(logs.value.reduce((sum, item) => sum + Number(item.duration_ms || 0), 0) / logs.value.length) : 0)
const safeConfigs = computed(() => configs.value.map((row) => ({
  ...row,
  label: configLabel(row.key),
  display: /key|secret|token|password/i.test(row.key) ? (row.value ? '已配置' : '未配置') : (row.value || '未配置')
})))

const configLabel = (key: string) => ({ LLM_PROVIDER: '内容服务类型', LLM_MODEL: '服务版本', DEEPSEEK_API_KEY: '在线服务凭据', DEEPSEEK_BASE_URL: '在线服务地址', EMBEDDING_PROVIDER: '课程检索方式', VECTOR_STORE: '课程索引存储' }[key] || key)
const purposeText = (purpose: string) => ({ lecture: '讲义生成', exercise: '练习生成', mindmap: '思维导图', quality: '质量校验', teacher_review: '教师预审', lecture_stream: '讲义生成' }[purpose] || '内容生成')
const friendlyValue = (value: string, fallback: string) => !value || value === '-' ? fallback : value
const formatTime = (value: string) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'

async function load() {
  loading.value = true
  error.value = ''
  try {
    ;[info.value, configs.value, logs.value] = await Promise.all([system.info(), admin.configs(), admin.llmLogs()])
  } catch (err: any) {
    error.value = err?.message || '请检查后端服务后重试。'
  } finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.service-overview { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.service-overview article { display: grid; grid-template-columns: 42px 1fr; gap: 12px; padding: 18px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.service-overview article > span { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 11px; color: var(--primary); background: var(--primary-bg); font-size: 18px; }.service-overview small, .service-overview b, .service-overview p { display: block; }.service-overview small { color: var(--text-muted); }.service-overview b { margin-top: 3px; font-size: 16px; }.service-overview p { margin-top: 5px; color: var(--text-secondary); font-size: 11px; line-height: 1.55; }
.settings-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(400px, .85fr); gap: 16px; }
.settings-panel, .health-panel { padding: 22px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }.settings-panel header, .health-panel header { margin-bottom: 16px; }.settings-panel h2, .health-panel h2 { font-size: 16px; }.settings-panel header p, .health-panel header p { color: var(--text-secondary); font-size: 12px; }
.settings-panel dl { margin-bottom: 16px; }.settings-panel dl div { display: grid; grid-template-columns: 145px 1fr; gap: 12px; padding: 11px 0; border-bottom: 1px solid var(--border-light); }.settings-panel dt { color: var(--text-secondary); }.settings-panel dd { font-weight: 650; }
.health-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; overflow: hidden; border: 1px solid var(--border); border-radius: 10px; background: var(--border); }.health-summary div { padding: 13px; background: #fafbfe; }.health-summary b, .health-summary span { display: block; }.health-summary b { font-size: 21px; }.health-summary span { color: var(--text-muted); font-size: 11px; }
.health-list { display: grid; gap: 7px; margin-top: 14px; }.health-list article { display: grid; grid-template-columns: 9px 1fr auto; gap: 9px; align-items: center; padding: 9px 10px; border-radius: 9px; background: var(--bg-secondary); }.health-list i { width: 8px; height: 8px; border-radius: 50%; }.health-list i.success { background: var(--success); }.health-list i.failed { background: var(--danger); }.health-list b, .health-list small { display: block; }.health-list small { color: var(--text-muted); }.health-list > article > span { color: var(--text-secondary); font-size: 12px; }.health-empty { margin-top: 14px; padding: 28px; border-radius: 10px; background: var(--bg-secondary); color: var(--text-secondary); text-align: center; }
.config-table { margin-top: 16px; }
@media (max-width: 1180px) { .service-overview { grid-template-columns: repeat(2, 1fr); }.settings-grid { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .service-overview { grid-template-columns: 1fr; }.settings-panel dl div { grid-template-columns: 1fr; gap: 2px; } }
</style>
