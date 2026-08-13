<template>
  <div class="recall-audit-page">
    <!-- 统计卡片 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-5 mb-4">
      <h3 class="font-semibold text-slate-800 mb-4">召回审计统计</h3>
      <div v-if="statsLoading" class="flex justify-center py-4">
        <el-icon class="is-loading"><Loading /></el-icon>
      </div>
      <div v-else-if="stats" class="grid grid-cols-4 gap-4">
        <div class="stat-card">
          <div class="stat-label">总召回次数</div>
          <div class="stat-value">{{ stats.total }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">注入次数</div>
          <div class="stat-value text-green-600">{{ stats.injected }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">抑制次数</div>
          <div class="stat-value text-slate-500">{{ stats.suppressed }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">注入率</div>
          <div class="stat-value text-blue-600">{{ (stats.injection_rate * 100).toFixed(1) }}%</div>
        </div>
      </div>

      <!-- 抑制原因统计 -->
      <div v-if="stats && Object.keys(stats.suppress_reasons).length > 0" class="mt-4 pt-4 border-t border-slate-100">
        <div class="text-xs text-slate-500 mb-2">抑制原因分布</div>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="(count, reason) in stats.suppress_reasons"
            :key="reason"
            class="text-xs px-2 py-1 bg-slate-100 text-slate-600 rounded"
          >
            {{ reason }}: {{ count }}
          </span>
        </div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-4">
      <div class="flex items-center gap-3 flex-wrap">
        <el-select v-model="filters.flow" placeholder="全部流程" size="small" style="width: 160px" clearable @change="loadAudit">
          <el-option label="全部流程" value="" />
          <el-option label="交互对话" value="interactive-chat" />
          <el-option label="技能调用" value="skill-invocation" />
          <el-option label="调度任务" value="scheduled-task" />
          <el-option label="唤醒事件" value="wake-event" />
        </el-select>

        <el-select v-model="filters.gate_result" placeholder="全部结果" size="small" style="width: 140px" clearable @change="loadAudit">
          <el-option label="全部结果" value="" />
          <el-option label="已注入" value="passed" />
          <el-option label="已抑制" value="suppressed" />
        </el-select>

        <el-date-picker
          v-model="dateRange"
          type="daterange"
          size="small"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 240px"
          @change="handleDateChange"
        />

        <el-switch
          v-model="filters.suppressed_only"
          active-text="仅抑制"
          size="small"
          @change="loadAudit"
        />

        <button
          class="px-3 py-1.5 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600"
          @click="loadAll"
        >
          刷新
        </button>
      </div>
    </div>

    <!-- 审计列表 -->
    <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <el-table
        :data="items"
        v-loading="loading"
        size="small"
        :row-class-name="rowClassName"
        @expand-change="handleExpandChange"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="px-4 py-3 bg-slate-50">
              <div v-if="row.hits.length === 0" class="text-xs text-slate-400">无召回命中</div>
              <div v-else class="space-y-2">
                <div
                  v-for="(hit, idx) in row.hits"
                  :key="idx"
                  class="hit-card bg-white border border-slate-200 rounded-lg p-3"
                >
                  <div class="flex items-start justify-between mb-2">
                    <div class="flex items-center gap-2">
                      <span class="text-xs font-medium text-slate-700">记忆 #{{ hit.memory_id }}</span>
                      <span class="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
                        {{ hit.source }}
                      </span>
                      <span class="text-xs text-slate-500">得分: {{ hit.score.toFixed(3) }}</span>
                      <span v-if="hit.bm25_score != null" class="text-xs text-slate-400">
                        BM25: {{ hit.bm25_score.toFixed(3) }}
                      </span>
                      <span v-if="hit.vector_score != null" class="text-xs text-slate-400">
                        向量: {{ hit.vector_score.toFixed(3) }}
                      </span>
                    </div>
                    <div class="flex items-center gap-1">
                      <button
                        :class="[
                          'text-xs px-2 py-1 rounded border',
                          hit.feedback === 'relevant'
                            ? 'border-green-500 bg-green-50 text-green-600'
                            : 'border-slate-200 text-slate-500 hover:bg-green-50'
                        ]"
                        :disabled="feedbackLoading"
                        @click="handleFeedback(row.id, hit.memory_id, 'relevant')"
                      >
                        👍 相关
                      </button>
                      <button
                        :class="[
                          'text-xs px-2 py-1 rounded border',
                          hit.feedback === 'irrelevant'
                            ? 'border-red-500 bg-red-50 text-red-600'
                            : 'border-slate-200 text-slate-500 hover:bg-red-50'
                        ]"
                        :disabled="feedbackLoading"
                        @click="handleFeedback(row.id, hit.memory_id, 'irrelevant')"
                      >
                        👎 不相关
                      </button>
                    </div>
                  </div>
                  <div v-if="hit.title" class="text-xs font-medium text-slate-700 mb-1">{{ hit.title }}</div>
                  <div class="text-xs text-slate-600 line-clamp-2">
                    {{ hit.content || '(无内容)' }}
                  </div>
                  <div v-if="hit.feedback_by" class="text-xs text-slate-400 mt-1">
                    已标注：{{ hit.feedback }} ({{ hit.feedback_by }})
                  </div>
                </div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="时间" width="150">
          <template #default="{ row }">{{ formatTime(row.ts) }}</template>
        </el-table-column>

        <el-table-column label="流程" width="110">
          <template #default="{ row }">
            <span class="text-xs px-2 py-0.5 rounded-full" :class="flowClass(row.flow)">
              {{ flowLabel(row.flow) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="query_text" label="查询文本" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="text-xs">{{ row.query_text || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <span class="text-xs px-2 py-0.5 rounded-full" :class="gateClass(row.gate_result)">
              {{ row.gate_result === 'passed' ? '已注入' : '已抑制' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="抑制原因" width="120">
          <template #default="{ row }">
            <span v-if="row.suppress_reason" class="text-xs text-slate-500">
              {{ row.suppress_reason }}
            </span>
            <span v-else class="text-xs text-slate-300">-</span>
          </template>
        </el-table-column>

        <el-table-column label="命中数" width="80" align="center">
          <template #default="{ row }">{{ row.hits.length }}</template>
        </el-table-column>

        <el-table-column label="策略" width="80">
          <template #default="{ row }">
            <span class="text-xs text-slate-500">{{ row.strategy || '-' }}</span>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && items.length === 0" description="无召回审计记录" :image-size="60" />

      <!-- 分页 -->
      <div v-if="total > 0" class="flex justify-center py-3 border-t border-slate-100">
        <el-pagination
          v-model:current-page="filters.page"
          v-model:page-size="filters.page_size"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          small
          @current-change="loadAudit"
          @size-change="loadAudit"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { recallAuditApi, type RecallAuditItem, type RecallAuditStats } from '@/services/api/memory'

// ---------- 数据 ----------
const items = ref<RecallAuditItem[]>([])
const total = ref(0)
const loading = ref(false)
const statsLoading = ref(false)
const feedbackLoading = ref(false)
const stats = ref<RecallAuditStats | null>(null)

const filters = reactive({
  flow: '',
  gate_result: '',
  date_from: '',
  date_to: '',
  suppressed_only: false,
  page: 1,
  page_size: 20,
})

const dateRange = ref<[Date, Date] | null>(null)

// ---------- 加载数据 ----------
async function loadAudit() {
  loading.value = true
  try {
    const resp = await recallAuditApi.getAudit({
      flow: filters.flow || undefined,
      gate_result: filters.gate_result || undefined,
      date_from: filters.date_from || undefined,
      date_to: filters.date_to || undefined,
      suppressed_only: filters.suppressed_only || undefined,
      page: filters.page,
      page_size: filters.page_size,
    })
    items.value = resp.items || []
    total.value = resp.total ?? 0
  } catch (error) {
    ElMessage.error('加载召回审计失败')
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  statsLoading.value = true
  try {
    const resp = await recallAuditApi.getStats({
      date_from: filters.date_from || undefined,
      date_to: filters.date_to || undefined,
    })
    stats.value = resp
  } catch (error) {
    stats.value = null
  } finally {
    statsLoading.value = false
  }
}

function loadAll() {
  loadAudit()
  loadStats()
}

function handleDateChange(val: [Date, Date] | null) {
  if (val && val.length === 2) {
    filters.date_from = val[0].toISOString().split('T')[0]
    filters.date_to = val[1].toISOString().split('T')[0]
  } else {
    filters.date_from = ''
    filters.date_to = ''
  }
  loadAll()
}

// ---------- 反馈标注 ----------
async function handleFeedback(auditId: number, memoryId: number, feedback: 'relevant' | 'irrelevant') {
  feedbackLoading.value = true
  try {
    await recallAuditApi.postFeedback(auditId, {
      memory_id: memoryId,
      feedback,
      feedback_by: 'human',
    })
    ElMessage.success(`已标注为${feedback === 'relevant' ? '相关' : '不相关'}`)

    // 本地更新状态
    const item = items.value.find(it => it.id === auditId)
    if (item) {
      const hit = item.hits.find(h => h.memory_id === memoryId)
      if (hit) {
        hit.feedback = feedback
        hit.feedback_by = 'human'
      }
    }
  } catch (error: any) {
    if (error.response?.status === 409) {
      ElMessage.error('无法覆盖已有的人工标注')
    } else {
      ElMessage.error('标注失败')
    }
  } finally {
    feedbackLoading.value = false
  }
}

// ---------- 展示辅助 ----------
function rowClassName({ row }: { row: RecallAuditItem }) {
  return row.gate_result === 'suppressed' ? 'suppressed-row' : ''
}

function handleExpandChange() {
  // 展开时不需要额外加载，hits 已在列表中
}

function flowLabel(flow: string) {
  const labels: Record<string, string> = {
    'interactive-chat': '交互对话',
    'skill-invocation': '技能调用',
    'scheduled-task': '调度任务',
    'wake-event': '唤醒事件',
  }
  return labels[flow] || flow
}

function flowClass(flow: string) {
  const classes: Record<string, string> = {
    'interactive-chat': 'bg-blue-100 text-blue-700',
    'skill-invocation': 'bg-purple-100 text-purple-700',
    'scheduled-task': 'bg-green-100 text-green-700',
    'wake-event': 'bg-orange-100 text-orange-700',
  }
  return classes[flow] || 'bg-slate-100 text-slate-600'
}

function gateClass(gate: string) {
  return gate === 'passed' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
}

function formatTime(t: string | null | undefined) {
  if (!t) return '-'
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.stat-card {
  text-align: center;
}

.stat-label {
  font-size: 0.75rem;
  color: #64748b;
  margin-bottom: 0.25rem;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 600;
  color: #1e293b;
}

.hit-card {
  transition: all 0.2s;
}

.hit-card:hover {
  box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
}

:deep(.suppressed-row) {
  background-color: #f8fafc;
  color: #94a3b8;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
