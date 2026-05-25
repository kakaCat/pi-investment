<template>
  <div class="ml-engine-page">
    <!-- 训练和预测面板 -->
    <el-row :gutter="16" class="mb-4">
      <!-- 模型训练 -->
      <el-col :span="12">
        <el-card class="panel-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">模型训练</span>
            </div>
          </template>

          <el-form :model="trainForm" label-position="top" size="default">
            <el-form-item label="模型类型">
              <el-select v-model="trainForm.modelType" class="w-full">
                <el-option label="XGBoost" value="xgboost" />
                <el-option label="LightGBM" value="lightgbm" />
                <el-option label="Random Forest" value="random_forest" />
              </el-select>
            </el-form-item>

            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="训练起始">
                  <el-date-picker
                    v-model="trainForm.startDate"
                    type="date"
                    placeholder="选择日期"
                    class="w-full"
                    value-format="YYYY-MM-DD"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="训练结束">
                  <el-date-picker
                    v-model="trainForm.endDate"
                    type="date"
                    placeholder="选择日期"
                    class="w-full"
                    value-format="YYYY-MM-DD"
                  />
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="测试集比例">
              <el-slider
                v-model="trainForm.testRatio"
                :min="10"
                :max="40"
                :step="5"
                show-stops
                :marks="{ 10: '10%', 20: '20%', 30: '30%', 40: '40%' }"
              />
              <div class="text-xs text-slate-400 text-right mt-1">{{ trainForm.testRatio }}%</div>
            </el-form-item>

            <el-form-item label="股票范围 (可选，留空=全部)">
              <el-input
                v-model="trainForm.symbols"
                placeholder="如 600519.SH,000858.SZ"
                clearable
              />
            </el-form-item>

            <el-button
              type="primary"
              class="w-full"
              :loading="training"
              @click="handleTrain"
            >
              <el-icon class="mr-1"><Promotion /></el-icon>
              开始训练
            </el-button>
          </el-form>

          <!-- 训练进度 -->
          <div v-if="trainingProgress.show" class="mt-4">
            <el-divider />
            <div class="training-progress">
              <div class="flex items-center justify-between mb-2">
                <span class="text-sm font-medium">训练进度</span>
                <span class="text-sm text-slate-500">{{ trainingProgress.percent }}%</span>
              </div>
              <el-progress
                :percentage="trainingProgress.percent"
                :status="trainingProgress.status"
              />
              <div class="mt-2 text-xs text-slate-500">
                {{ trainingProgress.message }}
              </div>
            </div>
          </div>

          <!-- 训练日志 -->
          <div v-if="trainingLogs.length > 0" class="mt-4">
            <el-divider />
            <div class="training-logs">
              <div class="text-sm font-medium mb-2">训练日志</div>
              <div class="log-container">
                <div
                  v-for="(log, index) in trainingLogs"
                  :key="index"
                  class="log-item"
                >
                  <span class="log-time">{{ log.time }}</span>
                  <span class="log-message">{{ log.message }}</span>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- ML 预测 -->
      <el-col :span="12">
        <el-card class="panel-card">
          <template #header>
            <div class="card-header">
              <span class="card-title">ML 预测</span>
            </div>
          </template>

          <el-form :model="predictForm" label-position="top" size="default">
            <el-form-item label="模型">
              <el-select v-model="predictForm.modelId" class="w-full">
                <el-option
                  v-for="model in models"
                  :key="model.id"
                  :label="`${model.name} (${model.accuracy}%)`"
                  :value="model.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="目标股票">
              <el-input
                v-model="predictForm.symbols"
                placeholder="输入股票代码，逗号分隔"
                clearable
              />
            </el-form-item>

            <el-button
              type="success"
              class="w-full"
              :loading="predicting"
              @click="handlePredict"
            >
              <el-icon class="mr-1"><MagicStick /></el-icon>
              预测
            </el-button>
          </el-form>

          <!-- 预测结果 -->
          <div v-if="predictions.length > 0" class="mt-4">
            <el-divider />
            <div class="prediction-results">
              <div class="text-sm font-medium mb-3">预测结果</div>
              <div class="space-y-2">
                <div
                  v-for="pred in predictions"
                  :key="pred.symbol"
                  class="prediction-item"
                >
                  <div class="flex items-center justify-between">
                    <span class="font-medium">{{ pred.symbol }}</span>
                    <div class="flex items-center gap-3">
                      <span
                        :class="[
                          'font-semibold',
                          pred.direction === 'up' ? 'text-up' : 'text-down'
                        ]"
                      >
                        {{ pred.direction === 'up' ? '↑' : '↓' }}
                        {{ pred.direction.toUpperCase() }}
                        {{ pred.probability }}%
                      </span>
                      <span class="text-xs text-slate-400">
                        置信度 {{ pred.confidence.toFixed(2) }}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 评估结果 -->
          <div v-if="evaluation" class="mt-4">
            <el-divider />
            <div class="evaluation-results">
              <div class="text-sm font-medium mb-3">评估结果</div>
              <el-row :gutter="12">
                <el-col :span="12">
                  <div class="metric-item">
                    <div class="metric-label">准确率</div>
                    <div class="metric-value">{{ evaluation.accuracy }}%</div>
                  </div>
                </el-col>
                <el-col :span="12">
                  <div class="metric-item">
                    <div class="metric-label">精确率</div>
                    <div class="metric-value">{{ evaluation.precision }}%</div>
                  </div>
                </el-col>
                <el-col :span="12">
                  <div class="metric-item">
                    <div class="metric-label">召回率</div>
                    <div class="metric-value">{{ evaluation.recall }}%</div>
                  </div>
                </el-col>
                <el-col :span="12">
                  <div class="metric-item">
                    <div class="metric-label">F1分数</div>
                    <div class="metric-value">{{ evaluation.f1Score }}%</div>
                  </div>
                </el-col>
              </el-row>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 特征重要性 -->
    <el-card class="feature-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">特征重要性</span>
          <el-select v-model="selectedFeatureModel" size="small" style="width: 200px">
            <el-option
              v-for="model in models"
              :key="model.id"
              :label="model.name"
              :value="model.id"
            />
          </el-select>
        </div>
      </template>

      <div class="feature-importance-container">
        <div
          v-for="feature in featureImportance"
          :key="feature.name"
          class="feature-item"
        >
          <span class="feature-name">{{ feature.name }}</span>
          <div class="feature-bar-container">
            <div
              class="feature-bar"
              :style="{ width: `${feature.importance}%` }"
            />
          </div>
          <span class="feature-value">{{ feature.importance }}%</span>
        </div>
      </div>
    </el-card>

    <!-- 混淆矩阵 -->
    <el-card v-if="showConfusionMatrix" class="mt-4">
      <template #header>
        <div class="card-header">
          <span class="card-title">混淆矩阵</span>
        </div>
      </template>
      <div ref="confusionMatrixRef" class="chart-container" style="height: 400px;" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Promotion,
  MagicStick
} from '@element-plus/icons-vue'
import { useChart } from '@/composables/useChart'
import { mlApi } from '@/services/api/ml'
import type { MLModelInfo } from '@/services/api/ml'

// 类型定义
interface MLModel {
  id: string
  name: string
  type: string
  status: 'training' | 'ready' | 'failed'
  accuracy: number
  trainedAt: string
}

interface TrainingProgress {
  show: boolean
  percent: number
  status: 'success' | 'exception' | 'warning' | undefined
  message: string
}

interface TrainingLog {
  time: string
  message: string
}

interface Prediction {
  symbol: string
  direction: 'up' | 'down'
  probability: number
  confidence: number
}

interface Evaluation {
  accuracy: number
  precision: number
  recall: number
  f1Score: number
}

interface FeatureImportance {
  name: string
  importance: number
}

// 表单数据
const trainForm = reactive({
  modelType: 'xgboost',
  startDate: '2022-01-01',
  endDate: '2026-05-01',
  testRatio: 20,
  symbols: ''
})

const predictForm = reactive({
  modelId: '',
  symbols: '600519.SH,000858.SZ,300750.SZ'
})

// 状态
const training = ref(false)
const predicting = ref(false)
const models = ref<MLModel[]>([
  {
    id: 'xgboost-latest',
    name: 'XGBoost (latest)',
    type: 'xgboost',
    status: 'ready',
    accuracy: 78.5,
    trainedAt: '2026-05-20'
  },
  {
    id: 'xgboost-20260520',
    name: 'XGBoost v20260520',
    type: 'xgboost',
    status: 'ready',
    accuracy: 76.2,
    trainedAt: '2026-05-20'
  },
  {
    id: 'lightgbm-20260518',
    name: 'LightGBM v20260518',
    type: 'lightgbm',
    status: 'ready',
    accuracy: 75.8,
    trainedAt: '2026-05-18'
  }
])

const trainingProgress = reactive<TrainingProgress>({
  show: false,
  percent: 0,
  status: undefined,
  message: ''
})

const trainingLogs = ref<TrainingLog[]>([])
const predictions = ref<Prediction[]>([])
const evaluation = ref<Evaluation | null>(null)
const selectedFeatureModel = ref('xgboost-latest')
const showConfusionMatrix = ref(false)

const featureImportance = ref<FeatureImportance[]>([])

// 混淆矩阵图表
const { setOption: setConfusionMatrixOption } = useChart({
  autoResize: true
})

// 处理训练
const handleTrain = async () => {
  training.value = true
  trainingProgress.show = true
  trainingProgress.percent = 0
  trainingProgress.status = undefined
  trainingProgress.message = '准备训练数据...'
  trainingLogs.value = []

  const addLog = (message: string) => {
    trainingLogs.value.push({
      time: new Date().toLocaleTimeString(),
      message
    })
  }

  try {
    addLog('开始训练模型...')
    trainingProgress.percent = 20
    trainingProgress.message = '正在提交训练任务...'

    const result = await mlApi.train({
      modelType: trainForm.modelType as 'xgboost' | 'lightgbm' | 'randomforest',
      startDate: trainForm.startDate || undefined,
      endDate: trainForm.endDate || undefined,
      testSize: trainForm.testRatio / 100,
      symbols: trainForm.symbols
        ? trainForm.symbols.split(',').map(s => s.trim()).filter(Boolean)
        : undefined,
      params: {}
    })

    trainingProgress.percent = 100
    trainingProgress.status = 'success'
    trainingProgress.message = '训练完成！'
    addLog('模型训练完成')

    // 计算百分比显示值（后端返回 0-1 小数）
    const toPercent = (v: number) => Math.round(v * 1000) / 10

    // 添加新模型（使用后端返回的真实版本号）
    const backendVersion = result.version || `${new Date().toISOString().split('T')[0].replace(/-/g, '')}`
    const newModel: MLModel = {
      id: `${trainForm.modelType}-${backendVersion}`,
      name: `${trainForm.modelType.toUpperCase()} v${backendVersion}`,
      type: trainForm.modelType,
      status: 'ready',
      accuracy: toPercent(result.trainAccuracy || result.testAccuracy),
      trainedAt: new Date().toISOString().split('T')[0]
    }
    models.value.unshift(newModel)
    predictForm.modelId = newModel.id
    selectedFeatureModel.value = newModel.id

    // 显示评估结果
    evaluation.value = {
      accuracy: toPercent(result.trainAccuracy || result.testAccuracy),
      precision: toPercent(result.precision),
      recall: toPercent(result.recall),
      f1Score: toPercent(result.f1Score)
    }

    // 更新特征重要性（标准化：所有特征重要性之和为100%）
    if (result.featureImportance && Object.keys(result.featureImportance).length > 0) {
      const total = Object.values(result.featureImportance as Record<string, number>).reduce((s, v) => s + v, 0) || 1
      featureImportance.value = Object.entries(result.featureImportance)
        .map(([name, importance]) => ({
          name,
          importance: Math.round((importance / total) * 1000) / 10
        }))
        .sort((a, b) => b.importance - a.importance)
    }

    // 显示混淆矩阵
    showConfusionMatrix.value = true
    setTimeout(() => {
      renderConfusionMatrix()
    }, 100)

    ElMessage.success('模型训练完成！')
  } catch (error: any) {
    trainingProgress.status = 'exception'
    trainingProgress.message = '训练失败'
    addLog(`训练失败: ${error?.message || '未知错误'}`)
    ElMessage.error(error?.message || '训练失败')
  } finally {
    training.value = false
  }
}

// 处理预测
const handlePredict = async () => {
  if (!predictForm.modelId) {
    ElMessage.warning('请选择模型')
    return
  }

  if (!predictForm.symbols.trim()) {
    ElMessage.warning('请输入股票代码')
    return
  }

  predicting.value = true
  predictions.value = []

  try {
    const symbols = predictForm.symbols.split(',').map(s => s.trim()).filter(Boolean)
    if (symbols.length === 0) {
      ElMessage.warning('请输入有效的股票代码')
      return
    }

    // 从已选模型ID提取模型类型和版本 (id 格式: "{type}-{version}")
    const selectedModel = models.value.find(m => m.id === predictForm.modelId)
    const modelType = selectedModel?.type || 'xgboost'
    const version = predictForm.modelId.includes('-')
      ? predictForm.modelId.slice(predictForm.modelId.indexOf('-') + 1)
      : 'latest'

    const results = await mlApi.predict({
      modelType,
      symbols,
      version
    })

    // 置信度映射: 字符串 → 数值
    const confidenceMap: Record<string, number> = {
      high: 0.85,
      medium: 0.65,
      low: 0.5
    }

    predictions.value = results.map(p => ({
      symbol: p.symbol,
      direction: p.predictedClass === 1 ? 'up' : 'down',
      probability: Math.round(p.probability * 100),
      confidence: confidenceMap[p.confidence] ?? 0.5
    }))

    ElMessage.success('预测完成！')
  } catch (error: any) {
    ElMessage.error(error?.message || '预测失败')
  } finally {
    predicting.value = false
  }
}

// 渲染混淆矩阵
const renderConfusionMatrix = () => {
  const data = [
    [0, 0, 85],
    [0, 1, 12],
    [1, 0, 15],
    [1, 1, 88]
  ]

  const option = {
    tooltip: {
      position: 'top'
    },
    grid: {
      left: 100,
      right: 60,
      top: 60,
      bottom: 60
    },
    xAxis: {
      type: 'category' as const,
      data: ['预测下跌', '预测上涨'],
      splitArea: {
        show: true
      },
      axisLabel: {
        fontSize: 14
      }
    },
    yAxis: {
      type: 'category',
      data: ['实际下跌', '实际上涨'],
      splitArea: {
        show: true
      },
      axisLabel: {
        fontSize: 14
      }
    },
    visualMap: {
      min: 0,
      max: 100,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 10,
      inRange: {
        color: ['#e0f3ff', '#1890ff']
      }
    },
    series: [
      {
        name: '混淆矩阵',
        type: 'heatmap',
        data: data,
        label: {
          show: true,
          fontSize: 16,
          fontWeight: 'bold'
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }

  setConfusionMatrixOption(option as any)
}

// 加载中状态
const featuresLoading = ref(false)

// 监听模型选择变化，重新加载对应模型的特征重要性
watch(selectedFeatureModel, async (newModelId) => {
  const selectedModel = models.value.find(m => m.id === newModelId)
  if (selectedModel && selectedModel.status === 'ready') {
    try {
      const features = await mlApi.getFeatures(selectedModel.type)
      if (features.length > 0) {
        featureImportance.value = features
          .map(f => ({
            name: f.name,
            importance: Math.round(f.importance * 10) / 10
          }))
          .sort((a, b) => b.importance - a.importance)
      }
    } catch {
      // 静默失败，保留已有数据
    }
  }
})

onMounted(async () => {
  // 设置默认模型
  if (models.value.length > 0) {
    predictForm.modelId = models.value[0].id
  }

  // 加载特征重要性（API 已返回 0-100 百分比值）
  featuresLoading.value = true
  try {
    const features = await mlApi.getFeatures()
    if (features.length > 0) {
      featureImportance.value = features
        .map(f => ({
          name: f.name,
          importance: Math.round(f.importance * 10) / 10
        }))
        .sort((a, b) => b.importance - a.importance)
    }
  } catch {
    // 加载失败时保留空白
  } finally {
    featuresLoading.value = false
  }

  // 尝试加载已训练模型信息并更新模型列表
  for (const modelType of ['xgboost', 'lightgbm', 'randomforest'] as const) {
    try {
      const info: MLModelInfo | null = await mlApi.getModelInfo(modelType)
      if (info && info.version) {
        // 检查是否已存在同名模型
        const existingIdx = models.value.findIndex(
          m => m.type === modelType && m.name.includes(info.version)
        )
        const trainedModel: MLModel = {
          id: `${modelType}-${info.version}`,
          name: `${modelType.toUpperCase()} v${info.version}`,
          type: modelType,
          status: 'ready',
          accuracy: Math.round(info.accuracy * 1000) / 10,
          trainedAt: info.trainingDate ? info.trainingDate.slice(0, 10) : ''
        }
        if (existingIdx >= 0) {
          models.value[existingIdx] = trainedModel
        } else {
          models.value.push(trainedModel)
        }
      }
    } catch {
      // 静默失败
    }
  }
})
</script>

<style scoped lang="scss">
.ml-engine-page {
  padding: 24px;

  .panel-card {
    height: 100%;

    :deep(.el-card__body) {
      padding: 20px;
    }
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;

    .card-title {
      font-size: 16px;
      font-weight: 600;
      color: #1f2937;
    }
  }

  .w-full {
    width: 100%;
  }

  .mb-4 {
    margin-bottom: 16px;
  }

  .mt-4 {
    margin-top: 16px;
  }

  // 训练进度
  .training-progress {
    padding: 12px;
    background: #f8fafc;
    border-radius: 8px;
  }

  // 训练日志
  .training-logs {
    .log-container {
      max-height: 200px;
      overflow-y: auto;
      padding: 12px;
      background: #1e293b;
      border-radius: 8px;
      font-family: 'Monaco', 'Menlo', monospace;
      font-size: 12px;

      .log-item {
        display: flex;
        gap: 12px;
        margin-bottom: 4px;
        color: #94a3b8;

        .log-time {
          color: #64748b;
          flex-shrink: 0;
        }

        .log-message {
          color: #e2e8f0;
        }
      }
    }
  }

  // 预测结果
  .prediction-results {
    .prediction-item {
      padding: 12px;
      background: #f8fafc;
      border-radius: 8px;
      font-size: 14px;

      .text-up {
        color: #10b981;
      }

      .text-down {
        color: #ef4444;
      }
    }
  }

  // 评估结果
  .evaluation-results {
    .metric-item {
      padding: 12px;
      background: #f8fafc;
      border-radius: 8px;
      text-align: center;
      margin-bottom: 12px;

      .metric-label {
        font-size: 12px;
        color: #64748b;
        margin-bottom: 4px;
      }

      .metric-value {
        font-size: 20px;
        font-weight: 600;
        color: #1f2937;
      }
    }
  }

  // 特征重要性
  .feature-card {
    margin-top: 16px;
  }

  .feature-importance-container {
    padding: 8px 0;

    .feature-item {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;

      .feature-name {
        width: 100px;
        text-align: right;
        font-size: 14px;
        color: #64748b;
        flex-shrink: 0;
      }

      .feature-bar-container {
        flex: 1;
        height: 20px;
        background: #f1f5f9;
        border-radius: 9999px;
        overflow: hidden;

        .feature-bar {
          height: 100%;
          background: #6366f1;
          border-radius: 9999px;
          transition: width 0.3s ease;
        }
      }

      .feature-value {
        width: 60px;
        font-size: 14px;
        font-weight: 500;
        color: #1f2937;
        flex-shrink: 0;
      }
    }
  }

  // 图表容器
  .chart-container {
    width: 100%;
  }
}
</style>
