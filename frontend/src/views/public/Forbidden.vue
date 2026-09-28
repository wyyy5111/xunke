<template>
  <main class="standalone-state">
    <section>
      <span class="state-code">403</span>
      <p class="eyebrow">访问权限不足</p>
      <h1>这个工作区不属于当前角色</h1>
      <p>系统已在后端继续执行角色与数据归属校验。请返回自己的工作台，或切换到具备权限的账号。</p>
      <div class="actions">
        <el-button type="primary" @click="router.replace(home)">返回我的工作台</el-button>
        <el-button @click="router.back()">返回上一页</el-button>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { homeForRole } from '@/router/guards'

const router = useRouter()
const store = useUserStore()
const home = computed(() => homeForRole(store.role))
</script>

<style scoped>
.standalone-state { min-height: 100vh; display: grid; place-items: center; padding: 32px; color: var(--text); background: radial-gradient(circle at 18% 10%, rgba(79,70,229,.1), transparent 34%), var(--bg); }
.standalone-state section { width: min(640px, 100%); padding: 48px; border: 1px solid var(--border); border-radius: var(--radius-xl); background: #fff; box-shadow: var(--shadow-md); }
.state-code { color: var(--primary); font-size: 72px; line-height: 1; font-weight: 800; letter-spacing: -.07em; }
.eyebrow { margin-top: 24px; color: var(--primary); font-size: 12px; font-weight: 800; letter-spacing: .1em; }
h1 { margin: 8px 0 14px; font-size: clamp(28px, 5vw, 42px); line-height: 1.15; letter-spacing: -.04em; }
section > p:not(.eyebrow) { color: var(--text-secondary); line-height: 1.8; }
.actions { display: flex; gap: 10px; margin-top: 28px; flex-wrap: wrap; }
</style>
