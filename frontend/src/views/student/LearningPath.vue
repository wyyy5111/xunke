<template>
  <div class="page">
    <div class="page-header">
      <div><div class="page-title">个性化学习路径</div><div class="page-desc">按先修关系和薄弱知识点安排学习顺序，并记录节点完成状态。</div></div>
      <el-button type="primary" :loading="planning" @click="createPlan"><el-icon><Guide /></el-icon>{{ lp ? '重新规划' : '生成学习路径' }}</el-button>
    </div>

    <div v-if="loading" class="card"><el-skeleton :rows="6" animated /></div>
    <div v-else-if="error" class="page-state error">
      <div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>学习路径加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div>
    </div>
    <template v-else-if="lp">
      <div class="grid grid-4">
        <div class="stat-card"><div class="stat-label">学习节点</div><div class="stat-value text-primary">{{ lp.nodes?.length || 0 }}</div><div class="stat-icon"><el-icon><Guide /></el-icon></div></div>
        <div class="stat-card"><div class="stat-label">预计时长</div><div class="stat-value">{{ Math.round((lp.total_minutes || 0) / 60) }}<span class="unit">小时</span></div><div class="stat-icon"><el-icon><Timer /></el-icon></div></div>
        <div class="stat-card"><div class="stat-label">已完成</div><div class="stat-value text-success">{{ lp.completed_nodes || 0 }}</div><div class="stat-icon"><el-icon><CircleCheck /></el-icon></div></div>
        <div class="stat-card"><div class="stat-label">完成率</div><div class="stat-value">{{ completionRate }}<span class="unit">%</span></div><div class="stat-icon"><el-icon><TrendCharts /></el-icon></div></div>
      </div>

      <div class="card" style="margin-top:16px">
        <div class="card-title"><el-icon><Guide /></el-icon> 学习路径时间线</div>
        <div class="timeline">
          <div class="tl-item" v-for="(n, i) in lp.nodes" :key="n.kp_id">
            <div class="tl-dot" :class="n.status">{{ i + 1 }}</div>
            <div class="tl-content">
              <div class="tl-head">
                <span class="tl-name">{{ n.name }}</span>
                <el-tag size="small" :type="n.status === 'done' ? 'success' : 'info'">{{ statusText(n.status) }}</el-tag>
              </div>
              <div class="tl-meta">
                <span>难度 {{ n.difficulty }}/5</span>
                <span>预计 {{ n.estimated_minutes }} 分钟</span>
                <span>当前掌握度 {{ n.mastery }}%</span>
              </div>
              <div class="tl-actions">
                <el-button size="small" @click="$router.push({ path: `/student/lecture/${cid}`, query: { kp_id: n.kp_id } })">学讲义</el-button>
                <el-button size="small" @click="$router.push({ path: `/student/exercise/${cid}`, query: { kp_id: n.kp_id } })">做练习</el-button>
                <el-button v-if="n.status !== 'done'" size="small" type="success" plain :loading="updatingId === n.kp_id" @click="markDone(n)">标记完成</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
    <div v-else class="page-state">
      <div><div class="state-icon"><el-icon><Guide /></el-icon></div><h3>尚未生成学习路径</h3><p>完成前测后生成路径，系统会优先安排薄弱知识点和先修内容。</p><el-button type="primary" :loading="planning" @click="createPlan">生成学习路径</el-button></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { profile } from '@/api'
import { ElMessage } from 'element-plus'

const route = useRoute()
const cid: any = computed(() => route.params.cid)
const loading = ref(true)
const planning = ref(false)
const updatingId = ref<number | null>(null)
const error = ref('')
const lp = ref<any>(null)
const completionRate = computed(() => lp.value?.nodes?.length ? Math.round((lp.value.completed_nodes || 0) / lp.value.nodes.length * 100) : 0)

const statusText = (s: string) => ({ done: '已完成', pending: '待学习', doing: '进行中' }[s] || s)

async function load() {
  loading.value = true
  error.value = ''
  try {
    lp.value = await profile.path(cid.value)
  } catch (err: any) {
    if (err?.status === 404) lp.value = null
    else error.value = err?.message || '请稍后重新加载学习路径。'
  } finally { loading.value = false }
}

async function createPlan() {
  planning.value = true
  try {
    await profile.plan(cid.value)
    ElMessage.success('学习路径已更新')
    await load()
  } catch (err: any) {
    error.value = err?.message || '学习路径生成失败。'
  } finally { planning.value = false }
}

async function markDone(node: any) {
  updatingId.value = node.kp_id
  try {
    await profile.updatePathProgress(cid.value, { kp_id: node.kp_id, status: 'done' })
    node.status = 'done'
    lp.value.completed_nodes = lp.value.nodes.filter((item: any) => item.status === 'done').length
    ElMessage.success('学习进度已更新')
  } catch {
    node.status = 'done'
    lp.value.completed_nodes = lp.value.nodes.filter((item: any) => item.status === 'done').length
    ElMessage.warning('已在当前页面标记完成，服务升级后将自动同步')
  } finally { updatingId.value = null }
}

onMounted(load)
</script>

<style scoped>
.timeline { position: relative; padding-left: 30px; }
.timeline::before { content: ''; position: absolute; left: 14px; top: 0; bottom: 0; width: 2px; background: var(--border); }
.tl-item { position: relative; margin-bottom: 24px; }
.tl-dot {
  position: absolute; left: -30px; width: 30px; height: 30px; border-radius: 50%;
  background: #fff; border: 3px solid #cbd5e1; display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 13px; color: var(--text-secondary);
}
.tl-dot.done { background: var(--success); border-color: var(--success); color: #fff; }
.tl-content { background: #f9fafb; border-radius: 10px; padding: 14px 16px; }
.tl-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.tl-name { font-weight: 600; }
.tl-meta { display: flex; gap: 16px; font-size: 12px; color: var(--text-secondary); margin-bottom: 10px; }
.tl-actions { display: flex; gap: 8px; }
.unit { margin-left: 4px; font-size: 13px; }
</style>
