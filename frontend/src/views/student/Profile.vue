<template>
  <div class="page">
    <div class="page-header">
      <div><div class="page-title">学习画像</div><div class="page-desc">基于前测表现和知识点掌握度形成的学习建议。</div></div>
      <el-button type="primary" @click="$router.push(`/student/path/${cid}`)">查看学习路径</el-button>
    </div>

    <div v-if="loading" class="card"><el-skeleton :rows="6" animated /></div>
    <div v-else-if="error" class="page-state error">
      <div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>学习画像加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div>
    </div>
    <template v-else-if="p">
      <div class="grid grid-4">
        <div class="stat-card"><div class="stat-label">基础水平</div><div class="stat-value">{{ levelText(p.base_level) }}</div><div class="stat-icon"><el-icon><DataAnalysis /></el-icon></div></div>
        <div class="stat-card"><div class="stat-label">前测成绩</div><div class="stat-value" :class="scoreColor(p.pre_score)">{{ p.pre_score }}<span class="unit">分</span></div><div class="stat-icon"><el-icon><EditPen /></el-icon></div></div>
        <div class="stat-card"><div class="stat-label">学习节奏</div><div class="stat-value text-success">{{ speedText(p.learning_speed) }}</div><div class="stat-icon"><el-icon><Timer /></el-icon></div></div>
        <div class="stat-card"><div class="stat-label">薄弱知识点</div><div class="stat-value text-danger">{{ p.weak_points?.length || 0 }}</div><div class="stat-icon"><el-icon><Aim /></el-icon></div></div>
      </div>

      <div class="grid grid-2" style="margin-top:16px">
        <div class="card">
          <div class="card-title"><el-icon><Aim /></el-icon> 知识点掌握度雷达图</div>
          <v-chart v-if="radarOption" :option="radarOption" style="height:340px" autoresize />
          <el-empty v-else description="暂无掌握度数据" />
        </div>
        <div class="card">
          <div class="card-title"><el-icon><Histogram /></el-icon> 掌握度详情</div>
          <div class="mastery-list">
            <div class="mastery-row" v-for="m in mastery" :key="m.kp_id">
              <span class="m-name">{{ m.name }}</span>
              <el-progress :percentage="Math.round(m.mastery_score)" :color="barColor(m.mastery_score)" style="flex:1" />
              <el-tag size="small" :type="statusType(m.status)">{{ statusText(m.status) }}</el-tag>
            </div>
          </div>
        </div>
      </div>

      <div class="grid grid-2" style="margin-top:16px">
        <div class="card">
          <div class="card-title"><el-icon><User /></el-icon> 学习偏好</div>
          <div class="pref-grid">
            <div class="pref-item"><span class="pref-label">学习风格</span><span class="pref-val">{{ p.pref_style }}</span></div>
            <div class="pref-item"><span class="pref-label">偏好形式</span><span class="pref-val">{{ p.pref_format }}</span></div>
            <div class="pref-item"><span class="pref-label">每周学时</span><span class="pref-val">{{ p.weekly_hours }} 小时</span></div>
            <div class="pref-item"><span class="pref-label">学习目标</span><span class="pref-val">{{ p.goal || '通过考试' }}</span></div>
          </div>
        </div>
        <div class="card">
          <div class="card-title"><el-icon><MagicStick /></el-icon> AI 推荐学习策略</div>
          <div class="recommend">{{ p.recommendation }}</div>
          <div class="rec-tags">
            <el-tag v-for="w in p.weak_points?.slice(0, 8)" :key="w.name" type="danger" effect="plain" size="small">{{ w.name }}</el-tag>
          </div>
        </div>
      </div>
    </template>
    <el-empty v-else description="尚未生成画像，请先完成前测">
      <el-button type="primary" @click="$router.push(`/student/pretest/${cid}`)">去前测</el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { RadarChart, BarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { profile as profileApi } from '@/api'

use([CanvasRenderer, RadarChart, BarChart, TooltipComponent, LegendComponent, GridComponent])

const route = useRoute()
const cid: any = computed(() => route.params.cid)
const loading = ref(true)
const error = ref('')
const p = ref<any>(null)
const mastery = ref<any[]>([])

const radarOption = computed(() => {
  if (!mastery.value.length) return null
  const top = mastery.value.slice(0, 8)
  return {
    tooltip: {},
    radar: {
      indicator: top.map(m => ({ name: m.name, max: 100 })),
      radius: '65%'
    },
    series: [{
      type: 'radar',
      data: [{
        value: top.map(m => m.mastery_score),
        name: '掌握度',
        areaStyle: { color: 'rgba(79,70,229,.18)' },
        lineStyle: { color: '#4f46e5' },
        itemStyle: { color: '#4f46e5' }
      }]
    }]
  }
})

const levelText = (l: string) => ({ basic: '基础', intermediate: '中等', advanced: '进阶' }[l] || l)
const speedText = (s: string) => ({ slow: '较慢', normal: '正常', fast: '较快' }[s] || s)
const statusText = (s: string) => ({ weak: '薄弱', consolidated: '待巩固', mastered: '已掌握' }[s] || s)
const statusType = (s: string) => ({ weak: 'danger', consolidated: 'warning', mastered: 'success' }[s] as any)
const barColor = (s: number) => s >= 80 ? '#10b981' : s >= 60 ? '#f59e0b' : '#ef4444'
const scoreColor = (s: number) => s >= 80 ? 'text-success' : s >= 60 ? 'text-warning' : 'text-danger'

async function load() {
  loading.value = true
  error.value = ''
  try {
    p.value = await profileApi.get(cid.value)
    mastery.value = await profileApi.mastery(cid.value)
  } catch (err: any) {
    if (err?.status === 404) p.value = null
    else error.value = err?.message || '请稍后重新加载学习画像。'
  } finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.mastery-list { max-height: 340px; overflow-y: auto; }
.mastery-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.m-name { width: 120px; font-size: 13px; flex-shrink: 0; }
.pref-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.pref-item { background: #f9fafb; border-radius: 10px; padding: 14px; }
.pref-label { display: block; font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; }
.pref-val { font-weight: 600; }
.recommend { background: var(--primary-bg); padding: 16px; border-radius: 10px; line-height: 1.8; color: var(--text); }
.rec-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.unit { margin-left: 3px; font-size: 14px; }
</style>
