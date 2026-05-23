<template>
  <div class="strategy-config-page">
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
            :type="strategy.active ? 'success' : 'info'"
            size="small"
          >
            {{ strategy.active ? '已激活' : '未激活' }}
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
            :max="activeStrategyCount"
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
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

interface Strategy {
  id: string
  name: string
  category: string
  description: string
  active: boolean
  params: Record<string, number | string>
  stopLoss?: number
  takeProfit?: number
  maxPosition?: number
}

// 策略列表
const strategies = ref<Strategy[]>([
  {
    id: '1',
    name: 'MA 双均线',
    category: '趋势跟踪',
    description: '快慢均线交叉信号',
    active: true,
    params: { 快线: 5, 慢线: 20 },
    stopLoss: 5,
    takeProfit: 15,
    maxPosition: 5
  },
  {
    id: '2',
    name: 'RSI 反转',
    category: '均值回归',
    description: '超买超卖反转',
    active: true,
    params: { 周期: 14, '超买/卖': '70/30' },
    stopLoss: 3,
    takeProfit: 10,
    maxPosition: 3
  },
  {
    id: '3',
    name: '布林带突破',
    category: '波动率突破',
    description: '带宽收缩扩张',
    active: false,
    params: { 周期: 20, 标准差: 2.0 },
    stopLoss: 4,
    takeProfit: 12,
    maxPosition: 4
  },
  {
    id: '4',
    name: '海龟交易',
    category: '趋势跟踪',
    description: 'Donchian通道突破',
    active: false,
    params: { 入场: '20日', 出场: '10日' },
    stopLoss: 6,
    takeProfit: 20,
    maxPosition: 3
  },
  {
    id: '5',
    name: '动量策略',
    category: '趋势跟踪',
    description: '价格动量排序',
    active: false,
    params: { 回顾期: '60日', 持有: '20日' },
    stopLoss: 5,
    takeProfit: 15,
    maxPosition: 5
  }
])

// 组合模式
const combineMode = ref<'and' | 'vote' | 'or'>('vote')
const voteThreshold = ref(2)

// 激活策略数量
const activeStrategyCount = computed(() => {
  return strategies.value.filter(s => s.active).length
})

// 投票标记
const voteMarks = computed(() => {
  const marks: Record<number, string> = {}
  for (let i = 1; i <= activeStrategyCount.value; i++) {
    marks[i] = i.toString()
  }
  return marks
})

// 编辑对话框
const editDialogVisible = ref(false)
const currentStrategy = ref<Strategy | null>(null)
const editForm = reactive<Partial<Strategy>>({
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
const editStrategy = (strategy: Strategy) => {
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
const saveStrategy = () => {
  if (currentStrategy.value) {
    Object.assign(currentStrategy.value, editForm)
    ElMessage.success('策略配置已保存')
    editDialogVisible.value = false
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
const addStrategy = () => {
  if (!addForm.template || !addForm.name) {
    ElMessage.warning('请填写完整信息')
    return
  }

  const newStrategy: Strategy = {
    id: Date.now().toString(),
    name: addForm.name,
    category: '自定义',
    description: addForm.description,
    active: false,
    params: {},
    stopLoss: 5,
    takeProfit: 15,
    maxPosition: 5
  }

  strategies.value.push(newStrategy)
  ElMessage.success('策略已添加')
  addDialogVisible.value = false
}

// 保存组合配置
const saveCombineConfig = () => {
  ElMessage.success('组合配置已保存')
}
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
