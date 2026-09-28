<template>
  <div class="page review-page">
    <div class="page-header">
      <div>
        <div class="page-title">资源审核</div>
        <div class="page-desc">核对正文、课程引用与质量指标，修订后再发布给学生。</div>
      </div>
      <div class="toolbar-actions">
        <el-radio-group v-model="filter" size="small">
          <el-radio-button value="pending">待处理</el-radio-button>
          <el-radio-button value="all">全部资源</el-radio-button>
        </el-radio-group>
        <el-button :loading="loading" @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>

    <div v-if="loading" class="card"><el-skeleton :rows="10" animated /></div>
    <div v-else-if="error" class="page-state error">
      <div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>审核队列加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div>
    </div>
    <div v-else-if="!filtered.length" class="page-state">
      <div><div class="state-icon"><el-icon><Checked /></el-icon></div><h3>{{ filter === 'pending' ? '待审核资源已处理完毕' : '当前课程暂无生成资源' }}</h3><p>新的生成内容会自动进入审核队列，并附带引用和质量信息。</p></div>
    </div>

    <div v-else class="review-workspace">
      <aside class="resource-queue">
        <header><b>{{ filter === 'pending' ? '待处理队列' : '全部资源' }}</b><span>{{ filtered.length }} 项</span></header>
        <button
          v-for="item in filtered"
          :key="item.id"
          type="button"
          class="queue-item"
          :class="{ active: current?.id === item.id }"
          @click="selectResource(item)"
        >
          <span class="type-mark"><el-icon><Document /></el-icon></span>
          <span class="queue-copy"><b>{{ item.title }}</b><small>{{ resourceType(item.rtype) }} · 质量 {{ Math.round(item.quality_score || 0) }}</small></span>
          <el-tag size="small" :type="statusType(item.review_status)" effect="plain">{{ statusText(item.review_status) }}</el-tag>
        </button>
      </aside>

      <main v-if="current" class="review-editor">
        <header class="editor-head">
          <div><span>{{ resourceType(current.rtype) }}</span><h1>{{ current.title }}</h1></div>
          <div class="tag-row"><el-tag :type="statusType(current.review_status)">{{ statusText(current.review_status) }}</el-tag><el-tag effect="plain">质量 {{ Math.round(current.quality_score || 0) }}</el-tag></div>
        </header>

        <el-tabs v-model="activeTab">
          <el-tab-pane label="正文预览" name="preview"><MarkdownView :content="previewContent" /></el-tab-pane>
          <el-tab-pane label="修订正文" name="edit" :disabled="current.published"><el-input v-model="draftContent" type="textarea" :rows="26" resize="vertical" /></el-tab-pane>
        </el-tabs>

        <footer class="review-actions">
          <el-input v-if="!current.published" v-model="comment" placeholder="填写审核意见，便于保留审核依据" />
          <p v-else class="published-note">该资源正在对学生发布。如需修订，请先取消发布。</p>
          <div class="toolbar-actions">
            <template v-if="current.published">
              <el-button type="warning" plain :loading="submitting" @click="unpublishResource">取消发布</el-button>
            </template>
            <template v-else>
              <el-button type="danger" plain :loading="submitting" @click="submitDecision('risk')">标记风险</el-button>
              <el-button :loading="submitting" @click="submitDecision('needs_edit')">保存修订并退回</el-button>
              <el-button type="primary" :loading="submitting" @click="approveAndPublish">通过并发布</el-button>
            </template>
          </div>
        </footer>
      </main>

      <aside v-if="current" class="review-context">
        <section>
          <h2><el-icon><DataAnalysis /></el-icon>质量指标</h2>
          <div class="quality-overview"><strong>{{ Math.round(current.quality_score || 0) }}</strong><span>综合质量</span></div>
          <div class="metric-list">
            <div v-for="metric in qualityMetrics" :key="metric.name"><span>{{ metric.name }}</span><b>{{ metric.value }}{{ metric.unit }}</b></div>
          </div>
        </section>

        <section>
          <h2><el-icon><User /></el-icon>系统预审建议</h2>
          <div v-if="reviewSuggestion" class="suggestion">
            <p>{{ reviewSuggestion.summary }}</p>
            <div v-if="reviewSuggestion.checklist.length" class="suggestion-group">
              <b>建议核对</b>
              <ul><li v-for="item in reviewSuggestion.checklist" :key="item">{{ item }}</li></ul>
            </div>
            <div v-if="reviewSuggestion.revisions.length" class="suggestion-group">
              <b>修订建议</b>
              <ul><li v-for="item in reviewSuggestion.revisions" :key="item">{{ item }}</li></ul>
            </div>
          </div>
          <div v-else class="suggestion-empty">
            <b>暂无针对该资源的系统预审建议</b>
            <span>直接生成的资源可能只完成质量评分；运行完整智能体流水线后会补充审核要点。</span>
          </div>
        </section>

        <section>
          <h2><el-icon><Link /></el-icon>课程引用（{{ current.citations?.length || 0 }}）</h2>
          <div v-if="current.citations?.length" class="citation-list">
            <article v-for="(citation, index) in current.citations" :key="index">
              <header><b>[{{ index + 1 }}] {{ citationSource(citation) }}</b><span>{{ citationScore(citation.relevance_score ?? citation.score) }}</span></header>
              <small>第 {{ citation.page_number ?? citation.page ?? 1 }} 页<span v-if="citation.chapter"> · {{ citation.chapter }}</span></small>
              <p>{{ cleanSnippet(citation.excerpt ?? citation.snippet) || '该来源用于支撑正文内容。' }}</p>
            </article>
          </div>
          <p v-else class="context-empty">当前资源没有可核验的引用，建议谨慎发布。</p>
        </section>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownView from '@/components/MarkdownView.vue'
import { resource, review } from '@/api'
import { formatResourcePreview } from '@/utils/resourcePreview'

const route = useRoute()
const cid = computed(() => Number(route.params.cid))
const loading = ref(true)
const submitting = ref(false)
const error = ref('')
const all = ref<any[]>([])
const current = ref<any>(null)
const filter = ref('pending')
const activeTab = ref('preview')
const draftContent = ref('')
const comment = ref('')

const filtered = computed(() => filter.value === 'pending' ? all.value.filter((item) => ['pending', 'risk'].includes(item.review_status)) : all.value)
const previewContent = computed(() => formatResourcePreview(current.value, draftContent.value))
const qualityMetrics = computed(() => [
  { name: '内容质量', value: Math.round(current.value?.quality_score || 0), unit: '分' },
  { name: '课程引用', value: current.value?.citations?.length || 0, unit: '条' },
  { name: '审核状态', value: statusText(current.value?.review_status || 'pending'), unit: '' },
])
const reviewSuggestion = computed(() => {
  const suggestion = current.value?.extra?.teacher_review_suggestion
  if (!suggestion || typeof suggestion !== 'object') return null
  const summary = String(suggestion.summary || '').trim()
  const checklist = stringList(suggestion.checklist)
  const revisions = stringList(suggestion.revision_suggestions)
  if (!summary && !checklist.length && !revisions.length) return null
  return {
    summary: summary || '系统已完成预审，请结合以下要点人工复核。',
    checklist,
    revisions,
  }
})
const cleanSnippet = (value: string) => String(value || '')
  .replace(/#{1,6}\s*/g, '')
  .replace(/```[\s\S]*?```/g, ' ')
  .replace(/[>*_`|]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim()
  .slice(0, 220)

const resourceType = (type: string) => ({ lecture: '讲义', mindmap: '思维导图', exercise: '练习', experiment: '实验任务', reading: '拓展阅读', ppt: '课件大纲', video: '视频脚本', wrong_review: '错题复盘', remedial: '补救资源' }[type] || type)
const statusText = (status: string) => ({ pending: '待审核', approved: '已通过', rejected: '已退回', needs_edit: '待修改', risk: '需关注', published: '已发布' }[status] || status)
const statusType = (status: string) => ({ pending: 'info', approved: 'success', rejected: 'danger', needs_edit: 'warning', risk: 'warning', published: 'success' }[status] as any)
const citationScore = (score: number) => `${Math.round(Number(score || 0) * (Number(score || 0) <= 1 ? 100 : 1))}%`
const citationSource = (citation: any) => citation.source_file_name || citation.source || '课程资料'
const stringList = (value: unknown) => Array.isArray(value)
  ? value.map((item) => String(item || '').trim()).filter(Boolean).slice(0, 6)
  : []

function selectResource(item: any) {
  current.value = item
  draftContent.value = item.content || ''
  comment.value = ''
  activeTab.value = 'preview'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    all.value = await resource.list({ course_id: cid.value })
    const next = filtered.value.find((item) => item.id === current.value?.id) || filtered.value[0] || all.value[0] || null
    if (next) selectResource(next)
    else current.value = null
  } catch (err: any) {
    error.value = err?.message || '请稍后重新加载审核队列。'
  } finally {
    loading.value = false
  }
}

async function submitDecision(decision: string) {
  if (!current.value) return
  if (decision === 'risk' && !comment.value.trim()) return ElMessage.warning('请填写风险原因')
  submitting.value = true
  try {
    await review.decide(current.value.id, {
      decision,
      comment: comment.value.trim(),
      revised_content: draftContent.value !== current.value.content ? draftContent.value : ''
    })
    ElMessage.success(decision === 'needs_edit' ? '修订内容已保存并退回' : '审核状态已更新')
    await load()
  } catch (err: any) {
    ElMessage.error(err?.message || '审核提交失败')
  } finally {
    submitting.value = false
  }
}

async function approveAndPublish() {
  if (!current.value) return
  if (!current.value.citations?.length) {
    try { await ElMessageBox.confirm('该资源没有可展示的课程引用，仍要发布吗？', '发布确认', { type: 'warning' }) } catch { return }
  }
  submitting.value = true
  try {
    if (draftContent.value !== current.value.content) {
      await review.decide(current.value.id, { decision: 'needs_edit', comment: '教师修订后发布', revised_content: draftContent.value })
    }
    await review.decide(current.value.id, { decision: 'approved', comment: comment.value.trim() || '教师审核通过', revised_content: '' })
    await review.publish(current.value.id)
    ElMessage.success('资源已通过审核并发布给学生')
    await load()
  } catch (err: any) {
    ElMessage.error(err?.message || '发布失败')
  } finally {
    submitting.value = false
  }
}

async function unpublishResource() {
  if (!current.value) return
  try {
    await ElMessageBox.confirm('取消发布后，学生将无法继续打开该资源；审核修订记录会保留。', '取消发布', { type: 'warning' })
  } catch { return }
  submitting.value = true
  try {
    await review.unpublish(current.value.id)
    ElMessage.success('资源已取消发布，可修改后重新发布')
    await load()
  } catch (err: any) {
    ElMessage.error(err?.message || '取消发布失败')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
watch(filter, () => {
  const next = filtered.value[0] || null
  if (next) selectResource(next)
  else current.value = null
})
</script>

<style scoped>
.review-workspace { display: grid; grid-template-columns: 260px minmax(0, 1fr) 300px; gap: 14px; align-items: start; }
.resource-queue, .review-editor, .review-context { border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.resource-queue { position: sticky; top: 14px; overflow: hidden; }
.resource-queue > header { display: flex; justify-content: space-between; padding: 16px; border-bottom: 1px solid var(--border); }
.resource-queue > header span { color: var(--text-muted); font-size: 12px; }
.queue-item { width: 100%; display: grid; grid-template-columns: 34px minmax(0, 1fr) auto; gap: 9px; align-items: center; padding: 12px 14px; border: 0; border-bottom: 1px solid var(--border-light); background: #fff; color: var(--text); text-align: left; cursor: pointer; }
.queue-item:hover { background: #fafaff; }
.queue-item.active { background: var(--primary-bg); box-shadow: inset 3px 0 var(--primary); }
.type-mark { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 9px; color: var(--primary); background: #f3f4ff; }
.queue-copy { min-width: 0; }
.queue-copy b, .queue-copy small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.queue-copy small { color: var(--text-muted); }
.review-editor { min-height: 720px; padding: 24px 28px; }
.editor-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 10px; }
.editor-head span { color: var(--primary); font-size: 11px; font-weight: 800; letter-spacing: .08em; }
.editor-head h1 { margin-top: 4px; font-size: 23px; }
.review-actions { position: sticky; bottom: 10px; display: grid; gap: 10px; margin-top: 24px; padding: 14px; border: 1px solid var(--border); border-radius: 12px; background: rgba(255,255,255,.95); box-shadow: var(--shadow); backdrop-filter: blur(12px); }
.review-actions .toolbar-actions { justify-content: flex-end; }
.published-note { margin: 0; color: var(--text-secondary); font-size: 12px; }
.review-context { position: sticky; top: 14px; padding: 18px; }
.review-context section + section { margin-top: 20px; padding-top: 18px; border-top: 1px solid var(--border); }
.review-context h2 { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; font-size: 14px; }
.review-context h2 .el-icon { color: var(--primary); }
.quality-overview { display: flex; align-items: baseline; margin-bottom: 12px; }
.quality-overview strong { font-size: 34px; line-height: 1; }
.quality-overview span { margin-left: 7px; color: var(--text-muted); }
.metric-list { display: grid; gap: 7px; }
.metric-list div { display: flex; justify-content: space-between; gap: 10px; padding: 8px 10px; border-radius: 8px; background: var(--bg-secondary); font-size: 12px; }
.suggestion, .context-empty, .suggestion-empty { padding: 12px; border-radius: 9px; background: var(--primary-bg); color: var(--text-secondary); font-size: 12px; line-height: 1.7; }
.suggestion p { margin: 0; }
.suggestion-group { margin-top: 10px; padding-top: 9px; border-top: 1px solid rgba(79,70,229,.12); }
.suggestion-group b { color: var(--text); }
.suggestion-group ul { margin: 5px 0 0; padding-left: 18px; }
.suggestion-empty { display: grid; gap: 4px; background: var(--bg-secondary); }
.suggestion-empty b { color: var(--text); }
.citation-list { display: grid; gap: 8px; }
.citation-list article { padding: 10px; border: 1px solid var(--border); border-radius: 9px; background: #fbfcfe; }
.citation-list header { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; }
.citation-list header span { color: var(--success); font-weight: 700; }
.citation-list small { color: var(--text-muted); }
.citation-list p { margin-top: 5px; color: var(--text-secondary); font-size: 12px; line-height: 1.55; }
@media (max-width: 1240px) { .review-workspace { grid-template-columns: 240px minmax(0, 1fr); } .review-context { position: static; grid-column: 1 / -1; display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; } .review-context section + section { margin: 0; padding: 0; border: 0; } }
@media (max-width: 820px) { .review-workspace { grid-template-columns: 1fr; } .resource-queue, .review-context { position: static; } .review-editor { min-height: auto; padding: 20px 16px; } .review-context { grid-template-columns: 1fr; } .editor-head { flex-direction: column; } }
</style>
