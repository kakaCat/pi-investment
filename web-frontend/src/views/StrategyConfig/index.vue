<template>
  <div class="strategy-config-page" v-loading="loading">
    <!-- 策略卡片网格 -->
    <div class="grid grid-cols-3 gap-4 mb-4">
      <el-card
        v-for="strategy in strategies"
        :key="strategy.id"
        shadow="hover"
        class="strategy-card"
      >
        <div class="mb-3">
          <h3 class="text-base font-semibold mb-1">{{ strategy.name }}</h3>
          <p class="text-xs text-gray-400">{{ strategy.category }} · {{ strategy.description }}</p>
        </div>

        <div class="grid grid-cols-2 gap-2 text-xs mb-3">
          <div
            v-for="(value, key) in strategy.params"
            :key="key"
            class="bg-gray-50 px-2 py-1 rounded"
          >
            <span class="text-gray-400">{{ key }}</span>
            <span class="font-medium ml-1">{{ value }}</span>
          </div>
        </div>

        <div class="flex items-center justify-between">
          <el-tag
            :type="strategy.active || strategy.status === 'running' ? 'success' : 'info'"
            size="small"
          >
            {{ strategy.active || strategy.status === 'running' ? '已激活' : '未激活' }}
          </el-tag>
          <el-button type="primary" link @click="editStrategy(strategy)">
            编辑参数
          </el-button>
        </div>
      </el-card>

      <!-- 添加新策略卡片 -->
      <el-card
        shadow="hover"
        class="add-strategy-card cursor-pointer"
        @click="showAddDialog"
      >
        <div class="flex flex-col items-center justify-center h-full text-center">
          <div class="w-10 h-10 bg-gray-100 rounded-full flex items-center justify-center mb-2">
            <el-icon :size="20" color="#9ca3af"><Plus /></el-icon>
          </div>
          <span class="text-sm text-gray-400 font-medium">添加新策略</span>
        </div>
      </el-card>
    </div>

    <!-- 多策略组合配置 -->
    <el-card shadow="never">
      <h3 class="text-base font-semibold mb-2">多策略组合配置</h3>
      <p class="text-xs text-gray-400 mb-4">多个激活策略的投票规则和权重</p>

      <div class="grid grid-cols-3 gap-4">
        <div
          class="rounded-lg p-4 text-center cursor-pointer transition-all"
          :class="combineMode === 'and' ? 'bg-blue-50 ring-2 ring-blue-300' : 'bg-gray-50 hover:bg-gray-100'"
          @click="combineMode = 'and'"
        >
          <div class="text-2xl font-bold mb-1" :class="combineMode === 'and' ? 'text-blue-700' : 'text-gray-800'">
            AND
          </div>
          <div class="text-xs" :class="combineMode === 'and' ? 'text-blue-600' : 'text-gray-500'">
            所有策略一致才出信号
          </div>
          <div class="text-xs mt-1" :class="combineMode === 'and' ? 'text-blue-500' : 'text-gray-400'">
            {{ combineMode === 'and' ? '当前: 已启用' : '当前: 未启用' }}
          </div>
        </div>

        <div
          class="rounded-lg p-4 text-center cursor-pointer transition-all"
          :class="combineMode === 'vote' ? 'bg-blue-50 ring-2 ring-blue-300' : 'bg-gray-50 hover:bg-gray-100'"
          @click="combineMode = 'vote'"
        >
          <div class="text-2xl font-bold mb-1" :class="combineMode === 'vote' ? 'text-blue-700' : 'text-gray-800'">
            VOTE
          </div>
          <div class="text-xs" :class="combineMode === 'vote' ? 'text-blue-600' : 'text-gray-500'">
            多数投票制
          </div>
          <div class="text-xs mt-1" :class="combineMode === 'vote' ? 'text-blue-500' : 'text-gray-400'">
            {{ combineMode === 'vote' ? `当前: ≥${voteThreshold}票出信号` : '当前: 未启用' }}
          </div>
        </div>

        <div
          class="rounded-lg p-4 text-center cursor-pointer transition-all"
          :class="combineMode === 'or' ? 'bg-blue-50 ring-2 ring-blue-300' : 'bg-gray-50 hover:bg-gray-100'"
          @click="combineMode = 'or'"
        >
          <div class="text-2xl font-bold mb-1" :class="combineMode === 'or' ? 'text-blue-700' : 'text-gray-800'">
            OR
          </div>
          <div class="text-xs" :class="combineMode === 'or' ? 'text-blue-600' : 'text-gray-500'">
            任一策略出信号即触发
          </div>
          <div class="text-xs mt-1" :class="combineMode === 'or' ? 'text-blue-500' : 'text-gray-400'">
            {{ combineMode === 'or' ? '当前: 已启用' : '当前: 未启用' }}
          </div>
        </div>
      </div>

      <!-- 投票阈值设置 -->
      <div v-if="combineMode === 'vote'" class="mt-4 p-4 bg-blue-50 rounded-lg">
        <div class="flex items-center gap-4">
          <span class="text-sm font-medium">投票阈值:</span>
          <el-slider
            v-model="voteThreshold"
            :min="1"
            :max="Math.max(1, activeStrategyCount)"
            :marks="voteMarks"
            show-stops
            style="width: 300px"
          />
          <span class="text-sm text-gray-600">需要至少 {{ voteThreshold }} 个策略同意</span>
        </div>
      </div>

      <div class="mt-4 flex justify-end">
        <el-button type="primary" @click="saveCombineConfig">保存配置</el-button>
      </div>
    </el-card>

    <!-- 编辑策略对话框 -->
    <el-dialog
      v-model="editDialogVisible"
      :title="`编辑策略: ${currentStrategy?.name}`"
      width="600px"
    >
      <el-form v-if="currentStrategy" :model="editForm" label-width="100px">
        <el-form-item label="策略名称">
          <el-input v-model="editForm.name" />
        </el-form-item>

        <el-form-item label="策略描述">
          <el-input v-model="editForm.description" type="textarea" :rows="2" />
        </el-form-item>

        <el-form-item label="是否激活">
          <el-switch v-model="editForm.active" />
        </el-form-item>

        <el-divider>策略参数</el-divider>

        <el-form-item
          v-for="(_value, key) in editForm.params || {}"
          :key="key"
          :label="key"
        >
          <el-input-number
            v-model="editForm.params![key]"
            :min="0"
            :max="1000"
            style="width: 100%"
          />
        </el-form-item>

        <el-divider>风控参数</el-divider>

        <el-form-item label="止损比例(%)">
          <el-input-number
            v-model="editForm.stopLoss"
            :min="0"
            :max="50"
            :step="0.5"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="止盈比例(%)">
          <el-input-number
            v-model="editForm.takeProfit"
            :min="0"
            :max="100"
            :step="1"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="最大持仓">
          <el-input-number
            v-model="editForm.maxPosition"
            :min="1"
            :max="20"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveStrategy">保存</el-button>
      </template>
    </el-dialog>

    <!-- 添加策略对话框 -->
    <el-dialog
      v-model="addDialogVisible"
      title="添加新策略"
      width="600px"
    >
      <el-form :model="addForm" label-width="100px">
        <el-form-item label="策略模板">
          <el-select v-model="addForm.template" placeholder="选择策略模板" style="width: 100%">
            <el-option label="MA 双均线" value="ma" />
            <el-option label="RSI 反转" value="rsi" />
            <el-option label="MACD 金叉" value="macd" />
            <el-option label="布林带突破" value="boll" />
            <el-option label="海龟交易" value="turtle" />
            <el-option label="动量策略" value="momentum" />
          </el-select>
        </el-form-item>

        <el-form-item label="策略名称">
          <el-input v-model="addForm.name" placeholder="自定义策略名称" />
        </el-form-item>

        <el-form-item label="策略描述">
          <el-input v-model="addForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="addStrategy">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { strategyApi } from '@/services/api'
import type { Strategy } from '@/types'

interface StrategyConfig extends Strategy {
  category?: string
  active?: boolean
  stopLoss?: number
  takeProfit?: number
  maxPosition?: number
}

// 策略列表
const strategies = ref<StrategyConfig[]>([])
const loading = ref(false)

// 组合模式
const combineMode = ref<'and' | 'vote' | 'or'>('vote')
const voteThreshold = ref(2)

// 激活策略数量
const activeStrategyCount = computed(() => {
  return strategies.value.filter(s => s.active || s.status === 'running').length
})

// 投票标记
const voteMarks = computed(() => {
  const marks: Record<number, string> = {}
  for (let i = 1; i <= activeStrategyCount.value; i++) {
    marks[i] = i.toString()
  }
  return marks
})

// 加载策略配置
const loadConfig = async () => {
  loading.value = true
  try {
    const response = await strategyApi.getStrategies({
      page: 1,
      pageSize: 100
    })

    // 转换后端数据为前端格式
    strategies.value = (response.items || []).map(item => ({
      ...item,
      category: getCategoryFromType(item.type),
      active: item.status === 'running',
      params: item.params || {},
      stopLoss: item.params?.stopLoss || 5,
      takeProfit: item.params?.takeProfit || 15,
      maxPosition: item.params?.maxPosition || 5
    }))
  } catch (error) {
    console.error('加载策略配置失败:', error)
    ElMessage.error('加载策略配置失败')
  } finally {
    loading.value = false
  }
}

// 类型映射到分类
const getCategoryFromType = (type: string): string => {
  const categoryMap: Record<string, string> = {
    trend: '趋势跟踪',
    momentum: '动量策略',
    meanReversion: '均值回归',
    arbitrage: '套利策略',
    volatility: '波动率突破'
  }
  return categoryMap[type] || '自定义'
}

// 编辑对话框
const editDialogVisible = ref(false)
const currentStrategy = ref<StrategyConfig | null>(null)
const editForm = reactive<Partial<StrategyConfig>>({
  name: '',
  description: '',
  active: false,
  params: {},
  stopLoss: 0,
  takeProfit: 0,
  maxPosition: 0
})

// 添加对话框
const addDialogVisible = ref(false)
const addForm = reactive({
  template: '',
  name: '',
  description: ''
})

// 编辑策略
const editStrategy = (strategy: StrategyConfig) => {
  currentStrategy.value = strategy
  Object.assign(editForm, {
    name: strategy.name,
    description: strategy.description,
    active: strategy.active,
    params: { ...strategy.params },
    stopLoss: strategy.stopLoss,
    takeProfit: strategy.takeProfit,
    maxPosition: strategy.maxPosition
  })
  editDialogVisible.value = true
}

// 保存策略
const saveStrategy = async () => {
  if (!currentStrategy.value) return

  try {
    // 合并参数
    const updatedParams = {
      ...editForm.params,
      stopLoss: editForm.stopLoss,
      takeProfit: editForm.takeProfit,
      maxPosition: editForm.maxPosition
    }

    await strategyApi.updateStrategy({
      id: currentStrategy.value.id,
      name: editForm.name,
      description: editForm.description,
      parameters: updatedParams
    })

    // 如果激活状态改变，启动或停止策略
    if (editForm.active !== currentStrategy.value.active) {
      if (editForm.active) {
        await strategyApi.startStrategy(currentStrategy.value.id)
      } else {
        await strategyApi.stopStrategy(currentStrategy.value.id)
      }
    }

    ElMessage.success('策略配置已保存')
    editDialogVisible.value = false
    await loadConfig() // 重新加载配置
  } catch (error) {
    console.error('保存策略失败:', error)
    ElMessage.error('保存策略失败')
  }
}

// 显示添加对话框
const showAddDialog = () => {
  addForm.template = ''
  addForm.name = ''
  addForm.description = ''
  addDialogVisible.value = true
}

// 添加策略
const addStrategy = async () => {
  if (!addForm.template || !addForm.name) {
    ElMessage.warning('请填写完整信息')
    return
  }

  try {
    // 根据模板生成策略代码
    const templateCode = getTemplateCode(addForm.template)

    await strategyApi.createStrategy({
      name: addForm.name,
      description: addForm.description,
      code: templateCode,
      type: addForm.template,
      parameters: {
        stopLoss: 5,
        takeProfit: 15,
        maxPosition: 5
      },
      riskLevel: 'medium'
    })

    ElMessage.success('策略已添加')
    addDialogVisible.value = false
    await loadConfig() // 重新加载配置
  } catch (error) {
    console.error('添加策略失败:', error)
    ElMessage.error('添加策略失败')
  }
}

// 获取模板代码
const getTemplateCode = (template: string): string => {
  const templates: Record<string, string> = {
    ma: '# MA双均线策略\ndef strategy():\n    pass',
    rsi: '# RSI反转策略\ndef strategy():\n    pass',
    macd: '# MACD金叉策略\ndef strategy():\n    pass',
    boll: '# 布林带突破策略\ndef strategy():\n    pass',
    turtle: '# 海龟交易策略\ndef strategy():\n    pass',
    momentum: '# 动量策略\ndef strategy():\n    pass'
  }
  return templates[template] || '# 自定义策略\ndef strategy():\n    pass'
}

// 保存组合配置
const saveCombineConfig = async () => {
  try {
    // TODO: 实现组合配置保存API
    // 目前仅本地保存
    localStorage.setItem('strategy_combine_mode', combineMode.value)
    localStorage.setItem('strategy_vote_threshold', voteThreshold.value.toString())
    ElMessage.success('组合配置已保存')
  } catch (error) {
    console.error('保存组合配置失败:', error)
    ElMessage.error('保存组合配置失败')
  }
}

// 页面加载时获取配置
onMounted(() => {
  loadConfig()

  // 加载组合配置
  const savedMode = localStorage.getItem('strategy_combine_mode')
  if (savedMode) {
    combineMode.value = savedMode as 'and' | 'vote' | 'or'
  }

  const savedThreshold = localStorage.getItem('strategy_vote_threshold')
  if (savedThreshold) {
    voteThreshold.value = parseInt(savedThreshold, 10)
  }
})
</script>

<style scoped>
.strategy-config-page {
  padding: 20px;
}

.strategy-card {
  min-height: 200px;
}

.add-strategy-card {
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed #e5e7eb;
  transition: all 0.3s;
}

.add-strategy-card:hover {
  background-color: #f9fafb;
  border-color: #d1d5db;
}
</style>
