<template>
  <div class="page knowledge-page">
    <header class="page-header">
      <div>
        <div class="page-title">课程知识体系</div>
        <div class="page-desc">统一维护章节、知识点与先修关系，变更会直接进入检索、学习路径和知识图谱。</div>
      </div>
      <el-button @click="router.push(`/teacher/graph/${cid}`)"><el-icon><Share /></el-icon>查看知识图谱</el-button>
    </header>

    <section class="knowledge-summary" aria-label="知识体系概览">
      <article><span><el-icon><Collection /></el-icon></span><div><small>课程章节</small><strong>{{ chapters.length }}</strong></div></article>
      <article><span><el-icon><Connection /></el-icon></span><div><small>知识点</small><strong>{{ points.length }}</strong></div></article>
      <article><span><el-icon><Share /></el-icon></span><div><small>知识关系</small><strong>{{ relations.length }}</strong></div></article>
      <article><span><el-icon><DataAnalysis /></el-icon></span><div><small>平均难度</small><strong>{{ averageDifficulty }}</strong></div></article>
    </section>

    <div v-if="loading" class="knowledge-loading"><el-skeleton animated :rows="8" /></div>
    <div v-else-if="error" class="page-state error">
      <div><div class="state-icon"><el-icon><WarningFilled /></el-icon></div><h3>知识体系加载失败</h3><p>{{ error }}</p><el-button type="primary" @click="load">重新加载</el-button></div>
    </div>

    <section v-else class="knowledge-workspace">
      <el-tabs v-model="activeTab">
        <el-tab-pane name="chapters">
          <template #label><span class="tab-label"><el-icon><Collection /></el-icon>章节管理 <b>{{ chapters.length }}</b></span></template>
          <div class="workspace-head"><div><h2>课程章节</h2><p>组织教学顺序；删除章节时知识点会保留并回到“未归类”。</p></div><el-button type="primary" @click="openChapter()"><el-icon><Plus /></el-icon>新增章节</el-button></div>
          <el-table v-if="chapters.length" :data="chapters" row-key="id">
            <el-table-column prop="order_index" label="顺序" width="80" />
            <el-table-column prop="title" label="章节名称" min-width="180" />
            <el-table-column prop="summary" label="章节说明" min-width="300" show-overflow-tooltip>
              <template #default="{ row }"><span class="muted">{{ row.summary || '暂未填写章节说明' }}</span></template>
            </el-table-column>
            <el-table-column label="知识点" width="100"><template #default="{ row }">{{ chapterPointCount(row.id) }} 个</template></el-table-column>
            <el-table-column label="操作" width="160"><template #default="{ row }"><el-button size="small" @click="openChapter(row)">编辑</el-button><el-button size="small" type="danger" plain @click="removeChapter(row)">删除</el-button></template></el-table-column>
          </el-table>
          <div v-else class="inline-empty"><el-icon><Collection /></el-icon><div><b>暂无课程章节</b><p>先建立章节结构，再将知识点归入对应章节。</p></div><el-button type="primary" @click="openChapter()">新增章节</el-button></div>
        </el-tab-pane>

        <el-tab-pane name="points">
          <template #label><span class="tab-label"><el-icon><Connection /></el-icon>知识点 <b>{{ points.length }}</b></span></template>
          <div class="workspace-head"><div><h2>知识点资产</h2><p>难度和重要度会参与测评组卷、掌握度计算和路径排序。</p></div><el-button type="primary" @click="openPoint()"><el-icon><Plus /></el-icon>新增知识点</el-button></div>
          <el-table v-if="points.length" :data="points" row-key="id">
            <el-table-column prop="name" label="知识点" min-width="180" />
            <el-table-column label="所属章节" min-width="150"><template #default="{ row }">{{ chapterName(row.chapter_id) }}</template></el-table-column>
            <el-table-column prop="description" label="说明" min-width="240" show-overflow-tooltip><template #default="{ row }"><span class="muted">{{ row.description || '暂未填写说明' }}</span></template></el-table-column>
            <el-table-column label="难度" width="130"><template #default="{ row }"><el-rate :model-value="row.difficulty" disabled size="small" /></template></el-table-column>
            <el-table-column label="重要度" width="110"><template #default="{ row }"><b>{{ Math.round(row.importance * 100) }}%</b></template></el-table-column>
            <el-table-column prop="keywords" label="关键词" min-width="150" show-overflow-tooltip />
            <el-table-column label="操作" width="160"><template #default="{ row }"><el-button size="small" @click="openPoint(row)">编辑</el-button><el-button size="small" type="danger" plain @click="removePoint(row)">删除</el-button></template></el-table-column>
          </el-table>
          <div v-else class="inline-empty"><el-icon><Connection /></el-icon><div><b>暂无知识点</b><p>新增知识点后，可建立先修、相似或易混关系。</p></div><el-button type="primary" @click="openPoint()">新增知识点</el-button></div>
        </el-tab-pane>

        <el-tab-pane name="relations">
          <template #label><span class="tab-label"><el-icon><Share /></el-icon>知识关系 <b>{{ relations.length }}</b></span></template>
          <div class="workspace-head"><div><h2>知识关系</h2><p>关系是学习路径排序与知识图谱连线的真实数据来源。</p></div><el-button type="primary" :disabled="points.length < 2" @click="openRelation()"><el-icon><Plus /></el-icon>新增关系</el-button></div>
          <div v-if="relations.length" class="relation-list">
            <article v-for="item in relations" :key="item.id">
              <span class="node-name">{{ pointName(item.source) }}</span>
              <span class="relation-arrow"><small>{{ relationText(item.relation) }}</small><i></i><el-icon><Right /></el-icon></span>
              <span class="node-name target">{{ pointName(item.target) }}</span>
              <span class="relation-weight">权重 {{ Math.round(item.weight * 100) }}%</span>
              <div><el-button size="small" @click="openRelation(item)">编辑</el-button><el-button size="small" type="danger" plain @click="removeRelation(item)">删除</el-button></div>
            </article>
          </div>
          <div v-else class="inline-empty"><el-icon><Share /></el-icon><div><b>{{ points.length < 2 ? '至少需要两个知识点' : '暂无知识关系' }}</b><p>{{ points.length < 2 ? '请先在知识点页补齐课程概念。' : '建立关系后，学习路径和知识图谱会同步更新。' }}</p></div><el-button v-if="points.length >= 2" type="primary" @click="openRelation()">新增关系</el-button></div>
        </el-tab-pane>
      </el-tabs>
    </section>

    <el-dialog v-model="chapterDialog" :title="chapterForm.id ? '编辑章节' : '新增章节'" width="500px">
      <el-form label-position="top">
        <el-form-item label="章节名称" required><el-input v-model="chapterForm.title" maxlength="128" /></el-form-item>
        <el-form-item label="章节说明"><el-input v-model="chapterForm.summary" type="textarea" :rows="3" maxlength="1000" show-word-limit /></el-form-item>
        <el-form-item label="排序序号"><el-input-number v-model="chapterForm.order_index" :min="0" :max="10000" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="chapterDialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveChapter">保存章节</el-button></template>
    </el-dialog>

    <el-dialog v-model="pointDialog" :title="pointForm.id ? '编辑知识点' : '新增知识点'" width="560px">
      <el-form label-position="top">
        <div class="dialog-grid"><el-form-item label="知识点名称" required><el-input v-model="pointForm.name" maxlength="128" /></el-form-item><el-form-item label="所属章节"><el-select v-model="pointForm.chapter_id" clearable placeholder="未归类"><el-option v-for="item in chapters" :key="item.id" :label="item.title" :value="item.id" /></el-select></el-form-item></div>
        <el-form-item label="知识点说明"><el-input v-model="pointForm.description" type="textarea" :rows="3" maxlength="2000" show-word-limit /></el-form-item>
        <div class="dialog-grid"><el-form-item label="难度"><el-slider v-model="pointForm.difficulty" :min="1" :max="5" show-stops /></el-form-item><el-form-item label="重要度"><el-slider v-model="pointForm.importance" :min="0" :max="1" :step="0.1" show-stops /></el-form-item></div>
        <el-form-item label="关键词"><el-input v-model="pointForm.keywords" maxlength="256" placeholder="使用逗号分隔" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="pointDialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="savePoint">保存知识点</el-button></template>
    </el-dialog>

    <el-dialog v-model="relationDialog" :title="relationForm.id ? '编辑知识关系' : '新增知识关系'" width="540px">
      <el-form label-position="top">
        <div class="dialog-grid"><el-form-item label="起点知识" required><el-select v-model="relationForm.source_id" filterable><el-option v-for="item in points" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item><el-form-item label="目标知识" required><el-select v-model="relationForm.target_id" filterable><el-option v-for="item in points" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item></div>
        <el-form-item label="关系类型"><el-radio-group v-model="relationForm.relation"><el-radio-button value="prerequisite">先修</el-radio-button><el-radio-button value="相似">相似</el-radio-button><el-radio-button value="易混">易混</el-radio-button></el-radio-group></el-form-item>
        <el-form-item label="关系权重"><div class="weight-editor"><el-slider v-model="relationForm.weight" :min="0" :max="1" :step="0.1" /><strong>{{ Math.round(relationForm.weight * 100) }}%</strong></div></el-form-item>
      </el-form>
      <template #footer><el-button @click="relationDialog = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveRelation">保存关系</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { course, kp } from '@/api'

const route = useRoute()
const router = useRouter()
const cid = computed(() => Number(route.params.cid))
const activeTab = ref('chapters')
const chapters = ref<any[]>([])
const points = ref<any[]>([])
const relations = ref<any[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const chapterDialog = ref(false)
const pointDialog = ref(false)
const relationDialog = ref(false)
const chapterForm = reactive<any>({ id: null, title: '', summary: '', order_index: 0 })
const pointForm = reactive<any>({ id: null, chapter_id: null, name: '', description: '', difficulty: 3, importance: 0.5, keywords: '' })
const relationForm = reactive<any>({ id: null, source_id: null, target_id: null, relation: 'prerequisite', weight: 1 })

const averageDifficulty = computed(() => points.value.length ? (points.value.reduce((sum, item) => sum + Number(item.difficulty || 0), 0) / points.value.length).toFixed(1) : '0.0')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [chapterRows, pointRows, graph] = await Promise.all([course.chapters(cid.value), kp.list(cid.value), kp.graph(cid.value)])
    chapters.value = chapterRows
    points.value = pointRows
    relations.value = graph.edges || []
  } catch (err: any) { error.value = err?.message || '无法读取课程知识体系' }
  finally { loading.value = false }
}

function chapterName(id: number | null) { return chapters.value.find((item) => item.id === id)?.title || '未归类' }
function chapterPointCount(id: number) { return points.value.filter((item) => item.chapter_id === id).length }
function pointName(id: number) { return points.value.find((item) => item.id === id)?.name || `知识点 #${id}` }
function relationText(value: string) { return value === 'prerequisite' ? '先修' : value }

function openChapter(row?: any) {
  Object.assign(chapterForm, row ? { ...row } : { id: null, title: '', summary: '', order_index: chapters.value.length })
  chapterDialog.value = true
}

function openPoint(row?: any) {
  Object.assign(pointForm, row ? { ...row } : { id: null, chapter_id: chapters.value[0]?.id || null, name: '', description: '', difficulty: 3, importance: 0.5, keywords: '' })
  pointDialog.value = true
}

function openRelation(row?: any) {
  Object.assign(relationForm, row ? { ...row, source_id: row.source, target_id: row.target } : { id: null, source_id: points.value[0]?.id || null, target_id: points.value[1]?.id || null, relation: 'prerequisite', weight: 1 })
  relationDialog.value = true
}

async function saveChapter() {
  if (!chapterForm.title.trim()) return ElMessage.warning('请填写章节名称')
  saving.value = true
  try {
    const payload = { title: chapterForm.title.trim(), summary: chapterForm.summary.trim(), order_index: chapterForm.order_index }
    if (chapterForm.id) await course.updateChapter(cid.value, chapterForm.id, payload)
    else await course.addChapter(cid.value, payload)
    chapterDialog.value = false; ElMessage.success('章节已保存'); await load()
  } finally { saving.value = false }
}

async function savePoint() {
  if (!pointForm.name.trim()) return ElMessage.warning('请填写知识点名称')
  saving.value = true
  try {
    const payload = { course_id: cid.value, chapter_id: pointForm.chapter_id || null, name: pointForm.name.trim(), description: pointForm.description.trim(), difficulty: pointForm.difficulty, importance: pointForm.importance, keywords: pointForm.keywords.trim() }
    if (pointForm.id) await kp.update(pointForm.id, payload)
    else await kp.add(payload)
    pointDialog.value = false; ElMessage.success('知识点已保存'); await load()
  } finally { saving.value = false }
}

async function saveRelation() {
  if (!relationForm.source_id || !relationForm.target_id) return ElMessage.warning('请选择关系两端的知识点')
  if (relationForm.source_id === relationForm.target_id) return ElMessage.warning('知识点不能与自身建立关系')
  saving.value = true
  try {
    const payload = { course_id: cid.value, source_id: relationForm.source_id, target_id: relationForm.target_id, relation: relationForm.relation, weight: relationForm.weight }
    if (relationForm.id) await kp.updateRelation(relationForm.id, payload)
    else await kp.relation(payload)
    relationDialog.value = false; ElMessage.success('知识关系已保存'); await load()
  } finally { saving.value = false }
}

async function confirmed(message: string, action: () => Promise<any>) {
  try { await ElMessageBox.confirm(message, '请确认', { type: 'warning', confirmButtonText: '确认删除' }); await action(); ElMessage.success('已删除'); await load() }
  catch (err: any) { if (err !== 'cancel' && err !== 'close') throw err }
}

function removeChapter(row: any) { return confirmed(`删除章节“${row.title}”后，所属知识点将保留为未归类。`, () => course.removeChapter(cid.value, row.id)) }
function removePoint(row: any) { return confirmed(`确定删除知识点“${row.name}”吗？`, () => kp.remove(row.id)) }
function removeRelation(row: any) { return confirmed(`确定删除“${pointName(row.source)} → ${pointName(row.target)}”关系吗？`, () => kp.removeRelation(row.id)) }

onMounted(load)
</script>

<style scoped>
.knowledge-page { max-width: 1500px; }
.knowledge-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.knowledge-summary article { display: flex; align-items: center; gap: 13px; padding: 16px 18px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; }
.knowledge-summary article > span { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 11px; color: var(--primary); background: var(--primary-bg); font-size: 17px; }
.knowledge-summary article div { display: grid; }
.knowledge-summary small { color: var(--text-secondary); font-size: 11px; }
.knowledge-summary strong { font-size: 22px; line-height: 1.15; }
.knowledge-loading, .knowledge-workspace { padding: 22px; border: 1px solid var(--border); border-radius: var(--radius-lg); background: #fff; box-shadow: var(--shadow-sm); }
.knowledge-workspace :deep(.el-tabs__header) { margin-bottom: 22px; }
.tab-label { display: inline-flex; align-items: center; gap: 7px; }
.tab-label b { min-width: 20px; padding: 1px 5px; border-radius: 999px; color: var(--text-secondary); background: var(--bg-secondary); font-size: 10px; text-align: center; }
.workspace-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-bottom: 16px; }
.workspace-head h2 { font-size: 16px; }
.workspace-head p { margin-top: 3px; color: var(--text-secondary); font-size: 12px; }
.inline-empty { min-height: 170px; display: flex; align-items: center; justify-content: center; gap: 14px; padding: 30px; border: 1px dashed var(--border); border-radius: var(--radius); background: var(--bg); }
.inline-empty > .el-icon { color: var(--primary); font-size: 25px; }
.inline-empty div { max-width: 430px; }
.inline-empty b { font-size: 14px; }
.inline-empty p { color: var(--text-secondary); font-size: 12px; }
.relation-list { display: grid; gap: 9px; }
.relation-list article { display: grid; grid-template-columns: minmax(140px, 1fr) 150px minmax(140px, 1fr) 100px 150px; align-items: center; gap: 14px; padding: 14px 16px; border: 1px solid var(--border); border-radius: var(--radius); }
.node-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 700; }
.node-name.target { color: var(--primary-dark); }
.relation-arrow { display: grid; grid-template-columns: 1fr auto; align-items: center; position: relative; color: var(--primary); }
.relation-arrow small { grid-column: 1 / -1; margin-bottom: -3px; text-align: center; color: var(--text-secondary); font-size: 10px; }
.relation-arrow i { height: 1px; background: var(--primary-light); }
.relation-weight { color: var(--text-secondary); font-size: 11px; }
.dialog-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.weight-editor { width: 100%; display: grid; grid-template-columns: 1fr 60px; gap: 18px; align-items: center; }
.weight-editor strong { text-align: right; }
@media (max-width: 1050px) {
  .knowledge-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .relation-list article { grid-template-columns: 1fr 100px 1fr; }
  .relation-weight { grid-column: 1 / 2; }
}
@media (max-width: 700px) {
  .knowledge-summary { grid-template-columns: 1fr 1fr; }
  .knowledge-workspace { padding: 16px; }
  .workspace-head { align-items: stretch; flex-direction: column; }
  .relation-list article { grid-template-columns: 1fr; }
  .relation-arrow { width: 140px; transform: rotate(90deg); margin: 8px auto; }
  .dialog-grid { grid-template-columns: 1fr; gap: 0; }
}
</style>
