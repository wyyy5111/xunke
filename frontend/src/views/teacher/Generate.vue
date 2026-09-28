<template>
  <div class="page">
    <div class="page-title">课程资源生成中心</div>
    <div class="page-desc">基于课程资料与学生画像生成讲义、练习、导图和课堂资源，并进入教师审核流程。</div>

    <div class="grid" style="grid-template-columns: 280px 1fr; gap:16px">
      <div class="card">
        <div class="card-title"><el-icon><MagicStick /></el-icon> 生成配置</div>
        <el-form label-position="top">
          <el-form-item label="资源类型">
            <el-select v-model="rtype" style="width:100%">
              <el-option v-for="r in types" :key="r.v" :label="r.l" :value="r.v" />
            </el-select>
          </el-form-item>
          <el-form-item label="关联知识点">
            <el-select v-model="kpId" clearable style="width:100%">
              <el-option v-for="k in kps" :key="k.id" :label="k.name" :value="k.id" />
            </el-select>
          </el-form-item>
          <el-button type="primary" style="width:100%" :loading="gen" @click="generate">
            <el-icon><Cpu /></el-icon> 启动生成
          </el-button>
        </el-form>

        <el-divider>一键全流程</el-divider>
        <el-button type="success" style="width:100%" :loading="fullLoading" @click="runFull">
          <el-icon><Connection /></el-icon> 运行完整流水线
        </el-button>
        <p class="muted" style="margin-top:10px; font-size:12px">将依次执行 10 个智能体，可在 Agent 日志页查看。</p>
      </div>

      <div class="card">
        <div class="card-title"><el-icon><FolderOpened /></el-icon> 生成结果（{{ list.length }}）</div>
        <div v-if="error" class="page-state error"><div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>资源加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div></div>
        <div v-else-if="list.length" class="res-grid">
          <div class="res-card" v-for="r in list" :key="r.id" @click="preview(r)">
            <div class="rc-head">
              <span class="rc-type" :style="{background: typeBg(r.rtype)}">{{ typeIcon(r.rtype) }}</span>
              <span class="rc-title">{{ r.title }}</span>
            </div>
            <div class="rc-meta">
              <el-rate :model-value="r.quality_score / 20" disabled size="small" />
              <span>{{ Math.round(r.quality_score) }}分</span>
              <el-tag size="small" :type="statusType(r.review_status)">{{ statusText(r.review_status) }}</el-tag>
              <span v-if="r.is_personalized" class="pers-badge">个性化</span>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无生成资源，选择左侧类型后启动生成" />
      </div>
    </div>

    <el-drawer v-model="drawer" size="55%" :title="cur?.title">
      <div v-if="cur" style="padding:0 16px">
        <div class="cur-meta">
          <el-tag size="small" :type="statusType(cur.review_status)">{{ statusText(cur.review_status) }}</el-tag>
          <el-tag size="small" type="warning">质量 {{ Math.round(cur.quality_score) }}</el-tag>
          <el-button size="small" @click="goReview">去审核</el-button>
        </div>
        <MarkdownView :content="previewContent" />
        <div v-if="cur.citations?.length" style="margin-top:14px">
          <div class="card-title">引用溯源（{{ cur.citations.length }}）</div>
          <div class="cite-item" v-for="c in cur.citations" :key="c.id">
            <b>[{{ c.id }}]</b> {{ c.source_file_name || c.source }} P{{ c.page_number || c.page || 1 }}
            <span class="muted">命中 {{ (Number(c.relevance_score ?? c.score ?? 0) * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { IS_SHOWCASE } from '@/config/runtime'
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import MarkdownView from '@/components/MarkdownView.vue'
import { resource, kp as kpApi, agent } from '@/api'
import { formatResourcePreview } from '@/utils/resourcePreview'

const route = useRoute()
const router = useRouter()
const cid: any = computed(() => route.params.cid)
const types = [
  { v: 'lecture', l: '讲义' }, { v: 'mindmap', l: '思维导图' },
  { v: 'exercise', l: '练习题' }, { v: 'experiment', l: '实验任务' },
  { v: 'reading', l: '拓展阅读' }, { v: 'ppt', l: 'PPT 大纲' },
  { v: 'video', l: '视频脚本' }, { v: 'wrong_review', l: '错题复盘' },
]
const rtype = ref('lecture')
const kpId = ref<number | null>(null)
const kps = ref<any[]>([])
const list = ref<any[]>([])
const gen = ref(false)
const fullLoading = ref(false)
const drawer = ref(false)
const cur = ref<any>(null)
const error = ref('')
const previewContent = computed(() => formatResourcePreview(cur.value))

const typeIcon = (t: string) => ({ lecture: '讲', mindmap: '图', exercise: '练', experiment: '实', reading: '读', ppt: '课', video: '视', wrong_review: '复' } as any)[t] || '资'
const typeBg = (_type?: string) => 'var(--primary-bg)'
const statusText = (s: string) => ({ pending: '待审核', approved: '已通过', rejected: '已退回', risk: '高风险', published: '已发布' }[s] || s)
const statusType = (s: string) => ({ pending: 'info', approved: 'success', rejected: 'danger', risk: 'warning', published: 'success' }[s] as any)

async function load() {
  error.value = ''
  try {
    ;[kps.value, list.value] = await Promise.all([kpApi.list(cid.value), resource.list({ course_id: cid.value })])
  } catch (err: any) {
    error.value = err?.message || '请稍后重新加载资源。'
  }
}
async function generate() {
  gen.value = true
  try {
    const res: any = await resource.generate({ course_id: cid.value, rtype: rtype.value, kp_id: kpId.value })
    ElMessage.success(res?.status === 'failed' ? '生成未完成，请查看失败原因' : '资源已生成并进入教师审核')
    await load()
  } catch (err: any) {
    if (!(IS_SHOWCASE && err?.status === 405)) error.value = err?.message || '资源生成失败，请重试。'
  } finally { gen.value = false }
}
async function runFull() {
  fullLoading.value = true
  try {
    await agent.run({ course_id: cid.value, workflow: 'full_pipeline' })
    ElMessage.success('完整课程任务已提交，可在智能协作流程中查看实时进度')
    await load()
    router.push('/teacher/agents')
  } catch (err: any) {
    if (!(IS_SHOWCASE && err?.status === 405)) error.value = err?.message || '完整任务执行失败，请重试。'
  } finally { fullLoading.value = false }
}
function preview(r: any) { cur.value = r; drawer.value = true }
function goReview() { drawer.value = false; router.push(`/teacher/review/${cid.value}`) }

onMounted(load)
</script>

<style scoped>
.res-grid { display:grid; grid-template-columns: repeat(3,1fr); gap:10px; }
.res-card { background:#f9fafb; border-radius:10px; padding:12px; cursor:pointer; transition:all .2s; }
.res-card:hover { background:#ede9fe; transform:translateY(-2px); }
.rc-head { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
.rc-type { width:32px; height:32px; border-radius:8px; display:flex; align-items:center; justify-content:center; color:var(--primary); font-size:12px; font-weight:800; }
.rc-title { font-size:13px; font-weight:600; flex:1; }
.rc-meta { display:flex; align-items:center; gap:6px; flex-wrap:wrap; font-size:12px; }
.pers-badge { background:#fce7f3; color:#be185d; padding:1px 6px; border-radius:8px; font-size:11px; }
.cur-meta { display:flex; gap:8px; align-items:center; margin-bottom:14px; }
.cite-item { background:#f9fafb; padding:8px; border-radius:6px; margin-bottom:6px; font-size:13px; }
@media (max-width: 1180px) {
  .res-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
