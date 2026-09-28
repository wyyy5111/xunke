<template>
  <div class="page">
    <div class="page-header">
      <div>
        <div class="page-title">题库管理</div>
        <div class="page-desc">维护可用于前测、后测和分层练习的结构化题目。</div>
      </div>
      <el-button type="primary" @click="openEditor()"><el-icon><Plus /></el-icon>新增题目</el-button>
    </div>

    <div v-if="loading" class="card"><el-skeleton :rows="7" animated /></div>
    <div v-else-if="error" class="page-state error">
      <div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>题库加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div>
    </div>
    <div v-else class="card">
      <div class="toolbar table-toolbar">
        <div class="card-title"><el-icon><Tickets /></el-icon>题目列表（{{ list.length }}）</div>
        <el-select v-model="typeFilter" placeholder="全部题型" clearable style="width: 150px">
          <el-option v-for="type in questionTypes" :key="type.value" :label="type.label" :value="type.value" />
        </el-select>
      </div>
      <el-table :data="filtered" size="small" stripe>
        <el-table-column label="题型" width="88"><template #default="{ row }"><el-tag size="small" effect="plain">{{ typeText(row.qtype) }}</el-tag></template></el-table-column>
        <el-table-column prop="stem" label="题干" min-width="280" show-overflow-tooltip />
        <el-table-column label="选项" min-width="220" show-overflow-tooltip><template #default="{ row }">{{ optionSummary(row) }}</template></el-table-column>
        <el-table-column prop="answer" label="答案" width="100" show-overflow-tooltip />
        <el-table-column label="难度" width="130"><template #default="{ row }"><el-rate :model-value="row.difficulty" disabled size="small" /></template></el-table-column>
        <el-table-column prop="source" label="来源" width="90" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEditor(row)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="remove(row.id)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无题目，可以创建第一道题" /></template>
      </el-table>
    </div>

    <el-dialog v-model="dialogOpen" :title="form.id ? '编辑题目' : '新增题目'" width="min(760px, 94vw)" destroy-on-close>
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="题型">
            <el-select v-model="form.qtype" @change="normalizeOptions">
              <el-option v-for="type in questionTypes" :key="type.value" :label="type.label" :value="type.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="关联知识点">
            <el-select v-model="form.kp_id" clearable placeholder="可选">
              <el-option v-for="item in kps" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="题干"><el-input v-model="form.stem" type="textarea" :rows="3" placeholder="输入清晰、无歧义的题干" /></el-form-item>

        <el-form-item v-if="isChoice" label="选项与正确答案">
          <div class="option-editor">
            <div v-for="(option, index) in form.options" :key="option.key" class="option-row">
              <el-radio v-if="form.qtype === 'single'" v-model="singleCorrect" :value="option.key" aria-label="设为正确答案" />
              <el-checkbox v-else v-model="option.is_correct" aria-label="设为正确答案" />
              <span class="option-key">{{ option.key }}</span>
              <el-input v-model="option.content" :placeholder="`选项 ${option.key}`" />
              <el-button text type="danger" :disabled="form.options.length <= 2" @click="removeOption(index)"><el-icon><Delete /></el-icon></el-button>
            </div>
            <el-button plain :disabled="form.options.length >= 8" @click="addOption"><el-icon><Plus /></el-icon>增加选项</el-button>
          </div>
        </el-form-item>

        <el-form-item v-else label="参考答案"><el-input v-model="form.answer" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="答案解析"><el-input v-model="form.analysis" type="textarea" :rows="3" placeholder="说明正确答案依据，并提示常见误区" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="难度"><el-slider v-model="form.difficulty" :min="1" :max="5" show-stops /></el-form-item>
          <el-form-item label="标签"><el-input v-model="form.tags" placeholder="例如：核心概念,易错" /></el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存题目</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ApiError } from '@/api/request'
import { kp, question } from '@/api'

const route = useRoute()
const cid = computed(() => Number(route.params.cid))
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const list = ref<any[]>([])
const kps = ref<any[]>([])
const typeFilter = ref('')
const dialogOpen = ref(false)

const questionTypes = [
  { value: 'single', label: '单选题' },
  { value: 'multiple', label: '多选题' },
  { value: 'judge', label: '判断题' },
  { value: 'fill', label: '填空题' },
  { value: 'short', label: '简答题' }
]

const blankForm = () => ({ id: null as number | null, qtype: 'single', stem: '', answer: '', analysis: '', difficulty: 3, kp_id: null as number | null, tags: '', options: defaultOptions() })
const form = ref(blankForm())
const filtered = computed(() => typeFilter.value ? list.value.filter((row) => row.qtype === typeFilter.value) : list.value)
const isChoice = computed(() => ['single', 'multiple'].includes(form.value.qtype))
const singleCorrect = computed({
  get: () => form.value.options.find((option: any) => option.is_correct)?.key || '',
  set: (key: string) => form.value.options.forEach((option: any) => { option.is_correct = option.key === key })
})

const typeText = (type: string) => questionTypes.find((item) => item.value === type)?.label || type
const optionSummary = (row: any) => row.options?.length ? row.options.map((option: any) => `${option.key}.${option.content}`).join('  ') : '—'

function defaultOptions() {
  return ['A', 'B', 'C', 'D'].map((key, index) => ({ key, content: '', is_correct: index === 0, order_index: index }))
}

function normalizeOptions() {
  if (isChoice.value && form.value.options.length < 2) form.value.options = defaultOptions()
  if (form.value.qtype === 'single' && !form.value.options.some((item: any) => item.is_correct)) form.value.options[0].is_correct = true
}

function openEditor(row?: any) {
  form.value = row
    ? {
        id: row.id,
        qtype: row.qtype,
        stem: row.stem,
        answer: row.answer || '',
        analysis: row.analysis || '',
        difficulty: row.difficulty || 3,
        kp_id: row.kp_id || null,
        tags: row.tags || '',
        options: (row.options || []).map((option: any, index: number) => ({ ...option, order_index: index }))
      }
    : blankForm()
  normalizeOptions()
  dialogOpen.value = true
}

function addOption() {
  const key = String.fromCharCode(65 + form.value.options.length)
  form.value.options.push({ key, content: '', is_correct: false, order_index: form.value.options.length })
}

function removeOption(index: number) {
  form.value.options.splice(index, 1)
  form.value.options.forEach((option: any, idx: number) => { option.key = String.fromCharCode(65 + idx); option.order_index = idx })
  normalizeOptions()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    ;[list.value, kps.value] = await Promise.all([question.list({ course_id: cid.value }), kp.list(cid.value)])
  } catch (err: any) {
    error.value = err?.message || '请稍后重新加载题库。'
  } finally {
    loading.value = false
  }
}

function payload() {
  const options = isChoice.value
    ? form.value.options.map((option: any, index: number) => ({ key: option.key, content: option.content.trim(), is_correct: !!option.is_correct, order_index: index }))
    : []
  const answer = isChoice.value ? options.filter((option) => option.is_correct).map((option) => option.key).join('') : form.value.answer.trim()
  return { course_id: cid.value, kp_id: form.value.kp_id, qtype: form.value.qtype, stem: form.value.stem.trim(), answer, analysis: form.value.analysis.trim(), difficulty: form.value.difficulty, tags: form.value.tags.trim(), source: 'manual', options }
}

async function save() {
  const data = payload()
  if (!data.stem) return ElMessage.warning('请填写题干')
  if (isChoice.value && data.options.some((option) => !option.content)) return ElMessage.warning('请补全所有选项内容')
  if (!data.answer) return ElMessage.warning('请设置正确答案')
  saving.value = true
  try {
    let retainedOldVersion = false
    if (form.value.id) {
      try {
        await question.update(form.value.id, data)
      } catch (err) {
        if (!(err instanceof ApiError) || ![404, 405].includes(Number(err.status))) throw err
        await question.add(data)
        try { await question.remove(form.value.id, true) }
        catch { retainedOldVersion = true }
      }
    } else {
      await question.add(data)
    }
    if (retainedOldVersion) ElMessage.warning('已保存为新版本；旧题因已有学习记录而保留')
    else ElMessage.success('题目已保存')
    dialogOpen.value = false
    await load()
  } catch (err: any) {
    ElMessage.error(err?.message || '题目保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(id: number) {
  try {
    await ElMessageBox.confirm('删除后将不再用于后续测评，确定继续吗？', '删除题目', { type: 'warning' })
  } catch { return }
  await question.remove(id)
  ElMessage.success('题目已删除')
  await load()
}

onMounted(load)
</script>

<style scoped>
.table-toolbar { margin-bottom: 14px; }
.table-toolbar .card-title { margin-bottom: 0; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.option-editor { width: 100%; display: grid; gap: 9px; }
.option-row { display: grid; grid-template-columns: 28px 28px minmax(0, 1fr) 32px; gap: 8px; align-items: center; }
.option-key { width: 28px; height: 28px; display: grid; place-items: center; border-radius: 8px; color: var(--primary); background: var(--primary-bg); font-weight: 750; }
@media (max-width: 680px) { .form-grid { grid-template-columns: 1fr; gap: 0; } }
</style>
