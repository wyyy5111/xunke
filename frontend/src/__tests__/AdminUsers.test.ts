import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const usersMock = vi.hoisted(() => vi.fn())
const updateRoleMock = vi.hoisted(() => vi.fn())
const updateUserMock = vi.hoisted(() => vi.fn())

vi.mock('@/api', () => ({
  admin: {
    users: usersMock,
    updateRole: updateRoleMock,
    updateUser: updateUserMock,
  },
  auth: {
    login: vi.fn(),
    me: vi.fn(),
  },
  system: {
    info: vi.fn(),
  },
}))

import AdminUsers from '@/views/admin/Users.vue'

const accounts = [
  {
    id: 1,
    username: 'admin',
    full_name: '系统管理员',
    email: 'admin@example.com',
    role: 'admin',
    is_active: true,
    created_at: '2026-07-11T09:00:00',
  },
  {
    id: 2,
    username: 'teacher',
    full_name: '课程教师',
    email: 'teacher@example.com',
    role: 'teacher',
    is_active: true,
    created_at: '2026-07-11T09:10:00',
  },
]

describe('administrator user governance', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('xunkeflow_token', 'admin-test-token')
    localStorage.setItem('xunkeflow_user', JSON.stringify(accounts[0]))
    usersMock.mockReset().mockResolvedValue(accounts)
    updateRoleMock.mockReset().mockResolvedValue({ ...accounts[1], role: 'student' })
    updateUserMock.mockReset().mockResolvedValue(accounts[1])
  })

  it('confirms and submits a role change while protecting the current account in UI', async () => {
    const wrapper = mount(AdminUsers, {
      global: {
        plugins: [createPinia(), ElementPlus],
        components: ElementPlusIconsVue,
      },
    })
    await flushPromises()

    expect(wrapper.find('[data-testid="role-action-1"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('当前账号')

    await wrapper.get('[data-testid="role-action-2"]').trigger('click')
    await flushPromises()
    const roleGroup = wrapper.findComponent({ name: 'ElRadioGroup' })
    expect(roleGroup.exists()).toBe(true)
    roleGroup.vm.$emit('update:modelValue', 'student')
    await wrapper.vm.$nextTick()
    await wrapper.get('[data-testid="confirm-role"]').trigger('click')
    await flushPromises()

    expect(updateRoleMock).toHaveBeenCalledTimes(1)
    expect(updateRoleMock).toHaveBeenCalledWith(2, 'student')
    expect(usersMock).toHaveBeenCalledTimes(2)
  })
})
