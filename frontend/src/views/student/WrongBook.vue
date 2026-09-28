<template>
  <div class="page">
    <div class="page-header">
      <div><div class="page-title">错题复盘与补救</div><div class="page-desc">定位错因、回看课程证据，并生成需要教师审核的个性化补救内容。</div></div>
      <el-button type="primary" :loading="generating" @click="genRemedial"><el-icon><FirstAidKit /></el-icon>生成复盘与补救资源</el-button>
    </div>

    <el-alert v-if="error" type="error" :closable="false" show-icon style="margin-bottom:16px">{{ error }} <el-button text @click="load">重新加载</el-button></el-alert>

    <div class="grid grid-4">
      <div class="stat-card"><div class="stat-label">错题总数</div><div class="stat-value text-danger">{{ list.length }}</div><div class="stat-icon"><el-icon><Warning /></el-icon></div></div>
      <div class="stat-card"><div class="stat-label">主要错因</div><div class="stat-value compact-value">{{ topReason }}</div><div class="stat-icon"><el-icon><Search /></el-icon></div></div>
      <div class="stat-card"><div class="stat-label">薄弱知识点</div><div class="stat-value text-warning">{{ weakKps }}</div><div class="stat-icon"><el-icon><Aim /></el-icon></div></div>
      <div class="stat-card"><div class="stat-label">补救资源</div><div class="stat-value text-success compact-value">{{ remedial ? '已发布' : pendingGenerated ? '待审核' : '待生成' }}</div><div class="stat-icon"><el-icon><TrendCharts /></el-icon></div></div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-title"><el-icon><Warning /></el-icon> 错题列表</div>
      <el-alert v-if="pendingGenerated && !remedial" type="warning" :closable="false" show-icon style="margin-bottom:14px">复盘与补救资源已生成并提交教师审核，通过后将在这里展示正文。</el-alert>
      <div v-if="remedial" class="card" style="background:#fef3c7; margin-bottom:14px">
        <div class="card-title"><el-icon><FirstAidKit /></el-icon>错题补救包</div>
        <MarkdownView :content="remedial" />
      </div>
      <div v-for="w in list" :key="w.id" class="wrong-card">
        <div class="w-head">
          <el-tag size="small">{{ typeText(w.qtype) }}</el-tag>
          <span class="muted">难度 {{ w.difficulty }}/5</span>
          <el-tag size="small" type="danger">{{ w.reason }}</el-tag>
          <span class="muted" style="margin-left:auto">{{ fmt(w.created_at) }}</span>
        </div>
        <div class="w-stem">{{ w.stem }}</div>
        <div class="w-ans">
          <div><span class="lbl">你的答案：</span><b class="text-danger">{{ w.your || '未作答' }}</b></div>
          <div><span class="lbl">正确答案：</span><b class="text-success">{{ w.correct }}</b></div>
        </div>
        <div class="w-ana"><b>解析：</b>{{ w.analysis }}</div>
        <div class="w-actions">
          <el-button size="small" type="success" @click="resolve(w.id)">已掌握</el-button>
        </div>
      </div>
      <el-empty v-if="!list.length" description="暂无错题，继续保持！" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import MarkdownView from '@/components/MarkdownView.vue'
import { wrong, resource } from '@/api'

const route = useRoute()
const cid: any = route.params.cid
const list = ref<any[]>([])
const remedial = ref('')
const pendingGenerated = ref(false)
const generating = ref(false)
const error = ref('')

const typeText = (t: string) => ({ single: '单选', multiple: '多选', judge: '判断', fill: '填空', short: '简答' }[t] || t)
const fmt = (s: string) => s ? new Date(s).toLocaleString('zh-CN', { hour12: false }) : ''
const topReason = computed(() => {
  const m: any = {}
  list.value.forEach(w => { m[w.reason] = (m[w.reason] || 0) + 1 })
  return Object.entries(m).sort((a: any, b: any) => b[1] - a[1])[0]?.[0] || '-'
})
const weakKps = computed(() => new Set(list.value.map(w => w.kp_id)).size)

async function load() {
  error.value = ''
  try {
    const [wrongs, reviews, remedials] = await Promise.all([
      wrong.list(cid),
      resource.list({ course_id: cid, rtype: 'wrong_review' }),
      resource.list({ course_id: cid, rtype: 'remedial' })
    ])
    list.value = wrongs
    const published = [...reviews, ...remedials].sort((a: any, b: any) => Number(b.id) - Number(a.id))
    remedial.value = published.map((item: any) => item.content).filter(Boolean).join('\n\n---\n\n')
  }
  catch (err: any) { error.value = err?.message || '错题加载失败，请重试。' }
}
async function resolve(id: number) {
  await wrong.resolve(id)
  ElMessage.success('已标记为掌握')
  await load()
}
async function genRemedial() {
  generating.value = true
  error.value = ''
  try {
    await resource.generate({ course_id: cid, rtype: 'wrong_review' })
    await resource.generate({ course_id: cid, rtype: 'remedial' })
    pendingGenerated.value = true
    ElMessage.success('错题复盘与补救资源已生成，并提交教师审核')
  } catch (err: any) { error.value = err?.message || '补救资源生成失败，请重试。' } finally { generating.value = false }
}
onMounted(load)
</script>

<style scoped>
.wrong-card { border: 1px solid var(--border); border-radius: 10px; padding: 14px; margin-bottom: 12px; }
.w-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.w-stem { font-weight: 600; margin-bottom: 8px; }
.w-ans { display: flex; gap: 20px; margin-bottom: 6px; }
.lbl { color: var(--text-secondary); font-size: 13px; }
.w-ana { font-size: 13px; line-height: 1.7; padding: 8px; background: #f9fafb; border-radius: 6px; }
.w-actions { margin-top: 8px; }
.compact-value { font-size:18px !important; }
</style>
