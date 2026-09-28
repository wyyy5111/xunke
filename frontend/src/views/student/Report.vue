<template>
  <div class="page">
    <div class="page-header">
      <div><div class="page-title">个人学习报告</div><div class="page-desc">汇总前测、后测、知识点掌握、错题与后续学习建议。</div></div>
      <div class="toolbar-actions"><el-button :loading="loading" @click="loadMd"><el-icon><Refresh /></el-icon>刷新</el-button><el-button type="primary" :loading="exporting === 'pdf'" @click="exp('pdf')"><el-icon><Printer /></el-icon>PDF 预览</el-button></div>
    </div>

    <section class="report-types">
      <article><span><el-icon><DataAnalysis /></el-icon></span><div><b>学习成效摘要</b><p>前后测成绩、提升幅度与知识点变化。</p></div></article>
      <article><span><el-icon><Warning /></el-icon></span><div><b>薄弱点与错题</b><p>需要继续巩固的知识点和典型错因。</p></div></article>
      <article><span><el-icon><Guide /></el-icon></span><div><b>下一步计划</b><p>结合当前画像给出后续学习建议。</p></div></article>
    </section>

    <div class="card" v-if="loading"><el-skeleton :rows="8" animated /></div>
    <div v-else-if="error" class="page-state error"><div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>报告加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="loadMd">重新加载</el-button></div></div>
    <div class="card report-preview" v-else-if="md">
      <div class="toolbar preview-head"><div class="card-title"><el-icon><Document /></el-icon>报告预览</div><el-button :loading="exporting === 'md'" @click="exp('md')"><el-icon><Download /></el-icon>下载 Markdown</el-button></div>
      <MarkdownView :content="md" />
    </div>
    <div v-else class="page-state"><div><div class="state-icon"><el-icon><Document /></el-icon></div><h3>报告内容尚未生成</h3><p>完成前测、学习任务和后测后，系统会自动汇总个人学习报告。</p><el-button type="primary" @click="$router.push(`/student/pretest/${cid}`)">开始学习流程</el-button></div></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import MarkdownView from '@/components/MarkdownView.vue'
import { reports } from '@/api'

const route = useRoute()
const cid = computed(() => Number(route.params.cid || 0))
const md = ref('')
const loading = ref(false)
const error = ref('')
const exporting = ref<'md' | 'pdf' | ''>('')

async function loadMd() {
  loading.value = true
  error.value = ''
  try {
    const content = await reports.studentMd(cid.value)
    md.value = typeof content === 'string' ? content : String(content || '')
  } catch (err: any) {
    error.value = err?.message || '请稍后重新加载学习报告。'
  } finally {
    loading.value = false
  }
}

function openBlob(blob: Blob, filename: string, preview = false) {
  const url = URL.createObjectURL(blob)
  if (preview) {
    const popup = window.open(url, '_blank', 'noopener,noreferrer')
    if (popup) popup.opener = null
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
    return
  }
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

async function exp(type: 'md' | 'pdf') {
  exporting.value = type
  try {
    const file = await reports.studentFile(cid.value, type)
    openBlob(file, `student_report_${cid.value}.${type}`, type === 'pdf')
    ElMessage.success(type === 'pdf' ? '已打开打印预览' : '已开始下载')
  } catch (err: any) {
    ElMessage.error(err?.message || '报告导出失败')
  } finally {
    exporting.value = ''
  }
}
onMounted(loadMd)
</script>

<style scoped>
.report-types { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
.report-types article { display: grid; grid-template-columns: 42px 1fr; gap: 12px; padding: 16px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.report-types article > span { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 11px; color: var(--primary); background: var(--primary-bg); font-size: 18px; }
.report-types b { display: block; }.report-types p { margin-top: 3px; color: var(--text-secondary); font-size: 12px; }
.preview-head { margin-bottom: 18px; }.preview-head .card-title { margin: 0; }
.report-preview { padding: 28px 34px; }
@media (max-width: 820px) { .report-types { grid-template-columns: 1fr; }.report-preview { padding: 20px 16px; } }
</style>
