<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="page-title">AI 调用日志</div>
        <div class="page-desc">记录每一次生成、检索增强与质量校验调用，便于成本估算、质量追踪和故障排查。</div>
      </div>
      <el-input v-model="keyword" class="search" placeholder="过滤用途 / Trace / 模型" clearable>
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <el-alert v-if="error" type="error" :closable="false" show-icon style="margin-bottom:16px">{{ error }} <el-button text @click="load">重新加载</el-button></el-alert>

    <div class="grid grid-4">
      <div class="stat-card">
        <div class="stat-label">调用总数</div>
        <div class="stat-value">{{ logs.length }}</div>
        <div class="stat-icon"><el-icon><Connection /></el-icon></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">成功率</div>
        <div class="stat-value">{{ successRate }}<span style="font-size:14px">%</span></div>
        <div class="stat-icon"><el-icon><Checked /></el-icon></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">平均耗时</div>
        <div class="stat-value">{{ avgDuration }}<span style="font-size:14px">ms</span></div>
        <div class="stat-icon"><el-icon><Timer /></el-icon></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">输出 Tokens</div>
        <div class="stat-value">{{ totalCompletion }}</div>
        <div class="stat-icon"><el-icon><DataLine /></el-icon></div>
      </div>
    </div>

    <div class="card">
      <div class="card-title"><el-icon><Notebook /></el-icon> 调用明细</div>
      <el-table :data="filtered" size="small" stripe>
        <el-table-column type="expand" width="44">
          <template #default="{ row }">
            <div class="log-detail">
              <div><small>响应长度</small><b>{{ row.response_chars || 0 }} 字符</b></div>
              <div><small>重试次数</small><b>{{ row.retry_count || 0 }}</b></div>
              <div><small>降级保护</small><b :class="row.fallback_used ? 'text-warning' : ''">{{ row.fallback_used ? '已启用' : '未启用' }}</b></div>
              <div><small>成本估算</small><b>{{ row.estimated_cost == null ? '未估算' : row.estimated_cost }}</b></div>
              <div><small>错误信息</small><b :class="row.error ? 'text-danger' : ''">{{ row.error || '无' }}</b></div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="id" label="ID" width="64" />
        <el-table-column prop="provider" label="服务来源" width="130">
          <template #default="{ row }"><el-tag size="small" type="info">{{ providerText(row.provider) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="model" label="生成引擎" min-width="160">
          <template #default="{ row }">{{ modelText(row.model, row.provider) }}</template>
        </el-table-column>
        <el-table-column prop="purpose" label="业务用途" min-width="130">
          <template #default="{ row }">{{ purposeText(row.purpose) }}</template>
        </el-table-column>
        <el-table-column prop="trace_id" label="任务编号" min-width="160">
          <template #default="{ row }"><code>{{ row.trace_id }}</code></template>
        </el-table-column>
        <el-table-column label="Tokens" width="130">
          <template #default="{ row }">{{ row.prompt_tokens }} / {{ row.completion_tokens }}</template>
        </el-table-column>
        <el-table-column prop="duration_ms" label="耗时" width="100">
          <template #default="{ row }"><span :class="row.duration_ms > 1000 ? 'text-warning' : 'text-success'">{{ row.duration_ms }}ms</span></template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.fallback_used ? 'warning' : row.success ? 'success' : 'danger'">{{ row.fallback_used ? '已降级' : row.success ? '成功' : '失败' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="170" />
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { admin } from '@/api'

const logs = ref<any[]>([])
const error = ref('')
const keyword = ref('')
const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return logs.value
  return logs.value.filter(l => [l.purpose, l.trace_id, l.model, l.provider, l.error].some(v => String(v || '').toLowerCase().includes(k)))
})
const successRate = computed(() => logs.value.length ? Math.round(logs.value.filter(l => l.success).length / logs.value.length * 100) : 100)
const avgDuration = computed(() => logs.value.length ? Math.round(logs.value.reduce((s, l) => s + (l.duration_ms || 0), 0) / logs.value.length) : 0)
const totalCompletion = computed(() => logs.value.reduce((s, l) => s + (l.completion_tokens || 0), 0))
const providerText = (provider: string) => provider === 'deepseek' ? '在线智能服务' : '演示内容服务'
const modelText = (model: string, provider: string) => provider === 'deepseek' ? 'DeepSeek Flash' : '本地课程引擎'
const purposeText = (purpose: string) => ({
  lecture: '讲义生成', lecture_stream: '讲义生成', exercise: '练习生成', mindmap: '思维导图',
  multimodal: '多类型资源', quality: '质量校验', teacher_review: '教师预审', diagnosis: '学习诊断',
  fallback_test: '服务降级校验', general: '内容生成'
} as Record<string, string>)[purpose] || '内容生成'

async function load() {
  error.value = ''
  try { logs.value = await admin.llmLogs() }
  catch (err: any) { error.value = err?.message || '调用日志加载失败。' }
}
onMounted(load)
</script>

<style scoped>
.search { width: 300px; }
code { background: #f1f5f9; padding: 3px 6px; border-radius: 6px; font-size: 12px; }
.log-detail { display: grid; grid-template-columns: 130px 110px 120px 110px minmax(220px, 1fr); gap: 14px; padding: 14px 18px; background: #f8fafc; border-radius: 10px; }
.log-detail small, .log-detail b { display: block; }
.log-detail small { color: var(--text-muted); font-size: 11px; }
.log-detail b { margin-top: 4px; font-size: 12px; word-break: break-word; }
@media (max-width: 900px) { .log-detail { grid-template-columns: repeat(2, 1fr); } }
</style>
