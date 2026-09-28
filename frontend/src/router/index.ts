import { createRouter, createWebHashHistory, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { IS_SHOWCASE } from '@/config/runtime'
import { useUserStore } from '@/stores/user'
import { homeForRole } from './guards'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/dashboard' },
  { path: '/login', name: 'login', component: () => import('@/views/public/Login.vue') },
  { path: '/register', name: 'register', component: () => import('@/views/public/Register.vue') },
  { path: '/intro', name: 'intro', component: () => import('@/views/public/Intro.vue') },
  { path: '/403', name: 'forbidden', component: () => import('@/views/public/Forbidden.vue') },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('@/views/public/Dashboard.vue'), meta: { roles: ['student', 'teacher', 'admin'] } },
      { path: 'courses', name: 'courses', component: () => import('@/views/public/CourseList.vue'), meta: { roles: ['student', 'teacher', 'admin'] } },
      // 学生
      { path: 'student', name: 'studentHome', component: () => import('@/views/student/Home.vue'), meta: { roles: ['student'] } },
      { path: 'student/settings', name: 'studentSettings', component: () => import('@/views/student/Settings.vue'), meta: { roles: ['student'] } },
      { path: 'student/pretest/:cid', name: 'preTest', component: () => import('@/views/student/PreTest.vue'), meta: { roles: ['student'] } },
      { path: 'student/profile/:cid', name: 'studentProfile', component: () => import('@/views/student/Profile.vue'), meta: { roles: ['student'] } },
      { path: 'student/path/:cid', name: 'learningPath', component: () => import('@/views/student/LearningPath.vue'), meta: { roles: ['student'] } },
      { path: 'student/lecture/:cid', name: 'lecture', component: () => import('@/views/student/Lecture.vue'), meta: { roles: ['student'] } },
      { path: 'student/mindmap/:cid', name: 'studentMindmap', component: () => import('@/views/student/MindMap.vue'), meta: { roles: ['student'] } },
      { path: 'student/exercise/:cid', name: 'exercise', component: () => import('@/views/student/Exercise.vue'), meta: { roles: ['student'] } },
      { path: 'student/wrong/:cid', name: 'wrongBook', component: () => import('@/views/student/WrongBook.vue'), meta: { roles: ['student'] } },
      { path: 'student/posttest/:cid', name: 'postTest', component: () => import('@/views/student/PostTest.vue'), meta: { roles: ['student'] } },
      { path: 'student/compare/:cid', name: 'compare', component: () => import('@/views/student/Compare.vue'), meta: { roles: ['student'] } },
      { path: 'student/report/:cid', name: 'studentReport', component: () => import('@/views/student/Report.vue'), meta: { roles: ['student'] } },
      { path: 'student/agents/:cid', name: 'studentAgents', component: () => import('@/views/student/Agents.vue'), meta: { roles: ['student'] } },
      // 教师
      { path: 'teacher', name: 'teacherHome', component: () => import('@/views/teacher/Home.vue'), meta: { roles: ['teacher', 'admin'] } },
      { path: 'teacher/courses', name: 'teacherCourses', component: () => import('@/views/teacher/Courses.vue'), meta: { roles: ['teacher', 'admin'] } },
      { path: 'teacher/upload/:cid', name: 'upload', component: () => import('@/views/teacher/Upload.vue'), meta: { roles: ['teacher', 'admin'] } },
      { path: 'teacher/knowledge/:cid', name: 'knowledgeMgmt', component: () => import('@/views/teacher/Knowledge.vue'), meta: { roles: ['teacher', 'admin'] } },
      { path: 'teacher/graph/:cid', name: 'teacherGraph', component: () => import('@/views/teacher/Graph.vue'), meta: { roles: ['teacher', 'admin'] } },
      { path: 'teacher/review/:cid', name: 'review', component: () => import('@/views/teacher/Review.vue'), meta: { roles: ['teacher', 'admin'] } },
      { path: 'teacher/questions/:cid', name: 'questionBank', component: () => import('@/views/teacher/QuestionBank.vue'), meta: { roles: ['teacher', 'admin'] } },
      { path: 'teacher/dashboard/:cid', name: 'classDashboard', component: () => import('@/views/teacher/ClassDashboard.vue'), meta: { roles: ['teacher', 'admin'] } },
      { path: 'teacher/generate/:cid', name: 'generate', component: () => import('@/views/teacher/Generate.vue'), meta: { roles: ['teacher', 'admin'] } },
      { path: 'teacher/agents', name: 'teacherAgents', component: () => import('@/views/teacher/Agents.vue'), meta: { roles: ['teacher', 'admin'] } },
      // 实验
      { path: 'experiment/:cid', name: 'experiment', component: () => import('@/views/teacher/Experiment.vue'), meta: { roles: ['teacher', 'admin', 'student'] } },
      // 管理员
      { path: 'admin', name: 'adminHome', component: () => import('@/views/admin/Home.vue'), meta: { roles: ['admin'] } },
      { path: 'admin/users', name: 'adminUsers', component: () => import('@/views/admin/Users.vue'), meta: { roles: ['admin'] } },
      { path: 'admin/configs', name: 'adminConfigs', component: () => import('@/views/admin/Configs.vue'), meta: { roles: ['admin'] } },
      { path: 'admin/agents', name: 'adminAgents', component: () => import('@/views/admin/Agents.vue'), meta: { roles: ['admin'] } },
      { path: 'admin/logs', name: 'adminLogs', component: () => import('@/views/admin/Logs.vue'), meta: { roles: ['admin'] } },
    ]
  },
  { path: '/:pathMatch(.*)*', name: 'notFound', component: () => import('@/views/public/NotFound.vue') }
]

const router = createRouter({
  history: IS_SHOWCASE ? createWebHashHistory(import.meta.env.BASE_URL) : createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach(async (to) => {
  const store = useUserStore()
  if (to.meta.roles && (to.meta.roles as string[]).length) {
    if (!store.isLogin) return { path: '/login', query: { redirect: to.fullPath } }
    if (!store.user) {
      const ok = await store.fetchMe()
      if (!ok) return { path: '/login', query: { redirect: to.fullPath } }
    }
    if (!(to.meta.roles as string[]).includes(store.role)) {
      return { path: '/403', query: { from: to.fullPath } }
    }
  }
  if ((to.path === '/login' || to.path === '/register') && store.isLogin && store.user) {
    return homeForRole(store.role)
  }
  return true
})

export default router
