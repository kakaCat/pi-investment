<template>
  <div class="account-switcher">
    <el-select
      v-model="selected"
      placeholder="选择账户"
      style="width: 320px"
    >
      <el-option
        v-for="acc in accounts"
        :key="acc.account_name"
        :label="`${acc.display_name || acc.account_name}（¥${formatWan(acc.total_value)}）`"
        :value="acc.account_name"
      >
        <div class="account-option">
          <span>{{ acc.display_name || acc.account_name }}</span>
          <span class="account-option-meta">
            ¥{{ formatWan(acc.total_value) }}
            <el-tag v-if="acc.strategy_name" size="small" type="info">{{ acc.strategy_name }}</el-tag>
          </span>
        </div>
      </el-option>
      <template #footer>
        <el-button text type="primary" size="small" @click="openCreateDialog">+ 开户</el-button>
      </template>
    </el-select>

    <el-dialog v-model="createVisible" title="开立模拟账户" width="420px">
      <el-form label-width="90px">
        <el-form-item label="账户名" required>
          <el-input v-model="createForm.account_name" placeholder="如 manual_test（禁止 default）" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="createForm.display_name" placeholder="如 手工测试仓" />
        </el-form-item>
        <el-form-item label="初始资金" required>
          <el-input-number v-model="createForm.initial_capital" :min="1000" :step="10000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="绑定策略">
          <el-input v-model="createForm.strategy_name" placeholder="可选，如 v13" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { simulationApi } from '@/services/api/simulation'
import type { AccountSummary } from '@/services/api/simulation'

const props = defineProps<{ initialAccount?: string }>()
const emit = defineEmits<{ (e: 'change', accountName: string, account: AccountSummary): void }>()

const accounts = ref<AccountSummary[]>([])
const selected = ref<string>('')
const createVisible = ref(false)
const creating = ref(false)
const createForm = reactive({
  account_name: '',
  display_name: '',
  initial_capital: 100000,
  strategy_name: ''
})

function formatWan(v: number) {
  return (v / 10000).toFixed(1) + '万'
}

async function loadAccounts(selectName?: string) {
  try {
    const res = await simulationApi.listAccounts()
    accounts.value = res.accounts
    const target = selectName
      || (props.initialAccount && accounts.value.find(a => a.account_name === props.initialAccount)?.account_name)
      || accounts.value[0]?.account_name
    if (target) {
      selected.value = target  // watch 会触发 onChange → emit('change')
    }
  } catch {
    ElMessage.error('加载账户列表失败')
  }
}

function onChange(name: string) {
  const acc = accounts.value.find(a => a.account_name === name)
  if (acc) emit('change', name, acc)
}

// watch 而非 @change：编程式赋值（初始预选/开户后选中）同样触发
watch(selected, (name) => { if (name) onChange(name) })

async function openCreateDialog() {
  createVisible.value = true
}

async function submitCreate() {
  if (!createForm.account_name || createForm.account_name === 'default') {
    ElMessage.warning('账户名必填且不能为 default')
    return
  }
  creating.value = true
  try {
    await simulationApi.createAccount({
      account_name: createForm.account_name,
      display_name: createForm.display_name || undefined,
      initial_capital: createForm.initial_capital,
      strategy_name: createForm.strategy_name || undefined
    })
    ElMessage.success('开户成功')
    createVisible.value = false
    await loadAccounts(createForm.account_name)
  } catch (err: any) {
    ElMessage.error(`开户失败: ${err?.message || '未知错误'}`)
  } finally {
    creating.value = false
  }
}

onMounted(() => loadAccounts())

defineExpose({ selected, accounts, createForm, openCreateDialog, submitCreate, loadAccounts })
</script>

<style scoped>
.account-switcher { display: inline-block; }
.account-option { display: flex; justify-content: space-between; align-items: center; }
.account-option-meta { color: #999; font-size: 12px; display: flex; gap: 6px; align-items: center; }
</style>
