<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="page-title">课程资料</div>
        <div class="page-desc">上传后自动完成文本解析、内容分块和课程检索索引。</div>
      </div>
      <span class="metric-chip">课程 #{{ cid }}</span>
    </div>

    <section class="upload-layout">
      <div class="upload-panel">
        <el-upload
          drag
          :show-file-list="false"
          :http-request="customUpload"
          :before-upload="beforeUpload"
          accept=".pdf,.docx,.pptx,.txt,.md,.markdown"
          :disabled="uploading"
        >
          <span class="upload-icon"><el-icon><UploadFilled /></el-icon></span>
          <div class="upload-title">拖放课程资料到这里</div>
          <p>或点击选择 PDF、Word、PPT、TXT、Markdown 文件</p>
          <el-button type="primary" plain :loading="uploading">{{ uploading ? '正在上传' : '选择文件' }}</el-button>
          <template #tip><div class="upload-tip">单个文件不超过 50MB；建议上传包含完整章节结构的教学资料。</div></template>
        </el-upload>
      </div>

      <div class="process-panel">
        <div class="process-head"><b>处理进度</b><span>{{ processText }}</span></div>
        <el-steps direction="vertical" :active="processStep" finish-status="success">
          <el-step title="资料已上传" description="文件安全保存到课程资料区" />
          <el-step title="正文解析" description="提取章节、段落和页码信息" />
          <el-step title="课程索引" description="建立可检索的课程知识片段" />
          <el-step title="可用于内容生成" description="讲义、题目与审核可引用原文" />
        </el-steps>
      </div>
    </section>

    <div v-if="loading" class="card"><el-skeleton :rows="6" animated /></div>
    <div v-else-if="error" class="page-state error">
      <div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>资料列表加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div>
    </div>
    <section v-else class="card file-section">
      <div class="toolbar file-toolbar">
        <div class="card-title"><el-icon><Files /></el-icon>已上传资料（{{ files.length }}）</div>
        <el-button :loading="refreshing" @click="refreshAll"><el-icon><Refresh /></el-icon>刷新状态</el-button>
      </div>
      <el-table :data="files" stripe>
        <el-table-column label="资料" min-width="250">
          <template #default="{ row }">
            <div class="file-name"><span><el-icon><Document /></el-icon></span><div><b>{{ row.filename }}</b><small>{{ formatSize(row.size) }} · {{ String(row.file_type || '').toUpperCase() }}</small></div></div>
          </template>
        </el-table-column>
        <el-table-column label="处理状态" width="130">
          <template #default="{ row }"><el-tag size="small" :type="parseType(row.parse_status)" effect="plain">{{ parseText(row.parse_status) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="课程索引" width="110"><template #default="{ row }"><span :class="row.indexed ? 'text-success' : 'muted'">{{ row.indexed ? '已就绪' : '未完成' }}</span></template></el-table-column>
        <el-table-column label="处理说明" min-width="260">
          <template #default="{ row }"><span :class="row.parse_status === 'failed' ? 'text-danger' : 'muted'">{{ summaryText(row) }}</span></template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="180"><template #default="{ row }">{{ formatTime(row.created_at) }}</template></el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="refreshOne(row)">刷新</el-button>
            <el-button v-if="row.parse_status === 'failed'" size="small" type="primary" plain :loading="retryingId === row.id" @click="retryFile(row)">重新解析</el-button>
            <el-button size="small" type="danger" plain @click="removeFile(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="尚未上传课程资料" /></template>
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fileApi } from '@/api'

const route = useRoute()
const cid = computed(() => Number(route.params.cid))
const files = ref<any[]>([])
const loading = ref(true)
const uploading = ref(false)
const refreshing = ref(false)
const retryingId = ref<number | null>(null)
const error = ref('')
let pollTimer: number | null = null
let pollCount = 0

const pendingFiles = computed(() => files.value.filter((row) => ['pending', 'parsing', 'indexing'].includes(row.parse_status)))
const failedFiles = computed(() => files.value.filter((row) => row.parse_status === 'failed'))
const processStep = computed(() => {
  if (!files.value.length) return 0
  if (pendingFiles.value.length) return files.value.some((row) => row.indexed) ? 2 : 1
  if (files.value.some((row) => row.indexed)) return 4
  return failedFiles.value.length ? 1 : 2
})
const processText = computed(() => pendingFiles.value.length ? `${pendingFiles.value.length} 个文件处理中` : failedFiles.value.length ? `${failedFiles.value.length} 个文件需要处理` : files.value.length ? '课程资料已就绪' : '等待上传')

const parseText = (status: string) => ({ pending: '等待处理', parsing: '正在解析', indexing: '正在索引', parsed: '处理完成', failed: '处理失败' }[status] || status || '未知')
const parseType = (status: string) => ({ pending: 'warning', parsing: 'primary', indexing: 'primary', parsed: 'success', failed: 'danger' }[status] as any)
const formatSize = (size: number) => size >= 1024 * 1024 ? `${(size / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, size / 1024).toFixed(1)} KB`
const formatTime = (value: string) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'

function summaryText(row: any) {
  if (row.parse_summary) {
    try {
      const parsed = JSON.parse(row.parse_summary)
      if (parsed.error) return parsed.error
      const parts = []
      if (parsed.pages) parts.push(`${parsed.pages} 页`)
      if (parsed.chunks) parts.push(`${parsed.chunks} 个片段`)
      if (parsed.points) parts.push(`${parsed.points} 个知识点`)
      return parts.join(' · ') || row.parse_summary
    } catch { return row.parse_summary }
  }
  if (row.parse_status === 'pending') return '系统将在后台自动处理'
  if (row.parse_status === 'failed') return '可点击“重新解析”；若仍失败，请检查文件是否损坏或为扫描件'
  return row.indexed ? '已可用于课程内容生成' : '等待建立课程索引'
}

function beforeUpload(file: File) {
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.warning('单个文件不能超过 50MB')
    return false
  }
  return true
}

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    files.value = await fileApi.list(cid.value)
    schedulePolling()
  } catch (err: any) {
    if (!silent) error.value = err?.message || '请检查服务连接后重试。'
  } finally {
    if (!silent) loading.value = false
  }
}

async function customUpload(option: any) {
  uploading.value = true
  try {
    await fileApi.upload(cid.value, option.file)
    ElMessage.success('上传完成，系统正在解析课程资料')
    pollCount = 0
    await load(true)
  } catch (err: any) {
    ElMessage.error(err?.message || '文件上传失败')
  } finally {
    uploading.value = false
  }
}

async function refreshOne(row: any) {
  try {
    const status = await fileApi.parseStatus(row.id)
    Object.assign(row, { parse_status: status.status, parse_summary: status.summary, indexed: status.indexed })
    ElMessage.success('状态已更新')
  } catch (err: any) {
    ElMessage.error(err?.message || '状态刷新失败')
  }
}

async function refreshAll() {
  refreshing.value = true
  try { await load(true) } finally { refreshing.value = false }
}

async function retryFile(row: any) {
  retryingId.value = row.id
  try {
    const result = await fileApi.retry(row.id)
    Object.assign(row, {
      parse_status: result.status,
      parse_summary: result.summary,
      indexed: result.indexed
    })
    pollCount = 0
    schedulePolling()
    ElMessage.success('已重新提交解析任务')
  } catch (err: any) {
    ElMessage.error(err?.message || '重新解析失败')
  } finally {
    retryingId.value = null
  }
}

async function poll() {
  if (!pendingFiles.value.length || pollCount >= 40) return stopPolling()
  pollCount += 1
  await Promise.all(pendingFiles.value.map(async (row) => {
    try {
      const status = await fileApi.parseStatus(row.id, true)
      Object.assign(row, { parse_status: status.status, parse_summary: status.summary, indexed: status.indexed })
    } catch { /* 下一轮继续尝试 */ }
  }))
  schedulePolling()
}

function schedulePolling() {
  stopPolling()
  if (pendingFiles.value.length && pollCount < 40) pollTimer = window.setTimeout(poll, 2500)
}
function stopPolling() { if (pollTimer !== null) window.clearTimeout(pollTimer); pollTimer = null }

async function removeFile(row: any) {
  try { await ElMessageBox.confirm(`确定删除“${row.filename}”吗？相关课程索引也将失效。`, '删除课程资料', { type: 'warning' }) } catch { return }
  await fileApi.remove(row.id)
  ElMessage.success('资料已删除')
  await load(true)
}

onMounted(load)
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.upload-layout { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(320px, .75fr); gap: 16px; margin-bottom: 16px; }
.upload-panel, .process-panel { padding: 22px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.upload-panel :deep(.el-upload), .upload-panel :deep(.el-upload-dragger) { width: 100%; }
.upload-panel :deep(.el-upload-dragger) { min-height: 298px; display: flex; flex-direction: column; align-items: center; justify-content: center; border-color: #cfd4f8; background: #fbfbff; }
.upload-panel :deep(.el-upload-dragger:hover) { border-color: var(--primary); }
.upload-icon { width: 54px; height: 54px; display: grid; place-items: center; margin-bottom: 14px; border-radius: 15px; color: var(--primary); background: var(--primary-bg); font-size: 25px; }
.upload-title { font-size: 18px; font-weight: 750; }
.upload-panel p { margin: 5px 0 18px; color: var(--text-secondary); }
.upload-tip { margin-top: 12px; color: var(--text-muted); text-align: center; }
.process-head { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 18px; }
.process-head span { color: var(--text-secondary); font-size: 12px; }
.process-panel :deep(.el-step__title) { font-size: 14px; }
.process-panel :deep(.el-step__description) { padding-bottom: 11px; font-size: 12px; }
.file-toolbar { margin-bottom: 14px; }
.file-toolbar .card-title { margin: 0; }
.file-name { display: flex; align-items: center; gap: 10px; }
.file-name > span { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 9px; color: var(--primary); background: var(--primary-bg); }
.file-name b, .file-name small { display: block; }
.file-name small { color: var(--text-muted); }
@media (max-width: 960px) { .upload-layout { grid-template-columns: 1fr; } }
</style>
