import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'

const loginMock = vi.hoisted(() => vi.fn())
vi.mock('@/api', () => ({
  auth: {
    login: loginMock,
    me: vi.fn()
  },
  system: {
    info: vi.fn(async () => ({ demo_mode: true }))
  }
}))

import Login from '@/views/public/Login.vue'

describe('Login', () => {
  it('submits the demo account once and enters the role workspace', async () => {
    loginMock.mockResolvedValue({
      access_token: 'unit-test-token',
      user: {
        id: 1,
        username: 'admin',
        email: 'admin@test.local',
        role: 'admin',
        full_name: '管理员',
        student_no: '',
        avatar: '',
        is_active: true
      }
    })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/login', component: Login },
        { path: '/admin', component: { template: '<div>管理员工作台</div>' } },
        { path: '/register', component: { template: '<div>注册</div>' } },
        { path: '/intro', component: { template: '<div>介绍</div>' } }
      ]
    })
    await router.push('/login')
    await router.isReady()
    const wrapper = mount(Login, {
      global: {
        plugins: [createPinia(), router, ElementPlus],
        components: ElementPlusIconsVue
      }
    })

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(loginMock).toHaveBeenCalledTimes(1)
    expect(loginMock).toHaveBeenCalledWith({ username: 'admin', password: '123456' })
    expect(router.currentRoute.value.path).toBe('/admin')
  })
})
