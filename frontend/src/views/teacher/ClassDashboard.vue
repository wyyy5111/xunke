<template>
  <div class="page">
    <div class="page-title">班级教学看板</div>
    <div class="page-desc">查看已完成测评学生的真实提升、班级薄弱点与资源审核进度。</div>

    <div v-if="loading" class="card"><el-skeleton :rows="6" animated /></div>
    <div v-else-if="error" class="page-state error"><div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>班级数据加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div></div>
    <template v-else-if="data">
      <div class="grid grid-4">
        <div class="stat-card">
          <div class="stat-label">学生人数</div>
          <div class="stat-value">{{ data.student_count }}</div>
          <div class="stat-icon"><el-icon><User /></el-icon></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">平均前测</div>
          <div class="stat-value text-warning">{{ data.pre_avg }}<span style="font-size:14px">分</span></div>
          <div class="stat-icon"><el-icon><EditPen /></el-icon></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">平均后测 · {{ data.post_completed_count || 0 }} 人完成</div>
          <div class="stat-value text-success">{{ data.post_avg }}<span style="font-size:14px">分</span></div>
          <div class="stat-icon"><el-icon><TrendCharts /></el-icon></div>
        </div>
        <div class="stat-card">
          <div class="stat-label">平均提升</div>
          <div class="stat-value" :class="data.improvement_avg >= 0 ? 'text-success' : 'text-danger'">{{ signed(data.improvement_avg) }}<span style="font-size:14px">分</span></div>
          <div class="stat-icon"><el-icon><DataLine /></el-icon></div>
        </div>
      </div>

      <div class="grid grid-2" style="margin-top:16px">
        <div class="card">
          <div class="card-title"><el-icon><Histogram /></el-icon> 薄弱知识点热力图</div>
          <v-chart :option="heatOption" style="height:340px" autoresize />
        </div>
        <div class="card">
          <div class="card-title"><el-icon><Trophy /></el-icon> 学生排行（按后测）</div>
          <el-table :data="data.ranking" size="small" max-height="340">
            <el-table-column type="index" label="排名" width="60" />
            <el-table-column prop="student_name" label="学生" width="110" />
            <el-table-column label="前测">
              <template #default="{ row }">{{ row.pre }} 分</template>
            </el-table-column>
            <el-table-column label="后测">
              <template #default="{ row }"><b v-if="row.completed" class="text-success">{{ row.post }} 分</b><span v-else class="muted">未完成</span></template>
            </el-table-column>
            <el-table-column label="提升">
              <template #default="{ row }"><span v-if="row.completed" :class="row.improvement >= 0 ? 'text-success' : 'text-danger'">{{ signed(row.improvement) }}</span><span v-else class="muted">—</span></template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <div class="card">
        <div class="card-title"><el-icon><Checked /></el-icon> 资源审核状态分布 + 班级报告导出</div>
        <div class="grid grid-2">
          <v-chart :option="reviewOption" style="height:280px" autoresize />
          <div class="export-box">
            <h3>导出班级教学分析报告</h3>
            <p class="muted">含班级整体、薄弱知识点、学生排行</p>
            <div style="display:flex; gap:10px">
              <el-button type="primary" :loading="exporting === 'md'" @click="exp('md')">Markdown</el-button>
              <el-button type="success" :loading="exporting === 'pdf'" @click="exp('pdf')">PDF</el-button>
            </div>
          </div>
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
import { reports, stats } from '@/api'
import { ElMessage } from 'element-plus'

use([CanvasRenderer, BarChart, PieChart, TooltipComponent, GridComponent, LegendComponent])

const route = useRoute()
const cid: any = computed(() => route.params.cid)
const loading = ref(true)
const error = ref('')
const exporting = ref<'md' | 'pdf' | ''>('')
const data = ref<any>(null)
const signed = (value: number) => `${Number(value) >= 0 ? '+' : ''}${Number(value || 0).toFixed(1)}`
const reviewText = (value: string) => ({ pending: '待审核', approved: '已通过', published: '已发布', risk: '需复核', rejected: '已退回' } as Record<string, string>)[value] || value

const heatOption = computed(() => ({
  tooltip: {},
  grid: { left: 80, right: 20, top: 20, bottom: 40 },
  xAxis: { type: 'value', name: '薄弱人数' },
  yAxis: { type: 'category', data: (data.value?.weak_heatmap || []).map((h: any) => h.name) },
  series: [{
    type: 'bar', data: (data.value?.weak_heatmap || []).map((h: any) => h.count),
    itemStyle: {
      color: (p: any) => {
        const v = p.value
        return v > 8 ? '#ef4444' : v > 5 ? '#f59e0b' : '#10b981'
      }
    },
    label: { show: true, position: 'right' }
  }]
}))
const reviewOption = computed(() => {
  const rs = data.value?.review_status || {}
  return {
    tooltip: { trigger: 'item' },
    legend: { top: 'bottom' },
    series: [{
      type: 'pie', radius: ['40%', '70%'],
      data: Object.entries(rs).map(([k, v]) => ({ name: reviewText(k), value: v }))
    }]
  }
})
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

async function exp(t: 'md' | 'pdf') {
  exporting.value = t
  try {
    const file = await reports.classFile(Number(cid.value), t)
    openBlob(file, `class_report_${cid.value}.${t}`, t === 'pdf')
    ElMessage.success(t === 'pdf' ? '已打开打印预览' : '已开始下载')
  } catch (err: any) {
    ElMessage.error(err?.message || '班级报告导出失败')
  } finally {
    exporting.value = ''
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try { data.value = await stats.teacher(cid.value) }
  catch (err: any) { error.value = err?.message || '请稍后重新加载班级数据。' }
  finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.export-box { display:flex; flex-direction:column; justify-content:center; align-items:flex-start; padding:20px; }
.export-box h3 { margin-bottom:8px; }
</style>
