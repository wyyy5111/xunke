<template>
  <div class="page course-management">
    <header class="page-header">
      <div>
        <div class="page-title">课程管理</div>
        <div class="page-desc">维护课程信息、生命周期与教学资料入口，所有变更均实时保存到课程库。</div>
      </div>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建课程</el-button>
    </header>

    <section class="course-toolbar">
      <div>
        <span class="course-total">{{ list.length }}</span>
        <p><b>课程资产</b><small>{{ activeCount }} 门进行中 · {{ archivedCount }} 门已归档</small></p>
      </div>
      <el-input v-model="keyword" clearable placeholder="搜索课程名称、代码或标签" @keyup.enter="load">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </section>

    <div v-if="loading" class="table-state"><el-skeleton animated :rows="7" /></div>
    <div v-else-if="error" class="page-state error">
      <div>
        <div class="state-icon"><el-icon><WarningFilled /></el-icon></div>
        <h3>课程列表加载失败</h3><p>{{ error }}</p>
        <el-button type="primary" @click="load">重新加载</el-button>
      </div>
    </div>
    <div v-else-if="!filteredList.length" class="page-state">
      <div>
        <div class="state-icon"><el-icon><Reading /></el-icon></div>
        <h3>{{ keyword ? '没有匹配课程' : '还没有创建课程' }}</h3>
        <p>{{ keyword ? '请调整搜索关键词。' : '创建课程后即可上传资料、维护知识体系并生成学习资源。' }}</p>
        <el-button v-if="!keyword" type="primary" @click="openCreate">新建第一门课程</el-button>
      </div>
    </div>

    <div v-else class="table-shell">
      <el-table :data="filteredList" row-key="id">
        <el-table-column label="课程" min-width="250">
          <template #default="{ row }">
            <div class="course-cell">
              <span class="course-symbol"><el-icon><Reading /></el-icon></span>
              <div><b>{{ row.name }}</b><small>{{ row.code || `COURSE-${row.id}` }}</small></div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="课程说明" min-width="280" show-overflow-tooltip>
          <template #default="{ row }"><span class="description-cell">{{ row.description || '暂未填写课程说明' }}</span></template>
        </el-table-column>
        <el-table-column label="标签" min-width="180">
          <template #default="{ row }">
            <div class="tag-row"><el-tag v-for="tag in tagsOf(row.tags)" :key="tag" size="small" effect="plain">{{ tag }}</el-tag><span v-if="!tagsOf(row.tags).length" class="muted">未设置</span></div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }"><span :class="['course-status', row.status]">{{ row.status === 'active' ? '进行中' : '已归档' }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)"><el-icon><Edit /></el-icon>编辑</el-button>
            <el-button size="small" @click="go(row.id, 'upload')">资料</el-button>
            <el-button size="small" @click="go(row.id, 'knowledge')">知识体系</el-button>
            <el-dropdown trigger="click" @command="(command) => handleCommand(command, row)">
              <el-button size="small" text><el-icon><MoreFilled /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="generate">资源生成</el-dropdown-item>
                  <el-dropdown-item command="review">资源审核</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除课程</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑课程' : '新建课程'" width="560px" destroy-on-close>
      <el-form label-position="top">
        <div class="dialog-grid">
          <el-form-item label="课程名称" required><el-input v-model="form.name" maxlength="128" placeholder="例如：现代教育技术" /></el-form-item>
          <el-form-item label="课程代码"><el-input v-model="form.code" maxlength="64" placeholder="例如：EDU-2026" /></el-form-item>
        </div>
        <el-form-item label="课程说明"><el-input v-model="form.description" type="textarea" :rows="4" maxlength="2000" show-word-limit placeholder="说明课程目标、适用对象与教学范围" /></el-form-item>
        <el-form-item label="课程标签"><el-input v-model="form.tags" maxlength="256" placeholder="使用逗号分隔，例如：教师教育,项目式学习" /></el-form-item>
        <el-form-item label="封面地址"><el-input v-model="form.cover" maxlength="256" placeholder="可选，填写安全的 HTTPS 图片地址" /></el-form-item>
        <el-form-item v-if="editingId" label="课程状态">
          <el-radio-group v-model="form.status"><el-radio-button value="active">进行中</el-radio-button><el-radio-button value="archived">已归档</el-radio-button></el-radio-group>
          <div class="field-help">归档后学生无法发现课程，也不能启动新的生成任务；历史数据仍保留。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="saving" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ editingId ? '保存修改' : '创建课程' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { course } from '@/api'

const router = useRouter()
const list = ref<any[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const keyword = ref('')
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ name: '', code: '', description: '', tags: '', cover: '', status: 'active' })

const activeCount = computed(() => list.value.filter((item) => item.status === 'active').length)
const archivedCount = computed(() => list.value.filter((item) => item.status === 'archived').length)
const filteredList = computed(() => {
  const needle = keyword.value.trim().toLocaleLowerCase()
  if (!needle) return list.value
  return list.value.filter((item) => [item.name, item.code, item.tags].some((value) => String(value || '').toLocaleLowerCase().includes(needle)))
})

function clearForm() {
  Object.assign(form, { name: '', code: '', description: '', tags: '', cover: '', status: 'active' })
}

async function load() {
  loading.value = true
  error.value = ''
  try { list.value = await course.list('', true) }
  catch (err: any) { error.value = err?.message || '无法读取课程列表' }
  finally { loading.value = false }
}

function openCreate() {
  editingId.value = null
  clearForm()
  dialogVisible.value = true
}

function openEdit(row: any) {
  editingId.value = Number(row.id)
  Object.assign(form, {
    name: row.name || '', code: row.code || '', description: row.description || '',
    tags: row.tags || '', cover: row.cover || '', status: row.status || 'active'
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.name.trim()) return ElMessage.warning('请填写课程名称')
  saving.value = true
  try {
    const payload = { ...form, name: form.name.trim(), code: form.code.trim(), tags: form.tags.trim() }
    if (editingId.value) await course.update(editingId.value, payload)
    else await course.create(payload)
    ElMessage.success(editingId.value ? '课程信息已更新' : '课程创建成功')
    dialogVisible.value = false
    await load()
  } finally { saving.value = false }
}

function tagsOf(value: string) { return String(value || '').split(',').map((item) => item.trim()).filter(Boolean).slice(0, 3) }

function go(id: number, target: string) {
  localStorage.setItem('xunkeflow_cid', String(id))
  router.push(`/teacher/${target}/${id}`)
}

async function remove(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除课程“${row.name}”吗？已有学习数据时系统会拒绝删除，建议改为归档。`, '删除课程', { type: 'warning', confirmButtonText: '确认删除' })
    await course.remove(row.id)
    ElMessage.success('课程已删除')
    if (Number(localStorage.getItem('xunkeflow_cid')) === Number(row.id)) localStorage.removeItem('xunkeflow_cid')
    await load()
  } catch (err: any) {
    if (err === 'cancel' || err === 'close') return
    throw err
  }
}

function handleCommand(command: string, row: any) {
  if (command === 'delete') return remove(row)
  go(row.id, command)
}

onMounted(load)
</script>

<style scoped>
.course-management { max-width: 1500px; }
.course-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-bottom: 16px; padding: 16px 18px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; }
.course-toolbar > div { display: flex; align-items: center; gap: 12px; }
.course-total { width: 45px; height: 45px; display: grid; place-items: center; border-radius: 13px; color: var(--primary); background: var(--primary-bg); font-size: 20px; font-weight: 800; }
.course-toolbar p { display: grid; }
.course-toolbar p b { font-size: 14px; }
.course-toolbar p small { color: var(--text-secondary); font-size: 11px; }
.course-toolbar .el-input { width: min(360px, 40vw); }
.table-shell, .table-state { border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; background: #fff; box-shadow: var(--shadow-sm); }
.table-state { padding: 24px; }
.course-cell { display: flex; align-items: center; gap: 11px; }
.course-symbol { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 11px; color: var(--primary); background: var(--primary-bg); font-size: 17px; }
.course-cell div { display: grid; min-width: 0; }
.course-cell b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.course-cell small { color: var(--text-secondary); font-size: 11px; }
.description-cell { color: var(--text-secondary); }
.course-status { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 700; }
.course-status::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.course-status.active { color: var(--success); }
.course-status.archived { color: var(--text-muted); }
.dialog-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.field-help { margin-top: 8px; color: var(--text-secondary); font-size: 11px; }
@media (max-width: 760px) {
  .course-toolbar { align-items: stretch; flex-direction: column; }
  .course-toolbar .el-input { width: 100%; }
  .dialog-grid { grid-template-columns: 1fr; gap: 0; }
}
</style>
