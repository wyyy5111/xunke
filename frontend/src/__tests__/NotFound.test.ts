import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import NotFound from '@/views/public/NotFound.vue'

describe('NotFound', () => {
  it('shows an actionable non-empty state', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/missing', component: NotFound },
        { path: '/login', component: { template: '<div>登录</div>' } }
      ]
    })
    await router.push('/missing')
    await router.isReady()
    const wrapper = mount(NotFound, { global: { plugins: [createPinia(), router, ElementPlus] } })
    expect(wrapper.text()).toContain('404')
    expect(wrapper.text()).toContain('返回工作台')
  })
})
