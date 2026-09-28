<template>
  <main class="standalone-state">
    <section>
      <span class="state-code">404</span>
      <p class="eyebrow">页面不存在</p>
      <h1>没有找到你访问的页面</h1>
      <p>地址可能已变更，或该功能不属于当前版本。平台不会把未知地址静默跳转到其他页面。</p>
      <div class="actions">
        <el-button type="primary" @click="goHome">返回工作台</el-button>
        <el-button @click="router.replace('/login')">返回登录</el-button>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { homeForRole } from '@/router/guards'

const router = useRouter()
const store = useUserStore()
function goHome() {
  router.replace(store.isLogin ? homeForRole(store.role) : '/login')
}
</script>

<style scoped>
.standalone-state { min-height: 100vh; display: grid; place-items: center; padding: 32px; color: var(--text); background: radial-gradient(circle at 82% 12%, rgba(15,118,110,.09), transparent 32%), var(--bg); }
.standalone-state section { width: min(640px, 100%); padding: 48px; border: 1px solid var(--border); border-radius: var(--radius-xl); background: #fff; box-shadow: var(--shadow-md); }
.state-code { color: var(--primary); font-size: 72px; line-height: 1; font-weight: 800; letter-spacing: -.07em; }
.eyebrow { margin-top: 24px; color: var(--primary); font-size: 12px; font-weight: 800; letter-spacing: .1em; }
h1 { margin: 8px 0 14px; font-size: clamp(28px, 5vw, 42px); line-height: 1.15; letter-spacing: -.04em; }
section > p:not(.eyebrow) { color: var(--text-secondary); line-height: 1.8; }
.actions { display: flex; gap: 10px; margin-top: 28px; flex-wrap: wrap; }
</style>
