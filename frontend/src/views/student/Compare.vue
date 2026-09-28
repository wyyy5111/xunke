<template>
  <div class="page">
    <div class="page-header"><div><div class="page-title">前后测对比</div><div class="page-desc">从总分和知识点两个层面查看学习变化。</div></div><el-button @click="$router.push(`/student/report/${cid}`)">查看学习报告</el-button></div>

    <div v-if="loading" class="card"><el-skeleton :rows="6" animated /></div>
    <div v-else-if="error" class="page-state error"><div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>对比数据加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div></div>
    <template v-else-if="hasAssessment">
      <div class="grid grid-4">
        <div class="stat-card"><div class="stat-label">前测成绩</div><div class="stat-value text-warning">{{ data.pre_score }}<span class="unit">分</span></div><div class="stat-icon"><el-icon><EditPen /></el-icon></div></div>
        <div class="stat-card"><div class="stat-label">后测成绩</div><div class="stat-value text-success">{{ data.post_score }}<span class="unit">分</span></div><div class="stat-icon"><el-icon><CircleCheck /></el-icon></div></div>
        <div class="stat-card"><div class="stat-label">成绩变化</div><div class="stat-value" :class="data.improvement >= 0 ? 'text-success' : 'text-danger'">{{ signed(data.improvement) }}<span class="unit">分</span></div><div class="stat-icon"><el-icon><TrendCharts /></el-icon></div></div>
        <div class="stat-card"><div class="stat-label">提升率</div><div class="stat-value" :class="improvementRate >= 0 ? 'text-success' : 'text-danger'">{{ signed(improvementRate) }}%</div><div class="stat-icon"><el-icon><DataAnalysis /></el-icon></div></div>
      </div>

      <div class="grid grid-2" style="margin-top:16px">
        <div class="card">
          <div class="card-title"><el-icon><DataAnalysis /></el-icon> 总分对比</div>
          <v-chart :option="barOption" style="height:300px" autoresize />
        </div>
        <div class="card">
          <div class="card-title"><el-icon><TrendCharts /></el-icon> 按知识点提升</div>
          <v-chart :option="kpOption" :style="{ height: `${kpChartHeight}px` }" autoresize />
          <el-alert
            v-if="pendingKpCount"
            class="coverage-note"
            type="info"
            :closable="false"
            :title="`本次后测覆盖 ${assessedKps.length} 个知识点，另有 ${pendingKpCount} 个知识点待专项复测。`"
          />
        </div>
      </div>

      <div class="card">
        <div class="card-title"><el-icon><Document /></el-icon> 学习效果小结</div>
        <el-alert :type="data.improvement >= 0 ? 'success' : 'warning'" :closable="false">
          经过系统学习，你的成绩从 <b>{{ data.pre_score }}</b> 分提升到 <b>{{ data.post_score }}</b> 分，
          提升 <b>{{ data.improvement }}</b> 分（{{ improvementRate }}%）。
          {{ data.improvement >= 15 ? '效果显著，继续加油！' : data.improvement >= 0 ? '稳步提升，建议针对性补强薄弱点。' : '出现退步，建议复习补救资源。' }}
        </el-alert>
        <div class="actions">
          <el-button @click="$router.push(`/student/report/${cid}`)">导出学习报告</el-button>
          <el-button type="primary" @click="$router.push(`/student/wrong/${cid}`)">查看错题补救</el-button>
        </div>
      </div>
    </template>
    <div v-else class="page-state"><div><div class="state-icon"><el-icon><TrendCharts /></el-icon></div><h3>尚未形成前后测对比</h3><p>完成前测和后测后，系统会展示总分与知识点维度的变化。</p><el-button type="primary" @click="$router.push(`/student/posttest/${cid}`)">去完成后测</el-button></div></div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { test } from '@/api'

use([CanvasRenderer, BarChart, TooltipComponent, GridComponent, LegendComponent])

const route = useRoute()
const cid: any = route.params.cid
const loading = ref(true)
const error = ref('')
const data = ref<any>(null)

const improvementRate = computed(() => data.value?.pre_score ? Math.round(data.value.improvement / data.value.pre_score * 100) : 0)
const hasAssessment = computed(() => !!data.value && Number(data.value.pre_score) > 0 && Number(data.value.post_score) > 0)
const assessedKps = computed(() => (data.value?.by_kp || []).filter((item: any) => item.assessed !== false && item.post != null))
const pendingKpCount = computed(() => Number(data.value?.pending_kp_count ?? Math.max(0, (data.value?.by_kp || []).length - assessedKps.value.length)))
const kpChartHeight = computed(() => Math.max(300, assessedKps.value.length * 32 + 68))
const signed = (value: number) => `${Number(value) >= 0 ? '+' : ''}${Number(value || 0)}`
const barOption = computed(() => ({
  tooltip: {}, legend: { data: ['成绩'] }, grid: { left: 40, right: 20, top: 40, bottom: 30 },
  xAxis: { type: 'category', data: ['前测', '后测'] },
  yAxis: { type: 'value', max: 100 },
  series: [{
    name: '成绩', type: 'bar', data: [
      { value: data.value?.pre_score || 0, itemStyle: { color: '#f59e0b' } },
      { value: data.value?.post_score || 0, itemStyle: { color: '#10b981' } }
    ],
    barWidth: 60, label: { show: true, position: 'top', formatter: '{c}分' }
  }]
}))
const kpOption = computed(() => ({
  tooltip: { trigger: 'axis' }, legend: { data: ['前测', '后测'] },
  grid: { left: 172, right: 24, top: 42, bottom: 26 },
  xAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' }, splitLine: { lineStyle: { color: '#edf0f5' } } },
  yAxis: {
    type: 'category',
    inverse: true,
    data: assessedKps.value.map((k: any) => k.name || `知识点 ${k.kp_id}`),
    axisTick: { show: false },
    axisLabel: { width: 150, overflow: 'truncate', color: '#526078', fontSize: 11 }
  },
  series: [
    { name: '前测', type: 'bar', data: assessedKps.value.map((k: any) => k.pre), barMaxWidth: 12, itemStyle: { color: '#f59e0b', borderRadius: [0, 4, 4, 0] } },
    { name: '后测', type: 'bar', data: assessedKps.value.map((k: any) => k.post), barMaxWidth: 12, itemStyle: { color: '#10b981', borderRadius: [0, 4, 4, 0] } }
  ]
}))

async function load() {
  loading.value = true
  error.value = ''
  try { data.value = await test.compare(cid) }
  catch (err: any) { error.value = err?.message || '请稍后重新加载对比数据。' }
  finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.actions { display:flex; gap:10px; margin-top:14px; }
.unit { margin-left: 3px; font-size: 13px; }
.coverage-note { margin-top: 10px; }
</style>
