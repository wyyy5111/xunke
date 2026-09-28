<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '76px' : '256px'" class="sidebar" :class="{ 'mobile-open': mobileOpen }">
      <button class="brand" type="button" @click="$router.push('/dashboard')">
        <span class="brand-mark"><el-icon><Cpu /></el-icon></span>
        <span v-if="!collapsed" class="brand-copy">
          <b>XunkeFlow</b>
          <small>循课 · 智能课程中台</small>
        </span>
      </button>

      <el-menu
        :default-active="route.path"
        :collapse="collapsed"
        class="side-menu"
        background-color="transparent"
        text-color="#64748b"
        active-text-color="#0f172a"
        @select="onMenuSelect"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataLine /></el-icon><template #title>工作台</template>
        </el-menu-item>
        <el-menu-item index="/courses">
          <el-icon><Reading /></el-icon><template #title>课程中心</template>
        </el-menu-item>

        <template v-if="role === 'student'">
          <div v-if="!collapsed" class="menu-group-title">学习闭环</div>
          <el-menu-item index="/student"><el-icon><HomeFilled /></el-icon><template #title>学习工作台</template></el-menu-item>
          <el-menu-item index="/student/settings"><el-icon><Setting /></el-icon><template #title>个人设置</template></el-menu-item>
          <el-menu-item :index="`/student/pretest/${activeCourse}`"><el-icon><EditPen /></el-icon><template #title>前测诊断</template></el-menu-item>
          <el-menu-item :index="`/student/profile/${activeCourse}`"><el-icon><User /></el-icon><template #title>学生画像</template></el-menu-item>
          <el-menu-item :index="`/student/path/${activeCourse}`"><el-icon><Guide /></el-icon><template #title>学习路径</template></el-menu-item>
          <el-menu-item :index="`/student/lecture/${activeCourse}`"><el-icon><Document /></el-icon><template #title>智能讲义</template></el-menu-item>
          <el-menu-item :index="`/student/mindmap/${activeCourse}`"><el-icon><Share /></el-icon><template #title>思维导图</template></el-menu-item>
          <el-menu-item :index="`/student/exercise/${activeCourse}`"><el-icon><Tickets /></el-icon><template #title>分层练习</template></el-menu-item>
          <el-menu-item :index="`/student/wrong/${activeCourse}`"><el-icon><WarningFilled /></el-icon><template #title>错题补救</template></el-menu-item>
          <el-menu-item :index="`/student/posttest/${activeCourse}`"><el-icon><Finished /></el-icon><template #title>后测评估</template></el-menu-item>
          <el-menu-item :index="`/student/compare/${activeCourse}`"><el-icon><TrendCharts /></el-icon><template #title>前后对比</template></el-menu-item>
          <el-menu-item :index="`/student/report/${activeCourse}`"><el-icon><Download /></el-icon><template #title>学习报告</template></el-menu-item>
          <el-menu-item :index="`/student/agents/${activeCourse}`"><el-icon><Connection /></el-icon><template #title>AI 指挥舱</template></el-menu-item>
        </template>

        <template v-if="role === 'teacher' || role === 'admin'">
          <div v-if="!collapsed" class="menu-group-title">教学中台</div>
          <el-menu-item index="/teacher"><el-icon><HomeFilled /></el-icon><template #title>教师工作台</template></el-menu-item>
          <el-menu-item index="/teacher/courses"><el-icon><FolderOpened /></el-icon><template #title>课程管理</template></el-menu-item>
          <el-menu-item :index="`/teacher/upload/${activeCourse}`"><el-icon><Upload /></el-icon><template #title>资料上传</template></el-menu-item>
          <el-menu-item :index="`/teacher/knowledge/${activeCourse}`"><el-icon><Collection /></el-icon><template #title>知识点管理</template></el-menu-item>
          <el-menu-item :index="`/teacher/graph/${activeCourse}`"><el-icon><Share /></el-icon><template #title>知识图谱</template></el-menu-item>
          <el-menu-item :index="`/teacher/generate/${activeCourse}`"><el-icon><MagicStick /></el-icon><template #title>资源生成</template></el-menu-item>
          <el-menu-item :index="`/teacher/review/${activeCourse}`"><el-icon><Checked /></el-icon><template #title>资源审核</template></el-menu-item>
          <el-menu-item :index="`/teacher/questions/${activeCourse}`"><el-icon><EditPen /></el-icon><template #title>题库管理</template></el-menu-item>
          <el-menu-item :index="`/teacher/dashboard/${activeCourse}`"><el-icon><DataAnalysis /></el-icon><template #title>班级看板</template></el-menu-item>
          <el-menu-item index="/teacher/agents"><el-icon><Connection /></el-icon><template #title>AI 指挥舱</template></el-menu-item>
        </template>

        <template v-if="role === 'admin'">
          <div v-if="!collapsed" class="menu-group-title">系统治理</div>
          <el-menu-item index="/admin"><el-icon><Odometer /></el-icon><template #title>数据看板</template></el-menu-item>
          <el-menu-item index="/admin/users"><el-icon><Avatar /></el-icon><template #title>用户管理</template></el-menu-item>
          <el-menu-item index="/admin/configs"><el-icon><Setting /></el-icon><template #title>系统配置</template></el-menu-item>
          <el-menu-item index="/admin/agents"><el-icon><Cpu /></el-icon><template #title>AI 指挥舱</template></el-menu-item>
          <el-menu-item index="/admin/logs"><el-icon><Notebook /></el-icon><template #title>调用日志</template></el-menu-item>
        </template>
      </el-menu>

      <div v-if="!collapsed" class="engine-card">
        <span :class="['engine-dot', store.demoMode ? 'builtin' : 'remote']"></span>
        <div>
          <b>{{ IS_SHOWCASE ? '前端展示' : degraded ? '在线服务已降级' : store.demoMode ? '演示内容服务' : '智能生成服务' }}</b>
          <small>{{ IS_SHOWCASE ? '样例数据 · 仅供浏览' : degraded ? '真实调用失败，当前使用演示结果' : store.demoMode ? '当前使用本地演示结果' : '当前服务运行正常' }}</small>
        </div>
      </div>
    </el-aside>
    <button v-if="mobileOpen" class="sidebar-mask" type="button" aria-label="关闭导航" @click="mobileOpen = false"></button>

    <el-container class="main-area">
      <el-header class="topbar">
        <div class="topbar-left">
          <el-button text class="collapse-btn" aria-label="切换导航" @click="toggleSidebar">
            <el-icon :size="20"><Fold v-if="!collapsed && !isMobile" /><Expand v-else /></el-icon>
          </el-button>
          <div class="crumb">
            <span>首页</span>
            <el-icon><ArrowRight /></el-icon>
            <b>{{ pageTitle }}</b>
          </div>
        </div>
        <div class="topbar-right">
          <button class="course-context" type="button" @click="router.push('/courses')">
            <el-icon><Reading /></el-icon>
            <span>当前课程</span>
            <b>{{ activeCourse ? `#${activeCourse}` : '未选择' }}</b>
          </button>
          <span :class="['status-badge', store.demoMode ? 'demo' : 'live']">
            {{ IS_SHOWCASE ? '前端展示 · 只读' : degraded ? '服务降级' : store.demoMode ? '演示模式' : '在线模式' }}
          </span>
          <el-tag :type="roleTagType" size="small" effect="plain">{{ roleText }}</el-tag>
          <el-dropdown @command="onCommand" trigger="click">
            <button class="user-info" type="button">
              <el-avatar :size="32" class="avatar">{{ (user?.full_name || user?.username || 'U').charAt(0) }}</el-avatar>
              <span class="username">{{ user?.full_name || user?.username }}</span>
              <el-icon><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="role === 'student'" command="settings">个人设置</el-dropdown-item>
                <el-dropdown-item command="intro">系统介绍</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="page-fade" mode="out-in">
            <component :is="Component" :key="route.fullPath" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { course as courseApi } from '@/api'
import { IS_SHOWCASE } from '@/config/runtime'

const route = useRoute()
const router = useRouter()
const store = useUserStore()
const collapsed = ref(false)
const mobileOpen = ref(false)
const isMobile = ref(window.innerWidth <= 840)
const activeCourseId = ref(Number(localStorage.getItem('xunkeflow_cid') || 0))

const user = computed(() => store.user)
const role = computed(() => store.role)
const degraded = computed(() => !!store.engineInfo?.degraded)
const activeCourse = computed(() => Number(route.params.cid || activeCourseId.value || 0))

const roleText = computed(() => ({ student: '学生', teacher: '教师', admin: '管理员' }[role.value] || '访客'))
const roleTagType = computed(() => ({ student: 'success', teacher: 'info', admin: 'primary' }[role.value] as any))

const pageTitles: Record<string, string> = {
  '/dashboard': '工作台',
  '/courses': '课程中心',
  '/intro': '系统介绍',
  '/student': '学习工作台',
  '/student/settings': '个人设置',
  '/teacher': '教师工作台',
  '/admin': '数据看板',
  '/admin/users': '用户管理',
  '/admin/configs': '系统配置',
  '/admin/agents': 'AI 指挥舱',
  '/admin/logs': '调用日志',
  '/teacher/courses': '课程管理',
  '/teacher/agents': 'AI 指挥舱'
}
const namedTitles: Record<string, string> = {
  preTest: '前测诊断',
  studentProfile: '学生画像',
  learningPath: '学习路径',
  lecture: '智能讲义',
  studentMindmap: '思维导图',
  exercise: '分层练习',
  wrongBook: '错题补救',
  postTest: '后测评估',
  compare: '前后对比',
  studentReport: '学习报告',
  studentAgents: 'AI 指挥舱',
  upload: '资料上传',
  knowledgeMgmt: '知识点管理',
  teacherGraph: '知识图谱',
  generate: '资源生成',
  review: '资源审核',
  questionBank: '题库管理',
  classDashboard: '班级看板',
  experiment: '实验评测'
}
const pageTitle = computed(() => pageTitles[route.path] || namedTitles[String(route.name || '')] || '工作区')

function onCommand(cmd: string) {
  if (cmd === 'logout') {
    store.logout()
    router.push('/login')
  } else if (cmd === 'intro') {
    router.push('/intro')
  } else if (cmd === 'settings') {
    router.push('/student/settings')
  }
}

function onMenuSelect(index: string) {
  if (!index) return
  mobileOpen.value = false
  if (!activeCourse.value && /\/(student|teacher)\/(pretest|profile|path|lecture|mindmap|exercise|wrong|posttest|compare|report|upload|knowledge|graph|generate|review|questions|dashboard)/.test(index)) {
    ElMessage.info('请先选择一门课程')
    router.push('/courses')
    return
  }
  if (index === route.path) {
    router.replace({ path: index, query: { refresh: String(Date.now()) } })
  } else {
    router.push(index)
  }
}

function syncViewport() {
  isMobile.value = window.innerWidth <= 840
  if (isMobile.value) collapsed.value = false
  else mobileOpen.value = false
}

function toggleSidebar() {
  if (isMobile.value) mobileOpen.value = !mobileOpen.value
  else collapsed.value = !collapsed.value
}

watch(
  () => route.params.cid,
  (cid) => {
    if (cid && Number(cid) > 0) {
      activeCourseId.value = Number(cid)
      localStorage.setItem('xunkeflow_cid', String(cid))
    }
  },
  { immediate: true }
)

onMounted(async () => {
  window.addEventListener('resize', syncViewport)
  if (store.isLogin && !store.user) await store.fetchMe()
  try {
    const rows = await courseApi.list()
    const ids = rows.map((item) => Number(item.id))
    if (!ids.includes(activeCourseId.value)) {
      activeCourseId.value = ids[0] || 0
      if (activeCourseId.value) localStorage.setItem('xunkeflow_cid', String(activeCourseId.value))
      else localStorage.removeItem('xunkeflow_cid')
    }
  } catch { /* 页面自身会提供课程加载重试 */ }
  await store.checkDemo()
})
onBeforeUnmount(() => window.removeEventListener('resize', syncViewport))
</script>

<style scoped>
.layout { height: 100vh; background: var(--bg); }
.sidebar {
  background: rgba(255,255,255,.98);
  border-right: 1px solid var(--border);
  transition: width .25s cubic-bezier(.4,0,.2,1);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 8px 0 24px rgba(23,32,51,.035);
}
.brand {
  height: 72px;
  padding: 0 18px;
  border: 0;
  border-bottom: 1px solid var(--border);
  background: transparent;
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  color: var(--text);
  text-align: left;
}
.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--primary);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 9px 22px rgba(79,70,229,.2);
  flex-shrink: 0;
}
.brand-copy { display: grid; line-height: 1.1; }
.brand-copy b { font-size: 15px; letter-spacing: 0; }
.brand-copy small { margin-top: 5px; color: var(--text-secondary); font-size: 11px; }
.side-menu {
  border-right: 0;
  padding: 10px 8px;
  flex: 1;
  overflow-y: auto;
}
.menu-group-title {
  padding: 16px 12px 7px;
  font-size: 11px;
  color: #94a3b8;
  letter-spacing: .08em;
  font-weight: 800;
}
.side-menu :deep(.el-menu-item) {
  height: 40px;
  line-height: 40px;
  margin: 2px 0;
  border-radius: 10px;
  font-weight: 600;
}
.side-menu :deep(.el-menu-item:hover) {
  background: var(--primary-bg);
  color: var(--primary);
}
.side-menu :deep(.el-menu-item.is-active) {
  background: var(--primary-bg);
  color: var(--primary-dark);
  box-shadow: inset 3px 0 0 var(--primary);
}
.engine-card {
  margin: 12px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: rgba(255,255,255,.86);
  display: flex;
  align-items: center;
  gap: 10px;
}
.engine-card b { display: block; font-size: 12px; }
.engine-card small { display: block; color: var(--text-secondary); font-size: 11px; margin-top: 2px; }
.engine-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 0 4px rgba(245,158,11,.14);
  background: var(--warning);
}
.engine-dot.remote { background: var(--success); box-shadow: 0 0 0 4px rgba(5,150,105,.14); }
.main-area { flex-direction: column; min-width: 0; }
.topbar {
  height: 64px;
  background: rgba(255,255,255,.92);
  backdrop-filter: blur(16px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid rgba(226,232,240,.86);
  flex-shrink: 0;
}
.topbar-left, .topbar-right { display: flex; align-items: center; gap: 12px; min-width: 0; }
.collapse-btn { color: var(--text-secondary); padding: 4px; }
.crumb { display: inline-flex; align-items: center; gap: 8px; color: var(--text-secondary); font-size: 13px; white-space: nowrap; }
.crumb b { color: var(--text); }
.course-context {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0 11px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: #fff;
  color: var(--text-secondary);
  cursor: pointer;
}
.course-context:hover { border-color: var(--primary-light); color: var(--primary); }
.course-context b { color: var(--text); }
.user-info {
  border: 0;
  background: transparent;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--text);
}
.avatar { background: var(--primary); font-weight: 800; }
.username { font-size: 13px; color: var(--text); font-weight: 700; max-width: 108px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.main-content { background: transparent; padding: 0; overflow-y: auto; flex: 1; }
.page-fade-enter-active, .page-fade-leave-active { transition: opacity .2s, transform .2s; }
.page-fade-enter-from { opacity: 0; transform: translateY(5px); }
.page-fade-leave-to { opacity: 0; transform: translateY(-5px); }

@media (max-width: 980px) {
  .status-badge { display: none; }
}
@media (max-width: 840px) {
  .sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 30;
    width: 276px !important;
    transform: translateX(-102%);
    transition: transform .24s ease;
  }
  .sidebar.mobile-open { transform: translateX(0); }
  .sidebar-mask {
    position: fixed;
    inset: 0;
    z-index: 29;
    border: 0;
    background: rgba(23,32,51,.32);
    backdrop-filter: blur(2px);
  }
  .topbar { padding: 0 14px; }
  .crumb > span, .crumb > .el-icon { display: none; }
  .course-context span { display: none; }
  .username { display: none; }
}
</style>
