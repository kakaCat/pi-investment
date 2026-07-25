import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import AccountSwitcher from '@/components/AccountSwitcher.vue'

const simulationApiMock = vi.hoisted(() => ({
  listAccounts: vi.fn(),
  createAccount: vi.fn()
}))

vi.mock('@/services/api/simulation', () => ({ simulationApi: simulationApiMock }))

const ACCOUNTS = [
  { account_name: 'v13_simulation', display_name: 'V13 多因子模拟仓', strategy_name: 'v13', status: 'active', cash_available: 110000, cash_frozen: 0, position_value: 37000, total_value: 147000, cumulative_return: 0.47, positions_count: 1 },
  { account_name: 'v14_simulation', display_name: 'V14 模拟仓', strategy_name: 'v14', status: 'active', cash_available: 101873, cash_frozen: 0, position_value: 0, total_value: 144859, cumulative_return: 0.45, positions_count: 5 }
]

describe('AccountSwitcher', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    simulationApiMock.listAccounts.mockResolvedValue({ accounts: ACCOUNTS, total: 2 })
  })

  it('挂载后加载账户列表并默认选中第一个', async () => {
    const wrapper = mount(AccountSwitcher)
    await nextTick(); await nextTick()
    expect(simulationApiMock.listAccounts).toHaveBeenCalled()
    expect(wrapper.vm.selected).toBe('v13_simulation')
    expect(wrapper.emitted('change')?.[0]).toEqual(['v13_simulation', ACCOUNTS[0]])
  })

  it('切换账户时 emit change', async () => {
    const wrapper = mount(AccountSwitcher)
    await nextTick(); await nextTick()
    wrapper.vm.selected = 'v14_simulation'
    await nextTick()
    const events = wrapper.emitted('change')!
    expect(events[events.length - 1]).toEqual(['v14_simulation', ACCOUNTS[1]])
  })

  it('开户成功后刷新列表并选中新账户', async () => {
    simulationApiMock.createAccount.mockResolvedValue({ account_name: 'new_acc' })
    const wrapper = mount(AccountSwitcher)
    await nextTick(); await nextTick()
    await wrapper.vm.openCreateDialog()
    wrapper.vm.createForm.account_name = 'new_acc'
    wrapper.vm.createForm.initial_capital = 50000
    await wrapper.vm.submitCreate()
    expect(simulationApiMock.createAccount).toHaveBeenCalledWith(
      expect.objectContaining({ account_name: 'new_acc', initial_capital: 50000 }))
  })
})
