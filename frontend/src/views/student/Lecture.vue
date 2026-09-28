<template>
  <div class="page lecture-page">
    <div class="page-header">
      <div>
        <div class="page-title">个性化讲义</div>
        <div class="page-desc">只展示已通过教师审核的课程讲义，并保留课程资料引用。</div>
      </div>
      <el-button type="primary" :loading="generating" @click="generateLecture">
        <el-icon><MagicStick /></el-icon>申请生成新讲义
      </el-button>
    </div>

    <el-alert v-if="store.demoMode" type="warning" :closable="false" show-icon class="mode-alert">
      当前为演示模式，内容由本地演示服务生成；配置在线智能服务后可切换为实时生成。
    </el-alert>
    <el-alert v-else-if="generationNotice" type="warning" :closable="false" show-icon class="mode-alert">
      {{ generationNotice }}
    </el-alert>

    <div v-if="loading" class="card"><el-skeleton :rows="10" animated /></div>

    <div v-else-if="error" class="page-state error">
      <div>
        <div class="state-icon"><el-icon><WarningFilled /></el-icon></div>
        <h3>讲义加载失败</h3>
        <p>{{ error }}</p>
        <el-button type="primary" @click="load">重新加载</el-button>
      </div>
    </div>

    <div v-else-if="!lectures.length" class="page-state">
      <div>
        <div class="state-icon"><el-icon><Document /></el-icon></div>
        <h3>暂无已发布讲义</h3>
        <p v-if="pendingCount">你有 {{ pendingCount }} 份讲义正在等待教师审核，通过后会出现在这里。</p>
        <p v-else>可以申请生成一份适配当前学习画像的讲义，生成后由教师审核发布。</p>
        <el-button type="primary" :loading="generating" @click="generateLecture">申请生成</el-button>
      </div>
    </div>

    <div v-else class="lecture-workspace">
      <aside class="lecture-list">
        <div class="panel-heading">
          <div>
            <b>已发布讲义</b>
            <span>{{ lectures.length }} 份</span>
          </div>
          <el-button text circle aria-label="刷新讲义" @click="load"><el-icon><Refresh /></el-icon></el-button>
        </div>
        <button
          v-for="item in lectures"
          :key="item.id"
          type="button"
          class="lecture-item"
          :class="{ active: current?.id === item.id }"
          @click="current = item"
        >
          <span class="item-mark"><el-icon><Document /></el-icon></span>
          <span>
            <b>{{ item.title }}</b>
            <small>{{ item.is_personalized ? '为你生成' : '课程通用' }} · 质量 {{ Math.round(item.quality_score || 0) }}</small>
          </span>
        </button>
        <div v-if="pendingCount" class="pending-note">
          <el-icon><Clock /></el-icon>{{ pendingCount }} 份内容等待审核
        </div>
      </aside>

      <main v-if="current" class="lecture-content">
        <header class="content-head">
          <div>
            <span class="content-kicker">{{ current.is_personalized ? '个性化学习内容' : '课程核心内容' }}</span>
            <h1>{{ current.title }}</h1>
          </div>
          <div class="tag-row">
            <el-tag type="success" effect="plain">已审核</el-tag>
            <el-tag effect="plain">质量 {{ Math.round(current.quality_score || 0) }}</el-tag>
          </div>
        </header>
        <MarkdownView :content="current.content" />
      </main>

      <aside v-if="current" class="lecture-context">
        <section>
          <div class="context-title"><el-icon><Checked /></el-icon>内容质量</div>
          <div class="quality-score">
            <strong>{{ Math.round(current.quality_score || 0) }}</strong><span>/ 100</span>
          </div>
          <el-progress :percentage="Math.round(current.quality_score || 0)" :show-text="false" :stroke-width="8" />
        </section>

        <section>
          <div class="context-title"><el-icon><Link /></el-icon>资料引用</div>
          <div v-if="current.citations?.length" class="citation-list">
            <article v-for="(citation, index) in current.citations" :key="`${citation.source}-${index}`" class="citation-item">
              <header><b>[{{ index + 1 }}] {{ citation.source }}</b><span>{{ scoreText(citation.score) }}</span></header>
              <small>第 {{ citation.page || 1 }} 页</small>
              <p>{{ cleanSnippet(citation.snippet) || '该引用用于支撑讲义中的核心概念。' }}</p>
            </article>
          </div>
          <div v-else class="context-empty">该讲义暂未返回可展示的引用片段。</div>
        </section>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import MarkdownView from '@/components/MarkdownView.vue'
import { resource } from '@/api'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const store = useUserStore()
const cid = computed(() => Number(route.params.cid))
const userId = computed(() => Number(store.user?.id || 0))
const loading = ref(true)
const generating = ref(false)
const error = ref('')
const generationNotice = ref('')
const lectures = ref<any[]>([])
const pendingCount = ref(0)
const current = ref<any>(null)

const scoreText = (score: number) => `${Math.round(Number(score || 0) * (Number(score || 0) <= 1 ? 100 : 1))}%`
const cleanSnippet = (value: string) => String(value || '')
  .replace(/#{1,6}\s*/g, '')
  .replace(/```[\s\S]*?```/g, ' ')
  .replace(/[>*_`|]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim()
  .slice(0, 220)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const rows = await resource.list({ course_id: cid.value, rtype: 'lecture' })
    const mineOrGeneral = rows.filter((row) => !row.is_personalized || Number(row.student_id) === userId.value)
    lectures.value = mineOrGeneral.filter((row) => row.published || ['approved', 'published'].includes(row.review_status))
    pendingCount.value = mineOrGeneral.filter((row) => Number(row.student_id) === userId.value && !row.published && ['pending', 'risk'].includes(row.review_status)).length
    if (!current.value || !lectures.value.some((item) => item.id === current.value.id)) current.value = lectures.value[0] || null
  } catch (err: any) {
    error.value = err?.message || '请稍后重新加载讲义。'
  } finally {
    loading.value = false
  }
}

async function generateLecture() {
  generating.value = true
  generationNotice.value = ''
  try {
    const response = await resource.generate({ course_id: cid.value, rtype: 'lecture', personalized: true })
    if (response?.status === 'failed') throw new Error('生成任务未完成，请稍后重试。')
    const summary = response?.summary || {}
    if (response?.fallback || response?.demo_mode || response?.degraded || summary?.fallback_used) {
      generationNotice.value = '在线生成暂时不可用，本次已使用演示模式结果。'
    }
    ElMessage.success('讲义已生成并提交教师审核')
    await load()
  } catch (err: any) {
    error.value = err?.message || '讲义生成失败，请重试。'
  } finally {
    generating.value = false
  }
}

onMounted(async () => {
  await store.checkDemo()
  await load()
})
</script>

<style scoped>
.mode-alert { margin-bottom: 16px; }
.lecture-workspace { display: grid; grid-template-columns: 250px minmax(0, 1fr) 292px; gap: 14px; align-items: start; }
.lecture-list, .lecture-content, .lecture-context { border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.lecture-list { position: sticky; top: 14px; overflow: hidden; }
.panel-heading { display: flex; align-items: center; justify-content: space-between; padding: 16px; border-bottom: 1px solid var(--border); }
.panel-heading b, .panel-heading span { display: block; }
.panel-heading span { color: var(--text-muted); font-size: 11px; }
.lecture-item { width: 100%; display: grid; grid-template-columns: 34px 1fr; gap: 10px; padding: 13px 15px; border: 0; border-bottom: 1px solid var(--border-light); background: #fff; color: var(--text); text-align: left; cursor: pointer; }
.lecture-item:hover { background: #fafaff; }
.lecture-item.active { background: var(--primary-bg); box-shadow: inset 3px 0 var(--primary); }
.item-mark { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 9px; color: var(--primary); background: #f3f4ff; }
.lecture-item b { display: block; line-height: 1.5; }
.lecture-item small { display: block; margin-top: 3px; color: var(--text-muted); }
.pending-note { display: flex; align-items: center; gap: 7px; margin: 12px; padding: 10px; border-radius: 9px; color: var(--warning); background: var(--warning-bg); font-size: 12px; }
.lecture-content { min-height: 700px; padding: 28px 32px 42px; }
.content-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-bottom: 24px; padding-bottom: 18px; border-bottom: 1px solid var(--border); }
.content-kicker { color: var(--primary); font-size: 11px; font-weight: 800; letter-spacing: .08em; }
.content-head h1 { margin-top: 5px; font-size: 25px; }
.lecture-context { position: sticky; top: 14px; padding: 18px; }
.lecture-context section + section { margin-top: 22px; padding-top: 20px; border-top: 1px solid var(--border); }
.context-title { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; font-weight: 700; }
.context-title .el-icon { color: var(--primary); }
.quality-score { display: flex; align-items: baseline; margin-bottom: 8px; }
.quality-score strong { font-size: 34px; line-height: 1; }
.quality-score span { margin-left: 4px; color: var(--text-muted); }
.citation-list { display: grid; gap: 9px; }
.citation-item { padding: 11px; border: 1px solid var(--border); border-radius: 10px; background: #fbfcfe; }
.citation-item header { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; }
.citation-item header span { color: var(--success); font-weight: 700; }
.citation-item small { color: var(--text-muted); }
.citation-item p { margin-top: 6px; color: var(--text-secondary); font-size: 12px; line-height: 1.6; }
.context-empty { padding: 14px; border-radius: 9px; background: var(--bg-secondary); color: var(--text-secondary); font-size: 12px; }
@media (max-width: 1180px) { .lecture-workspace { grid-template-columns: 220px minmax(0, 1fr); } .lecture-context { position: static; grid-column: 1 / -1; display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; } .lecture-context section + section { margin: 0; padding: 0; border: 0; } }
@media (max-width: 780px) { .lecture-workspace { grid-template-columns: 1fr; } .lecture-list, .lecture-context { position: static; } .lecture-content { min-height: auto; padding: 22px 18px; } .content-head, .lecture-context { grid-template-columns: 1fr; flex-direction: column; } }
</style>
