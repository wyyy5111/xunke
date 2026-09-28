<template>
  <div class="page graph-page">
    <div class="page-header">
      <div>
        <div class="page-title">课程知识图谱</div>
        <div class="page-desc">按认知难度组织知识点，并展示先修、关联与易混关系。</div>
      </div>
      <el-button :loading="loading" @click="load"><el-icon><Refresh /></el-icon>刷新图谱</el-button>
    </div>

    <div v-if="loading" class="card"><el-skeleton :rows="9" animated /></div>
    <div v-else-if="error" class="page-state error">
      <div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>知识图谱加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div>
    </div>
    <div v-else-if="!nodes.length" class="page-state">
      <div><div class="state-icon"><el-icon><Share /></el-icon></div><h3>尚未形成知识图谱</h3><p>上传课程资料并完成知识点抽取后，系统会在这里建立关系网络。</p><el-button type="primary" @click="$router.push(`/teacher/knowledge/${cid}`)">管理知识点</el-button></div>
    </div>

    <template v-else>
      <section class="graph-summary">
        <div><span>知识节点</span><strong>{{ nodes.length }}</strong><small>来自当前课程资料</small></div>
        <div><span>关系数量</span><strong>{{ edges.length }}</strong><small>先修、关联与易混</small></div>
        <div><span>认知层级</span><strong>{{ categories.length }}</strong><small>从基础到高阶实践</small></div>
        <div><span>课程覆盖</span><strong>{{ coverage }}%</strong><small>已有关系的知识点占比</small></div>
      </section>

      <section class="graph-workspace">
        <div class="graph-canvas">
          <div class="graph-toolbar">
            <div><b>知识关系网络</b><span>拖动节点调整布局，滚轮缩放，点击查看相邻关系。</span></div>
            <div class="relation-legend"><span v-for="item in relationStats" :key="item.key"><i :style="{ background: item.color }"></i>{{ item.label }} {{ item.count }}</span></div>
          </div>
          <v-chart :option="option" style="height: 610px" autoresize />
        </div>

        <aside class="graph-inspector">
          <div><h2>认知分层</h2><p>颜色表示学习深度，不绑定任何特定专业术语。</p></div>
          <ul>
            <li v-for="(category, index) in categories" :key="category">
              <i :style="{ background: palette[index % palette.length] }"></i>
              <span><b>{{ category }}</b><small>{{ categoryCount(category) }} 个知识点</small></span>
            </li>
          </ul>
          <div class="graph-tip">
            <el-icon><InfoFilled /></el-icon>
            <p>先修关系用于规划学习顺序；关联关系用于扩展理解；易混关系用于生成辨析练习。</p>
          </div>
        </aside>
      </section>
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
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { kp } from '@/api'

use([CanvasRenderer, GraphChart, TooltipComponent, LegendComponent])

const route = useRoute()
const cid = computed(() => Number(route.params.cid || 0))
const nodes = ref<any[]>([])
const edges = ref<any[]>([])
const loading = ref(true)
const error = ref('')
const palette = ['#4f46e5', '#0891b2', '#7c3aed', '#d97706']

const categories = computed(() => Array.from(new Set(nodes.value.map((node) => node.category || '核心理解'))))
const coverage = computed(() => {
  const linked = new Set(edges.value.flatMap((edge) => [String(edge.source), String(edge.target)]))
  return nodes.value.length ? Math.round(linked.size / nodes.value.length * 100) : 0
})
const relationStats = computed(() => ['prerequisite', 'related', 'confusable'].map((key) => ({
  key,
  label: relationText(key),
  color: relationColor(key),
  count: edges.value.filter((edge) => normalizeRelation(edge.relation) === key).length
})))

const option = computed(() => ({
  animationDurationUpdate: 450,
  tooltip: {
    confine: true,
    formatter: (params: any) => params.dataType === 'edge'
      ? `${params.data.sourceName || '知识点'} → ${params.data.targetName || '知识点'}<br/>${params.data.value}`
      : `<b>${params.data.name}</b><br/>${params.data.categoryName}<br/>难度 ${params.data.difficulty}/5`
  },
  legend: [{
    top: 8,
    data: categories.value,
    textStyle: { color: '#667085', fontSize: 11 },
    itemWidth: 12,
    itemHeight: 8
  }],
  series: [{
    type: 'graph',
    layout: 'force',
    roam: true,
    draggable: true,
    force: { repulsion: 420, edgeLength: [105, 165], gravity: 0.08, friction: 0.55 },
    edgeSymbol: ['none', 'arrow'],
    edgeSymbolSize: 7,
    label: { show: true, position: 'right', color: '#273244', fontSize: 12, distance: 7 },
    categories: categories.value.map((name, index) => ({ name, itemStyle: { color: palette[index % palette.length] } })),
    data: nodes.value.map((node) => ({
      ...node,
      id: String(node.id),
      category: Math.max(0, categories.value.indexOf(node.category || '核心理解')),
      categoryName: node.category || '核心理解',
      symbolSize: 34 + Number(node.difficulty || 3) * 3,
      itemStyle: { borderColor: '#fff', borderWidth: 3, shadowBlur: 10, shadowColor: 'rgba(31,41,55,.12)' }
    })),
    links: edges.value.map((edge) => {
      const source = nodes.value.find((node) => String(node.id) === String(edge.source))
      const target = nodes.value.find((node) => String(node.id) === String(edge.target))
      return {
        source: String(edge.source),
        target: String(edge.target),
        sourceName: source?.name,
        targetName: target?.name,
        value: relationText(edge.relation),
        lineStyle: { color: relationColor(edge.relation), width: 1.8, opacity: 0.72, curveness: 0.08 }
      }
    }),
    emphasis: { focus: 'adjacency', scale: 1.12, lineStyle: { width: 3.5, opacity: 1 } }
  }]
}))

function normalizeRelation(value: string) {
  if (['similar', 'related', '关联', '相似'].includes(value)) return 'related'
  if (['confusion', 'confusable', '易混'].includes(value)) return 'confusable'
  return 'prerequisite'
}
function relationText(value: string) {
  return ({ prerequisite: '先修', related: '关联', confusable: '易混' } as Record<string, string>)[normalizeRelation(value)]
}
function relationColor(value: string) {
  return ({ prerequisite: '#4f46e5', related: '#0891b2', confusable: '#d97706' } as Record<string, string>)[normalizeRelation(value)]
}
function categoryCount(category: string) { return nodes.value.filter((node) => node.category === category).length }

async function load() {
  loading.value = true
  error.value = ''
  try {
    const graph: any = await kp.graph(cid.value)
    nodes.value = graph.nodes || []
    edges.value = graph.edges || []
  } catch (err: any) {
    error.value = err?.message || '请稍后重新加载知识图谱。'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.graph-page { max-width: 1520px; }
.graph-summary { display: grid; grid-template-columns: repeat(4, 1fr); overflow: hidden; margin-bottom: 14px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--border); box-shadow: var(--shadow-sm); gap: 1px; }
.graph-summary > div { padding: 17px 20px; background: #fff; }
.graph-summary span, .graph-summary strong, .graph-summary small { display: block; }
.graph-summary span { color: var(--text-secondary); font-size: 12px; }.graph-summary strong { margin: 3px 0; font-size: 25px; }.graph-summary small { color: var(--text-muted); }
.graph-workspace { display: grid; grid-template-columns: minmax(0, 1fr) 270px; gap: 14px; align-items: start; }
.graph-canvas, .graph-inspector { border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.graph-canvas { overflow: hidden; }.graph-toolbar { display: flex; justify-content: space-between; gap: 18px; padding: 17px 20px; border-bottom: 1px solid var(--border); }.graph-toolbar b, .graph-toolbar span { display: block; }.graph-toolbar > div:first-child span { margin-top: 3px; color: var(--text-secondary); font-size: 12px; }
.relation-legend { display: flex; align-items: center; justify-content: flex-end; gap: 12px; flex-wrap: wrap; }.relation-legend span { display: flex; align-items: center; gap: 5px; color: var(--text-secondary); font-size: 11px; }.relation-legend i { width: 8px; height: 8px; border-radius: 50%; }
.graph-inspector { padding: 20px; }.graph-inspector h2 { font-size: 16px; }.graph-inspector > div:first-child p { margin-top: 4px; color: var(--text-secondary); font-size: 12px; line-height: 1.6; }.graph-inspector ul { display: grid; gap: 4px; margin: 18px 0; padding: 0; list-style: none; }.graph-inspector li { display: grid; grid-template-columns: 10px 1fr; gap: 10px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--border-light); }.graph-inspector li > i { width: 9px; height: 9px; border-radius: 3px; }.graph-inspector li b, .graph-inspector li small { display: block; }.graph-inspector li small { margin-top: 2px; color: var(--text-muted); }
.graph-tip { display: grid; grid-template-columns: 20px 1fr; gap: 8px; padding: 12px; border-radius: 10px; color: var(--primary-dark); background: var(--primary-bg); }.graph-tip p { font-size: 12px; line-height: 1.65; }
@media (max-width: 1050px) { .graph-workspace { grid-template-columns: 1fr; }.graph-inspector ul { grid-template-columns: repeat(2, 1fr); }.graph-summary { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 620px) { .graph-summary { grid-template-columns: 1fr; }.graph-toolbar { flex-direction: column; }.relation-legend { justify-content: flex-start; }.graph-inspector ul { grid-template-columns: 1fr; } }
</style>
