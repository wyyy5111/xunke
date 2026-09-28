<template>
  <div class="page admin-users-page">
    <div class="page-header">
      <div>
        <div class="page-title">用户管理</div>
        <div class="page-desc">统一治理账号状态与角色权限。角色调整由后端校验，并始终保留至少一个启用管理员。</div>
      </div>
      <el-input v-model="keyword" class="search" placeholder="搜索姓名 / 用户名 / 邮箱" clearable>
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <el-alert v-if="error" type="error" :closable="false" show-icon style="margin-bottom:16px">{{ error }} <el-button text @click="load">重新加载</el-button></el-alert>

    <div class="grid grid-4">
      <div class="stat-card">
        <div class="stat-label">用户总数</div>
        <div class="stat-value">{{ list.length }}</div>
        <div class="stat-icon"><el-icon><User /></el-icon></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">学生</div>
        <div class="stat-value">{{ countRole('student') }}</div>
        <div class="stat-icon"><el-icon><Avatar /></el-icon></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">教师</div>
        <div class="stat-value">{{ countRole('teacher') }}</div>
        <div class="stat-icon"><el-icon><Reading /></el-icon></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">管理员</div>
        <div class="stat-value">{{ countRole('admin') }}</div>
        <div class="stat-icon"><el-icon><Key /></el-icon></div>
      </div>
    </div>

    <div class="card account-surface">
      <div class="account-head">
        <div class="card-title"><el-icon><Avatar /></el-icon> 账号列表</div>
        <div class="account-health"><span></span>{{ list.filter(u => u.is_active).length }} 个账号已启用</div>
      </div>
      <el-table v-loading="loading" :data="filtered" stripe empty-text="没有符合条件的账号">
        <el-table-column prop="id" label="ID" width="64" />
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="full_name" label="姓名" min-width="120" />
        <el-table-column prop="email" label="邮箱" min-width="200" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="roleType(row.role)">{{ roleText(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              :loading="updatingStatusId === row.id"
              :disabled="updatingStatusId !== null || roleUpdating"
              @change="toggle(row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" min-width="170" />
        <el-table-column label="权限操作" width="126" fixed="right">
          <template #default="{ row }">
            <span v-if="row.id === currentUserId" class="self-account"><el-icon><Lock /></el-icon> 当前账号</span>
            <el-button
              v-else
              link
              type="primary"
              :data-testid="`role-action-${row.id}`"
              @click="openRoleDialog(row)"
            >
              调整角色
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="governance-note">
        <el-icon><CircleCheck /></el-icon>
        <span>角色变更即时生效；已登录用户的下一次受保护请求会按数据库中的最新角色重新鉴权。</span>
      </div>
    </div>

    <el-dialog
      v-model="roleDialogVisible"
      title="调整账号角色"
      width="520px"
      :teleported="false"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div v-if="roleTarget" class="role-dialog-body">
        <div class="role-target">
          <span class="role-avatar">{{ (roleTarget.full_name || roleTarget.username).slice(0, 1) }}</span>
          <div>
            <b>{{ roleTarget.full_name || roleTarget.username }}</b>
            <p>@{{ roleTarget.username }} · 当前角色：{{ roleText(roleTarget.role) }}</p>
          </div>
        </div>
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="角色变更会影响该账号可访问的课程、审核与系统治理功能，请确认职责后再提交。"
        />
        <el-radio-group v-model="selectedRole" class="role-options">
          <el-radio v-for="option in roleOptions" :key="option.value" :value="option.value" border>
            <span class="role-option-copy"><b>{{ option.label }}</b><small>{{ option.description }}</small></span>
          </el-radio>
        </el-radio-group>
      </div>
      <template #footer>
        <el-button :disabled="roleUpdating" @click="roleDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          data-testid="confirm-role"
          :loading="roleUpdating"
          :disabled="!roleTarget || selectedRole === roleTarget.role"
          @click="confirmRoleChange"
        >确认变更</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { admin } from '@/api'
import { useUserStore } from '@/stores/user'

type UserRole = 'student' | 'teacher' | 'admin'
interface ManagedUser {
  id: number
  username: string
  full_name: string
  email: string
  role: UserRole
  is_active: boolean
  created_at: string
}

const userStore = useUserStore()
const list = ref<ManagedUser[]>([])
const keyword = ref('')
const error = ref('')
const loading = ref(true)
const updatingStatusId = ref<number | null>(null)
const roleUpdating = ref(false)
const roleDialogVisible = ref(false)
const roleTarget = ref<ManagedUser | null>(null)
const selectedRole = ref<UserRole>('student')
const currentUserId = computed(() => Number(userStore.user?.id || 0))
const roleOptions: Array<{ value: UserRole; label: string; description: string }> = [
  { value: 'student', label: '学生', description: '参与课程学习、测评与个人资源使用' },
  { value: 'teacher', label: '教师', description: '管理课程资料、资源生成与审核发布' },
  { value: 'admin', label: '管理员', description: '拥有平台治理、用户与运行观测权限' },
]
const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return list.value
  return list.value.filter(u => [u.username, u.full_name, u.email, roleText(u.role)].some(v => String(v || '').toLowerCase().includes(k)))
})
const roleText = (r: string) => ({ student: '学生', teacher: '教师', admin: '管理员' }[r] || r)
const roleType = (r: string) => ({ student: 'success', teacher: 'warning', admin: 'primary' }[r] as any)
const countRole = (r: string) => list.value.filter(u => u.role === r).length

async function load() {
  loading.value = true
  error.value = ''
  try { list.value = await admin.users() as ManagedUser[] }
  catch (err: any) { error.value = err?.message || '用户列表加载失败。' }
  finally { loading.value = false }
}
async function toggle(row: ManagedUser) {
  updatingStatusId.value = row.id
  try {
    await admin.updateUser(row.id, { is_active: !row.is_active })
    ElMessage.success(row.is_active ? '账号已停用' : '账号已启用')
    await load()
  } catch (err: any) {
    ElMessage.error(err?.message || '账号状态更新失败')
  } finally {
    updatingStatusId.value = null
  }
}
function openRoleDialog(row: ManagedUser) {
  roleTarget.value = row
  selectedRole.value = row.role
  roleDialogVisible.value = true
}
async function confirmRoleChange() {
  if (!roleTarget.value || selectedRole.value === roleTarget.value.role) return
  roleUpdating.value = true
  try {
    await admin.updateRole(roleTarget.value.id, selectedRole.value)
    ElMessage.success(`已将 ${roleTarget.value.full_name || roleTarget.value.username} 调整为${roleText(selectedRole.value)}`)
    roleDialogVisible.value = false
    await load()
  } catch (err: any) {
    ElMessage.error(err?.message || '角色调整失败')
  } finally {
    roleUpdating.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.search { width: 300px; }
.account-surface { padding-bottom: 16px; }
.account-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 4px; }
.account-health { display: inline-flex; align-items: center; gap: 7px; color: var(--text-secondary); font-size: 12px; font-weight: 700; }
.account-health span { width: 7px; height: 7px; border-radius: 50%; background: var(--success); box-shadow: 0 0 0 4px rgba(16, 185, 129, .11); }
.self-account { display: inline-flex; align-items: center; gap: 5px; color: var(--text-muted); font-size: 12px; }
.governance-note { display: flex; align-items: center; gap: 8px; margin: 14px 2px 0; color: var(--text-secondary); font-size: 12px; }
.governance-note .el-icon { color: var(--primary); }
.role-dialog-body { display: grid; gap: 18px; }
.role-target { display: flex; align-items: center; gap: 12px; padding: 14px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--bg-secondary); }
.role-avatar { width: 42px; height: 42px; display: grid; place-items: center; flex: none; border-radius: 12px; color: #fff; background: var(--gradient-primary); font-size: 17px; font-weight: 800; }
.role-target b { display: block; font-size: 15px; }
.role-target p { margin-top: 3px; color: var(--text-secondary); font-size: 12px; }
.role-options { display: grid; gap: 9px; }
.role-options :deep(.el-radio) { width: 100%; height: auto; min-height: 58px; margin: 0; padding: 10px 14px; }
.role-options :deep(.el-radio__label) { flex: 1; }
.role-option-copy { display: grid; gap: 3px; }
.role-option-copy b { color: var(--text); font-size: 13px; }
.role-option-copy small { color: var(--text-secondary); font-size: 12px; white-space: normal; }
@media (max-width: 720px) {
  .search { width: 100%; }
  .account-head { align-items: flex-start; flex-direction: column; }
}
</style>
