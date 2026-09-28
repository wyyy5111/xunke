<template>
  <div class="page">
    <div class="page-header">
      <div><div class="page-title">知识导图</div><div class="page-desc">用结构化导图理解课程脉络，并查看知识点之间的先修关系。</div></div>
      <el-radio-group v-model="viewMode" size="small"><el-radio-button value="mindmap">思维导图</el-radio-button><el-radio-button value="graph">知识关系</el-radio-button></el-radio-group>
    </div>

    <div v-if="loading" class="card"><el-skeleton :rows="8" animated /></div>
    <div v-else-if="error" class="page-state error"><div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>知识导图加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div></div>

    <template v-else-if="viewMode === 'mindmap'">
      <div v-if="mindmaps.length" class="mindmap-layout">
        <aside><b>已发布导图</b><button v-for="item in mindmaps" :key="item.id" type="button" :class="{ active: currentMap?.id === item.id }" @click="currentMap = item"><el-icon><Share /></el-icon><span>{{ item.title }}</span></button></aside>
        <main><header><div><h2>{{ currentMap?.title }}</h2><p>质量 {{ Math.round(currentMap?.quality_score || 0) }} · {{ currentMap?.citations?.length || 0 }} 条课程引用 · 可横向拖动查看完整导图</p></div><el-tag type="success" effect="plain">已审核</el-tag></header><MarkdownView :content="currentMap?.content || ''" /></main>
      </div>
      <div v-else class="page-state"><div><div class="state-icon"><el-icon><Share /></el-icon></div><h3>暂无已发布思维导图</h3><p>教师发布导图资源后，会在这里以可交互结构展示。</p></div></div>
    </template>

    <template v-else>
      <div v-if="nodes.length" class="graph-layout">
        <section class="graph-panel"><v-chart :option="graphOption" style="height:560px" autoresize @click="onNodeClick" /></section>
        <aside class="node-panel"><h2>知识点详情</h2><template v-if="selected"><h3>{{ selected.name }}</h3><p>类别：{{ selected.category || '课程基础' }}</p><p>难度：{{ selected.difficulty || 3 }}/5</p><div class="toolbar-actions"><el-button size="small" @click="$router.push({ path: `/student/lecture/${cid}`, query: { kp_id: selected.id } })">查看讲义</el-button><el-button size="small" type="primary" @click="$router.push({ path: `/student/exercise/${cid}`, query: { kp_id: selected.id } })">开始练习</el-button></div></template><div v-else class="node-empty">点击图中的知识点查看详情。</div></aside>
      </div>
      <div v-else class="page-state"><div><div class="state-icon"><el-icon><Connection /></el-icon></div><h3>尚未建立知识关系</h3><p>教师完成知识点整理后，系统会展示先修、相似和易混关系。</p></div></div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import MarkdownView from '@/components/MarkdownView.vue'
import { kp, resource } from '@/api'
import { useUserStore } from '@/stores/user'

use([CanvasRenderer, GraphChart, TooltipComponent])
const route = useRoute()
const store = useUserStore()
const cid = computed(() => Number(route.params.cid))
const loading = ref(true)
const error = ref('')
const viewMode = ref('mindmap')
const mindmaps = ref<any[]>([])
const currentMap = ref<any>(null)
const nodes = ref<any[]>([])
const edges = ref<any[]>([])
const selected = ref<any>(null)
const graphCategories = computed(() => Array.from(new Set(nodes.value.map((node) => node.category || '核心理解'))))
const graphPalette = ['#4f46e5', '#0891b2', '#7c3aed', '#d97706']

const graphOption = computed(() => ({
  tooltip: { formatter: (params: any) => params.dataType === 'node' ? params.data.name : params.data.value || '知识关系' },
  series: [{
    type: 'graph', layout: 'force', roam: true,
    force: { repulsion: 250, edgeLength: [80, 130], gravity: .08 },
    label: { show: true, position: 'right', color: '#172033', fontSize: 12 },
    data: nodes.value.map((node) => ({
      ...node,
      id: String(node.id),
      symbolSize: 34 + Number(node.difficulty || 3) * 2,
      itemStyle: { color: graphPalette[Math.max(0, graphCategories.value.indexOf(node.category || '核心理解')) % graphPalette.length], borderColor: '#fff', borderWidth: 2 }
    })),
    links: edges.value.map((edge) => ({ source: String(edge.source), target: String(edge.target), value: relationText(edge.relation), lineStyle: { color: '#94a3b8', width: 1.8, opacity: .78, curveness: .08 } })),
    emphasis: { focus: 'adjacency', lineStyle: { width: 3 } }
  }]
}))

const relationText = (value: string) => ({ prerequisite: '先修', similar: '相似', confusion: '易混', 相似: '相似', 易混: '易混' }[value] || value)
function onNodeClick(params: any) { if (params.dataType === 'node') selected.value = params.data }

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [maps, graph] = await Promise.all([resource.list({ course_id: cid.value, rtype: 'mindmap' }), kp.graph(cid.value)])
    mindmaps.value = maps.filter((item) => (!item.is_personalized || Number(item.student_id) === Number(store.user?.id)) && (item.published || ['approved', 'published'].includes(item.review_status)))
    currentMap.value = mindmaps.value[0] || null
    nodes.value = graph.nodes || []
    edges.value = graph.edges || []
    if (!mindmaps.value.length && nodes.value.length) viewMode.value = 'graph'
  } catch (err: any) {
    error.value = err?.message || '请稍后重新加载知识导图。'
  } finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.mindmap-layout, .graph-layout { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 14px; align-items: start; }
.mindmap-layout > aside, .mindmap-layout > main, .graph-panel, .node-panel { border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.mindmap-layout > aside { position: sticky; top: 14px; overflow: hidden; }.mindmap-layout > aside > b { display: block; padding: 15px; border-bottom: 1px solid var(--border); }.mindmap-layout > aside button { width: 100%; display: flex; align-items: center; gap: 9px; padding: 12px 15px; border: 0; border-bottom: 1px solid var(--border-light); background: #fff; color: var(--text); text-align: left; cursor: pointer; }.mindmap-layout > aside button.active { color: var(--primary); background: var(--primary-bg); box-shadow: inset 3px 0 var(--primary); }.mindmap-layout > main { min-height: 620px; padding: 24px; }.mindmap-layout > main > header { display: flex; justify-content: space-between; gap: 15px; margin-bottom: 18px; padding-bottom: 15px; border-bottom: 1px solid var(--border); }.mindmap-layout h2 { font-size: 19px; }.mindmap-layout header p { color: var(--text-secondary); font-size: 12px; }
.mindmap-layout :deep(.mermaid-chart) { overscroll-behavior-x: contain; scrollbar-gutter: stable; cursor: grab; }
.mindmap-layout :deep(.mermaid-chart:active) { cursor: grabbing; }
.mindmap-layout :deep(.mermaid-chart svg) { width: auto !important; min-width: 960px; max-width: none !important; }
.graph-layout { grid-template-columns: minmax(0, 1fr) 280px; }.graph-panel { overflow: hidden; }.node-panel { padding: 20px; }.node-panel h2 { margin-bottom: 18px; font-size: 16px; }.node-panel h3 { font-size: 18px; }.node-panel p { margin-top: 8px; color: var(--text-secondary); }.node-panel .toolbar-actions { margin-top: 18px; }.node-empty { padding: 30px 8px; color: var(--text-muted); text-align: center; }
@media (max-width: 860px) { .mindmap-layout, .graph-layout { grid-template-columns: 1fr; }.mindmap-layout > aside { position: static; } }
</style>
