import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'

const payload = {
  user: {
    id: 7,
    username: 'student',
    email: 'student@test.local',
    role: 'student',
    full_name: '演示学生',
    student_no: 'S2026001',
    learning_goal: '理解课程核心概念',
    weekly_hours: 8,
    learning_preferences: '视觉图解,实践演练',
    avatar: '',
    is_active: true
  },
  learning_goal: '理解课程核心概念',
  weekly_hours: 8,
  learning_preferences: ['视觉图解', '实践演练'],
  courses: [
    { course_id: 7, name: '教育研究方法', code: 'EDU-2026', goal: '完成研究设计', weekly_hours: 8 }
  ]
}

const settingsMock = vi.hoisted(() => vi.fn())
const updateSettingsMock = vi.hoisted(() => vi.fn())
vi.mock('@/api', () => ({
  auth: {
    settings: settingsMock,
    updateSettings: updateSettingsMock
  }
}))

import StudentSettings from '@/views/student/Settings.vue'

describe('StudentSettings', () => {
  it('loads persisted settings and saves the selected course strategy', async () => {
    settingsMock.mockResolvedValue(structuredClone(payload))
    updateSettingsMock.mockResolvedValue(structuredClone(payload))
    localStorage.setItem('xunkeflow_cid', '7')
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/student/settings', component: StudentSettings },
        { path: '/courses', component: { template: '<div>课程中心</div>' } }
      ]
    })
    await router.push('/student/settings')
    await router.isReady()
    const wrapper = mount(StudentSettings, {
      global: {
        plugins: [createPinia(), router, ElementPlus],
        components: ElementPlusIconsVue
      }
    })

    await flushPromises()
    expect(wrapper.text()).toContain('个人设置')
    expect(wrapper.text()).toContain('教育研究方法')
    expect(wrapper.text()).toContain('视觉图解')
    expect(wrapper.text()).toContain('实践演练')

    const saveButton = wrapper.findAll('button').find((item) => item.text().includes('保存个人设置'))
    expect(saveButton).toBeTruthy()
    await saveButton!.trigger('click')
    await flushPromises()

    expect(updateSettingsMock).toHaveBeenCalledWith({
      full_name: '演示学生',
      email: 'student@test.local',
      course_id: 7,
      learning_goal: '完成研究设计',
      weekly_hours: 8,
      learning_preferences: ['视觉图解', '实践演练']
    })
  })
})
