<template>
  <div class="register-wrap">
    <div class="register-card">
      <h2>注册新账号</h2>
      <el-form :model="form" label-width="90px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="3-32 位" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="至少 8 位，包含字母和数字" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.full_name" />
        </el-form-item>
        <el-form-item label="学号">
          <el-input v-model="form.student_no" />
        </el-form-item>
        <el-form-item label="账号类型">
          <el-tag type="primary" effect="plain">学生账号</el-tag>
          <span class="role-note">教师与管理员账号由平台管理员分配</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="onSubmit">注册</el-button>
          <el-button @click="$router.push('/login')">返回登录</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { auth } from '@/api'

const router = useRouter()
const loading = ref(false)
const form = ref({ username: '', email: '', password: '', full_name: '', student_no: '', role: 'student' })

async function onSubmit() {
  if (!form.value.username || !form.value.password || !form.value.email) return ElMessage.warning('请补全必填项')
  if (form.value.password.length < 8 || !/[A-Za-z]/.test(form.value.password) || !/\d/.test(form.value.password)) {
    return ElMessage.warning('密码至少 8 位，并同时包含字母和数字')
  }
  loading.value = true
  try {
    await auth.register(form.value)
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (err: any) {
    ElMessage.error(err?.message || '注册失败，请检查填写内容')
  } finally { loading.value = false }
}
</script>

<style scoped>
.register-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding:24px; background: var(--bg); }
.register-card { width: min(520px, 100%); background: #fff; padding: 36px; border:1px solid var(--border); border-radius: var(--radius-xl); box-shadow:var(--shadow); }
.register-card h2 { margin-bottom: 22px; }
.role-note { margin-left:10px; color:var(--text-secondary); font-size:12px; }
</style>
