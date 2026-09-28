<template>
  <main class="login-page">
    <section class="brand-panel">
      <header class="brand-lockup">
        <span><el-icon><Cpu /></el-icon></span>
        <div><b>XunkeFlow</b><small>循课</small></div>
      </header>
      <div class="brand-message">
        <p class="eyebrow">高校课程智能工作台</p>
        <h1><span>让课程资料驱动个性化学习</span><span>让教学成效形成可验证闭环</span></h1>
        <p>面向教师、学生和教学管理者的统一课程资源与学习成效平台。</p>
      </div>
      <div class="capability-list">
        <article><el-icon><Reading /></el-icon><div><b>课程内容沉淀</b><span>资料上传、知识点组织、课程引用可追溯</span></div></article>
        <article><el-icon><User /></el-icon><div><b>个性化学习</b><span>前测诊断、学习路径、讲义与分层练习</span></div></article>
        <article><el-icon><TrendCharts /></el-icon><div><b>教学成效闭环</b><span>教师审核、错题补救、前后测与学习报告</span></div></article>
      </div>
    </section>

    <section class="login-panel">
      <div class="login-form-wrap">
        <div class="form-head">
          <span class="mobile-brand"><el-icon><Cpu /></el-icon></span>
          <h2>登录工作台</h2>
          <p>{{ IS_SHOWCASE ? '前端展示 · 使用下方体验账号浏览，数据仅供演示。' : '使用学校或团队分配的账号继续。' }}</p>
        </div>

        <el-form :model="form" label-position="top" @submit.prevent="onLogin">
          <el-form-item label="用户名">
            <el-input v-model="form.username" autocomplete="username" placeholder="请输入用户名" size="large" :prefix-icon="User" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="form.password" autocomplete="current-password" type="password" placeholder="请输入密码" size="large" show-password :prefix-icon="Lock" @keyup.enter="onLogin" />
          </el-form-item>
          <el-button data-testid="login-submit" native-type="submit" type="primary" size="large" class="login-button" :loading="loading">登录</el-button>
        </el-form>

        <div class="quick-login">
          <div><span>体验账号</span><small>用于本地验收与比赛演示</small></div>
          <div class="account-buttons">
            <button type="button" @click="fill('admin')">管理员</button>
            <button type="button" @click="fill('teacher')">教师</button>
            <button type="button" @click="fill('student01')">学生</button>
          </div>
          <p>体验账号默认密码：123456</p>
        </div>

        <footer><router-link to="/register">注册学生账号</router-link><router-link to="/intro">了解平台</router-link></footer>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { IS_SHOWCASE } from '@/config/runtime'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { homeForRole, safeInternalRedirect } from '@/router/guards'

const route = useRoute()
const router = useRouter()
const store = useUserStore()
const loading = ref(false)
const form = ref({ username: 'admin', password: '123456' })

function fill(username: string) { form.value = { username, password: '123456' } }

async function onLogin() {
  if (loading.value) return
  if (!form.value.username.trim() || !form.value.password) return ElMessage.warning('请输入用户名和密码')
  loading.value = true
  try {
    await store.login(form.value.username.trim(), form.value.password)
    await store.checkDemo()
    const fallback = homeForRole(store.role)
    const redirect = safeInternalRedirect(route.query.redirect, fallback)
    ElMessage.success('登录成功')
    await router.replace(redirect)
  } catch { /* 请求层已展示可读错误 */ }
  finally { loading.value = false }
}

onMounted(() => { if (store.isLogin && store.user) router.replace('/dashboard') })
</script>

<style scoped>
.login-page { min-height: 100vh; display: grid; grid-template-columns: minmax(420px, 1.05fr) minmax(420px, .95fr); background: #f5f7fb; }
.brand-panel { min-height: 100vh; display: flex; flex-direction: column; padding: clamp(34px, 5vw, 72px); color: #fff; background: #3730a3; }
.brand-lockup { display: flex; align-items: center; gap: 12px; }.brand-lockup > span { width: 44px; height: 44px; display: grid; place-items: center; border-radius: 12px; background: rgba(255,255,255,.13); font-size: 21px; }.brand-lockup b, .brand-lockup small { display: block; }.brand-lockup b { font-size: 17px; }.brand-lockup small { color: #c7d2fe; font-size: 11px; }
.brand-message { max-width: 680px; margin: auto 0; }.eyebrow { color: #c7d2fe; font-size: 12px; font-weight: 800; letter-spacing: .1em; }.brand-message h1 { margin: 16px 0 18px; font-size: clamp(36px, 3.3vw, 46px); line-height: 1.16; letter-spacing: -.04em; text-wrap: balance; }.brand-message h1 span { display: block; }.brand-message h1 span + span { margin-top: 4px; }.brand-message > p:last-child { max-width: 600px; color: #e0e7ff; font-size: 15px; line-height: 1.8; }
.capability-list { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }.capability-list article { padding: 15px; border-top: 1px solid rgba(255,255,255,.28); }.capability-list .el-icon { margin-bottom: 9px; color: #c7d2fe; font-size: 20px; }.capability-list b, .capability-list span { display: block; }.capability-list b { font-size: 13px; }.capability-list span { margin-top: 4px; color: #c7d2fe; font-size: 11px; line-height: 1.6; }
.login-panel { display: grid; place-items: center; padding: 36px; }.login-form-wrap { width: min(410px, 100%); }.form-head { margin-bottom: 28px; }.form-head h2 { font-size: 28px; letter-spacing: -.035em; }.form-head p { margin-top: 5px; color: var(--text-secondary); }.mobile-brand { display: none; }
.login-form-wrap :deep(.el-form-item__label) { color: var(--text); font-weight: 700; }.login-button { width: 100%; height: 46px; margin-top: 4px; }
.quick-login { margin-top: 26px; padding-top: 20px; border-top: 1px solid var(--border); }.quick-login > div:first-child { display: flex; justify-content: space-between; gap: 12px; }.quick-login span { font-weight: 700; }.quick-login small, .quick-login p { color: var(--text-muted); font-size: 11px; }.account-buttons { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 11px 0 7px; }.account-buttons button { min-height: 38px; border: 1px solid var(--border); border-radius: 9px; background: #fff; color: var(--text-secondary); cursor: pointer; }.account-buttons button:hover { border-color: var(--primary-light); color: var(--primary); background: var(--primary-bg); }
.login-form-wrap footer { display: flex; justify-content: center; gap: 20px; margin-top: 24px; font-size: 13px; }
@media (max-width: 900px) { .login-page { grid-template-columns: 1fr; }.brand-panel { display: none; }.login-panel { min-height: 100vh; padding: 24px; }.mobile-brand { width: 46px; height: 46px; display: grid; place-items: center; margin-bottom: 18px; border-radius: 13px; color: #fff; background: var(--primary); font-size: 21px; } }
</style>
