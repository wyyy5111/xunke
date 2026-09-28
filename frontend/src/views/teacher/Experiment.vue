<template>
  <div class="page">
    <div class="page-title">实验评测与对比 · {{ cid }}</div>
    <div class="page-desc">RAG vs 无 RAG、多 Agent vs 单 Agent、有质量校验 vs 无、个性化 vs 通用</div>

    <div v-if="loading" class="card"><el-skeleton :rows="6" animated /></div>
    <div v-else-if="error" class="page-state error"><div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>评测数据加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div></div>
    <template v-else-if="data">
      <div class="grid grid-4">
        <div class="stat-card"><div class="stat-label">课程引用命中率</div><div class="stat-value text-success">{{ data.rag_vs_no_rag.with_rag_citation_hit }}<span class="unit">%</span></div><div class="stat-icon"><el-icon><Aim /></el-icon></div></div>
        <div class="stat-card"><div class="stat-label">协作执行步骤</div><div class="stat-value">{{ data.multi_vs_single_agent.multi_agent_steps }}</div><div class="stat-icon"><el-icon><Connection /></el-icon></div></div>
        <div class="stat-card"><div class="stat-label">平均质量评分</div><div class="stat-value text-success">{{ data.quality_check.with_check_avg_score }}</div><div class="stat-icon"><el-icon><Checked /></el-icon></div></div>
        <div class="stat-card"><div class="stat-label">智能生成调用</div><div class="stat-value">{{ data.llm_calls }}</div><div class="stat-icon"><el-icon><DataLine /></el-icon></div></div>
      </div>

      <div class="grid grid-2" style="margin-top:16px">
        <div class="card">
          <div class="card-title"><el-icon><DataAnalysis /></el-icon> RAG vs 无 RAG（引用命中率）</div>
          <v-chart :option="ragOption" style="height:300px" autoresize />
          <p class="muted note">{{ data.rag_vs_no_rag.note }}</p>
        </div>
        <div class="card">
          <div class="card-title"><el-icon><Cpu /></el-icon> 多 Agent vs 单 Agent（步数）</div>
          <v-chart :option="agentOption" style="height:300px" autoresize />
          <p class="muted note">{{ data.multi_vs_single_agent.note }}</p>
        </div>
      </div>

      <div class="grid grid-2" style="margin-top:16px">
        <div class="card">
          <div class="card-title"><el-icon><Checked /></el-icon> 个性化 vs 通用资源</div>
          <v-chart :option="persOption" style="height:300px" autoresize />
        </div>
        <div class="card">
          <div class="card-title"><el-icon><TrendCharts /></el-icon> 已校验资源质量</div>
          <v-chart :option="qualityOption" style="height:300px" autoresize />
          <p class="muted note">{{ data.quality_check.note }}</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { stats } from '@/api'

use([CanvasRenderer, BarChart, PieChart, TooltipComponent, GridComponent, LegendComponent])
const route = useRoute()
const cid: any = computed(() => route.params.cid)
const loading = ref(true)
const error = ref('')
const data = ref<any>(null)

const ragOption = computed(() => ({
  tooltip: {}, grid: { left: 40, right: 20, top: 30, bottom: 30 },
  xAxis: { type: 'category', data: ['无 RAG', 'RAG 增强'] },
  yAxis: { type: 'value', max: 100, name: '命中率%' },
  series: [{ type: 'bar', barWidth: 50, data: [
    { value: data.value?.rag_vs_no_rag.no_rag_citation_hit || 0, itemStyle: { color: '#ef4444' } },
    { value: data.value?.rag_vs_no_rag.with_rag_citation_hit || 0, itemStyle: { color: '#10b981' } }
  ], label: { show: true, position: 'top', formatter: '{c}%' } }]
}))
const agentOption = computed(() => ({
  tooltip: {}, grid: { left: 40, right: 20, top: 30, bottom: 30 },
  xAxis: { type: 'category', data: ['单 Agent', '多 Agent 协同'] },
  yAxis: { type: 'value', name: '步数' },
  series: [{ type: 'bar', barWidth: 50, data: [
    { value: data.value?.multi_vs_single_agent.single_agent_steps || 0, itemStyle: { color: '#94a3b8' } },
    { value: data.value?.multi_vs_single_agent.multi_agent_steps || 0, itemStyle: { color: '#6366f1' } }
  ], label: { show: true, position: 'top' } }]
}))
const persOption = computed(() => ({
  tooltip: { trigger: 'item' }, legend: { bottom: 0 },
  series: [{ type: 'pie', radius: ['40%','70%'], data: [
    { name: '个性化', value: data.value?.personalized.personalized_count || 0, itemStyle: { color: '#ec4899' } },
    { name: '通用', value: data.value?.personalized.general_count || 0, itemStyle: { color: '#94a3b8' } }
  ] }]
}))
const qualityOption = computed(() => ({
  tooltip: {}, grid: { left: 40, right: 20, top: 30, bottom: 30 },
  xAxis: { type: 'category', data: ['已开启质量校验'] },
  yAxis: { type: 'value', max: 100 },
  series: [{ type: 'bar', barWidth: 50, data: [
    { value: data.value?.quality_check.with_check_avg_score || 0, itemStyle: { color: '#0f8a72' } }
  ], label: { show: true, position: 'top' } }]
}))

async function load() {
  loading.value = true
  error.value = ''
  try { data.value = await stats.experiment(cid.value) }
  catch (err: any) { error.value = err?.message || '请稍后重新加载评测数据。' }
  finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.note { font-size: 12px; margin-top: 8px; line-height: 1.6; }
.unit { margin-left:3px; font-size:13px; }
</style>
